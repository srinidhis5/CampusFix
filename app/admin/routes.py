import csv
import io
import json
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.admin.forms import AssignForm, PriorityForm, StaffForm
from app.decorators import role_required
from app.extensions import db
from app.models import AuditLog, CATEGORIES, Complaint, Feedback, Notification, PredictionLog, PRIORITIES, STATUSES, User
from app.services.complaint_service import WorkflowError, assign_complaint, audit, change_status, export_review_queue
from app.services.notification_service import notify
from app.services.reporting_service import apply_complaint_filters, average_rating, breakdown, staff_workload
from src.predict import predict_complaint

admin_bp = Blueprint("admin", __name__)


def _load_ml_metrics():
    path = Path("models/metrics.json")
    if not path.exists():
        return {"model_name": "No trained model metrics found", "targets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_prediction_logs():
    logged_ids = {row[0] for row in PredictionLog.query.with_entities(PredictionLog.complaint_id).all() if row[0] is not None}
    missing = Complaint.query.filter(~Complaint.id.in_(logged_ids)).all() if logged_ids else Complaint.query.all()
    for complaint in missing:
        prediction = predict_complaint(complaint.title, complaint.description)
        predicted_category = prediction.get("category")
        predicted_priority = prediction.get("priority")
        db.session.add(
            PredictionLog(
                complaint_id=complaint.id,
                predicted_category=predicted_category,
                final_category=complaint.category,
                predicted_priority=predicted_priority,
                final_priority=complaint.priority,
                category_confidence=prediction.get("category_confidence"),
                priority_confidence=prediction.get("priority_confidence"),
                was_corrected=bool(
                    (predicted_category and predicted_category != complaint.category)
                    or (predicted_priority and predicted_priority != complaint.priority)
                ),
            )
        )
    if missing:
        db.session.commit()


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    _ensure_prediction_logs()
    counts = {status: Complaint.query.filter_by(status=status).count() for status in STATUSES}
    resolved = Complaint.query.filter(Complaint.resolved_at.isnot(None)).all()
    avg_hours = 0
    if resolved:
        avg_hours = round(sum((c.resolved_at - c.created_at).total_seconds() / 3600 for c in resolved) / len(resolved), 2)
    prediction_total = PredictionLog.query.count()
    corrected = PredictionLog.query.filter_by(was_corrected=True).count()
    return render_template(
        "admin/dashboard.html",
        total=Complaint.query.count(),
        counts=counts,
        unassigned=Complaint.query.filter_by(assignee_id=None).count(),
        overdue=[c for c in Complaint.query.all() if c.is_overdue],
        emergency=Complaint.query.filter_by(priority="Emergency").count(),
        avg_hours=avg_hours,
        avg_rating=average_rating(),
        by_category=breakdown(Complaint.category),
        category_cards=[(category, breakdown(Complaint.category).get(category, 0)) for category in CATEGORIES],
        by_status=breakdown(Complaint.status),
        by_priority=breakdown(Complaint.priority),
        workload=staff_workload(),
        recent=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all(),
        emergency_complaints=Complaint.query.filter_by(priority="Emergency").order_by(Complaint.created_at.desc()).limit(8).all(),
        prediction_logs=PredictionLog.query.order_by(PredictionLog.timestamp.desc()).limit(10).all(),
        correction_rate=round((corrected / prediction_total) * 100, 1) if prediction_total else 0,
    )


@admin_bp.route("/complaints")
@login_required
@role_required("admin")
def complaints():
    query = apply_complaint_filters(Complaint.query, request.args)
    term = request.args.get("q", "").strip()
    if term:
        like = f"%{term}%"
        query = query.join(User, Complaint.reporter_id == User.id).filter(
            (Complaint.reference_number.like(like)) | (Complaint.title.like(like)) | (Complaint.building.like(like)) | (User.full_name.like(like))
        )
    return render_template(
        "admin/complaints.html",
        complaints=query.order_by(Complaint.created_at.desc()).all(),
        staff=User.query.filter_by(role="maintenance").all(),
        statuses=STATUSES,
        categories=CATEGORIES,
        priorities=PRIORITIES,
    )


@admin_bp.route("/complaints/unassigned")
@login_required
@role_required("admin")
def unassigned():
    query = apply_complaint_filters(Complaint.query.filter_by(assignee_id=None), request.args)
    term = request.args.get("q", "").strip()
    if term:
        like = f"%{term}%"
        query = query.join(User, Complaint.reporter_id == User.id).filter(
            (Complaint.reference_number.like(like)) | (Complaint.title.like(like)) | (Complaint.building.like(like)) | (User.full_name.like(like))
        )
    complaints = query.order_by(Complaint.created_at.desc()).all()
    return render_template(
        "admin/complaints.html",
        complaints=complaints,
        staff=User.query.filter_by(role="maintenance").all(),
        title="Unassigned complaints",
        statuses=STATUSES,
        categories=CATEGORIES,
        priorities=PRIORITIES,
    )


@admin_bp.route("/categories/<category>")
@login_required
@role_required("admin")
def category_detail(category):
    if category not in CATEGORIES:
        abort(404)
    complaints = Complaint.query.filter_by(category=category).order_by(Complaint.created_at.desc()).all()
    status_counts = dict(
        Complaint.query.with_entities(Complaint.status, func.count(Complaint.id))
        .filter_by(category=category)
        .group_by(Complaint.status)
        .all()
    )
    priority_counts = dict(
        Complaint.query.with_entities(Complaint.priority, func.count(Complaint.id))
        .filter_by(category=category)
        .group_by(Complaint.priority)
        .all()
    )
    return render_template(
        "admin/category_detail.html",
        category=category,
        complaints=complaints,
        status_counts=status_counts,
        priority_counts=priority_counts,
        total=len(complaints),
    )


@admin_bp.route("/complaints/<int:complaint_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def complaint_detail(complaint_id):
    complaint = db.session.get(Complaint, complaint_id) or abort(404)
    priority_form = PriorityForm(prefix="priority")
    if priority_form.validate_on_submit() and request.form.get("form_name") == "priority":
        old = complaint.priority
        complaint.priority = priority_form.priority.data
        audit(current_user, "priority_change", "Complaint", complaint.id, f"{old} to {complaint.priority}")
        db.session.commit()
        flash("Priority updated.", "success")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint.id))
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "progress" and complaint.status == "Assigned":
                change_status(current_user, complaint, "In Progress", request.form.get("note", "Started by administrator."))
            elif action == "resolve" and complaint.status == "In Progress":
                change_status(current_user, complaint, "Resolved", request.form.get("note", "Resolved by administrator."))
            elif action == "close" and complaint.status == "Resolved":
                change_status(current_user, complaint, "Closed", request.form.get("note", "Closed by administrator."))
            elif action == "reopen" and complaint.status == "Resolved":
                change_status(current_user, complaint, "Reopened", request.form.get("note", "Reopened by administrator."))
            else:
                flash("Action is not valid for the current status.", "danger")
                return redirect(url_for("admin.complaint_detail", complaint_id=complaint.id))
            flash("Complaint updated.", "success")
        except WorkflowError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint.id))
    priority_form.priority.data = complaint.priority
    return render_template("admin/detail.html", complaint=complaint, priority_form=priority_form)


@admin_bp.route("/complaints/<int:complaint_id>/assign", methods=["GET", "POST"])
@login_required
@role_required("admin")
def assign(complaint_id):
    complaint = db.session.get(Complaint, complaint_id) or abort(404)
    form = AssignForm()
    form.assignee_id.choices = [(u.id, f"{u.full_name} - {u.department}") for u in User.query.filter_by(role="maintenance", is_active=True).all()]
    if form.validate_on_submit():
        try:
            assign_complaint(current_user, complaint, form.assignee_id.data, form.note.data)
            flash("Complaint assigned.", "success")
            return redirect(url_for("admin.complaint_detail", complaint_id=complaint.id))
        except WorkflowError as exc:
            flash(str(exc), "danger")
    return render_template("admin/assign.html", form=form, complaint=complaint)


@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    return render_template("admin/users.html", users=User.query.order_by(User.role, User.full_name).all())


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def toggle_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
    else:
        user.is_active = not user.is_active
        audit(current_user, "toggle_user", "User", user.id, f"Set active={user.is_active}")
        db.session.commit()
        flash("User status updated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/create-maintenance", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_maintenance():
    form = StaffForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
        else:
            user = User(full_name=form.full_name.data, email=email, role="maintenance", department=form.department.data, phone=form.phone.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()
            audit(current_user, "create_staff", "User", user.id, f"Created maintenance account {email}")
            db.session.commit()
            flash("Maintenance account created.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/create_maintenance.html", form=form)


@admin_bp.route("/reports")
@login_required
@role_required("admin")
def reports():
    query = apply_complaint_filters(Complaint.query, request.args)
    complaints = query.all()
    return render_template(
        "admin/reports.html",
        total=len(complaints),
        category=breakdown(Complaint.category),
        status=breakdown(Complaint.status),
        priority=breakdown(Complaint.priority),
        buildings=dict(Complaint.query.with_entities(Complaint.building, func.count(Complaint.id)).group_by(Complaint.building).all()),
        workload=staff_workload(),
        avg_rating=average_rating(),
        overdue=len([c for c in complaints if c.is_overdue]),
    )


@admin_bp.route("/reports/export.csv")
@login_required
@role_required("admin")
def export_csv():
    complaints = apply_complaint_filters(Complaint.query, request.args).order_by(Complaint.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reference", "Title", "Category", "Building", "Location", "Priority", "Status", "Reporter", "Assignee", "Created"])
    for c in complaints:
        writer.writerow([c.reference_number, c.title, c.category, c.building, c.room_location, c.priority, c.status, c.reporter.full_name, c.assignee.full_name if c.assignee else "", c.created_at.isoformat()])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=campusfix_complaints.csv"})


@admin_bp.route("/feedback")
@login_required
@role_required("admin")
def feedback():
    return render_template("admin/feedback.html", feedback=Feedback.query.order_by(Feedback.created_at.desc()).all())


@admin_bp.route("/audit-log")
@login_required
@role_required("admin")
def audit_log():
    return render_template("admin/audit.html", logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all())


@admin_bp.route("/ml-insights")
@login_required
@role_required("admin")
def ml_insights():
    reports_dir = Path("reports")
    matrices = sorted(path.name for path in reports_dir.glob("*.png")) if reports_dir.exists() else []
    prediction_total = PredictionLog.query.count()
    corrected = PredictionLog.query.filter_by(was_corrected=True).count()
    return render_template(
        "admin/ml_insights.html",
        metrics=_load_ml_metrics(),
        matrices=matrices,
        review_queue=PredictionLog.query.filter_by(was_corrected=True).order_by(PredictionLog.timestamp.desc()).all(),
        prediction_total=prediction_total,
        correction_rate=round((corrected / prediction_total) * 100, 1) if prediction_total else 0,
    )


@admin_bp.route("/ml-insights/confusion/<path:filename>")
@login_required
@role_required("admin")
def confusion_matrix(filename):
    path = Path("reports") / filename
    if not path.is_file() or path.suffix.lower() != ".png":
        abort(404)
    return send_file(path)


@admin_bp.route("/ml-insights/review-queue.csv")
@login_required
@role_required("admin")
def review_queue_csv():
    path = export_review_queue()
    return send_file(path, mimetype="text/csv", as_attachment=True, download_name="review_queue.csv")


@admin_bp.route("/notifications")
@login_required
@role_required("admin")
def notifications():
    return render_template("notifications.html", notifications=Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all())


@admin_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
@role_required("admin")
def mark_notification(notification_id):
    item = db.session.get(Notification, notification_id) or abort(404)
    if item.user_id != current_user.id:
        abort(403)
    item.is_read = True
    db.session.commit()
    return redirect(url_for("admin.notifications"))


@admin_bp.route("/profile")
@login_required
@role_required("admin")
def profile():
    return render_template("profile.html")
