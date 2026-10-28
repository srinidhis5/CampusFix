from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import role_required
from app.extensions import db
from app.models import CATEGORIES, PRIORITIES, STATUSES, Complaint, Feedback, Notification
from app.services.complaint_service import WorkflowError, change_status, create_complaint, duplicate_candidates, save_upload
from app.services.notification_service import notify_admins

from .forms import ComplaintForm, FeedbackForm

reporter_bp = Blueprint("reporter", __name__)


def reporter_complaint_or_403(complaint_id):
    complaint = db.session.get(Complaint, complaint_id) or abort(404)
    if complaint.reporter_id != current_user.id:
        abort(403)
    return complaint


@reporter_bp.route("/dashboard")
@login_required
@role_required("reporter")
def dashboard():
    complaints = Complaint.query.filter_by(reporter_id=current_user.id)
    return render_template(
        "reporter/dashboard.html",
        total=complaints.count(),
        submitted=complaints.filter_by(status="Submitted").count(),
        progress=complaints.filter(Complaint.status.in_(["Assigned", "In Progress", "Reopened"])).count(),
        done=complaints.filter(Complaint.status.in_(["Resolved", "Closed"])).count(),
        recent=complaints.order_by(Complaint.updated_at.desc()).limit(5).all(),
        unread=Notification.query.filter_by(user_id=current_user.id, is_read=False).count(),
    )


@reporter_bp.route("/complaints/new", methods=["GET", "POST"])
@login_required
@role_required("reporter")
def submit_complaint():
    form = ComplaintForm()
    duplicates = []
    if form.validate_on_submit():
        duplicates = duplicate_candidates(form.category.data, form.building.data, form.room_location.data)
        if duplicates and form.confirm_duplicate.data != "yes":
            flash("Possible duplicate complaints found. Review them before continuing.", "warning")
            return render_template("reporter/submit.html", form=form, duplicates=duplicates)
        try:
            filename = save_upload(form.image.data, current_app.config["UPLOAD_FOLDER"]) if form.image.data else None
            complaint = create_complaint(
                current_user,
                {
                    "title": form.title.data,
                    "description": form.description.data,
                    "category": form.category.data,
                    "building": form.building.data,
                    "room_location": form.room_location.data,
                    "priority": form.priority.data,
                    "predicted_category": form.predicted_category.data or None,
                    "predicted_priority": form.predicted_priority.data or None,
                    "category_confidence": float(form.category_confidence.data) if form.category_confidence.data else None,
                    "priority_confidence": float(form.priority_confidence.data) if form.priority_confidence.data else None,
                },
                filename,
            )
            flash("Complaint submitted successfully.", "success")
            return redirect(url_for("reporter.complaint_detail", complaint_id=complaint.id))
        except ValueError as exc:
            flash(str(exc), "danger")
    return render_template("reporter/submit.html", form=form, duplicates=duplicates)


@reporter_bp.route("/complaints")
@login_required
@role_required("reporter")
def complaints():
    query = Complaint.query.filter_by(reporter_id=current_user.id)
    term = request.args.get("q", "").strip()
    for field in ("status", "category", "priority"):
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(Complaint, field) == value)
    if term:
        like = f"%{term}%"
        query = query.filter((Complaint.reference_number.like(like)) | (Complaint.title.like(like)) | (Complaint.room_location.like(like)))
    return render_template(
        "reporter/complaints.html",
        complaints=query.order_by(Complaint.created_at.desc()).all(),
        statuses=STATUSES,
        categories=CATEGORIES,
        priorities=PRIORITIES,
    )


@reporter_bp.route("/complaints/<int:complaint_id>", methods=["GET", "POST"])
@login_required
@role_required("reporter")
def complaint_detail(complaint_id):
    complaint = reporter_complaint_or_403(complaint_id)
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "close":
                change_status(current_user, complaint, "Closed", request.form.get("note", "Closed by reporter."))
            elif action == "reopen":
                change_status(current_user, complaint, "Reopened", request.form.get("note", "Reopened by reporter."))
            flash("Complaint updated.", "success")
        except WorkflowError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("reporter.complaint_detail", complaint_id=complaint.id))
    return render_template("reporter/detail.html", complaint=complaint)


@reporter_bp.route("/complaints/<int:complaint_id>/feedback", methods=["GET", "POST"])
@login_required
@role_required("reporter")
def feedback(complaint_id):
    complaint = reporter_complaint_or_403(complaint_id)
    if complaint.status not in ("Resolved", "Closed") or complaint.feedback:
        abort(403)
    form = FeedbackForm()
    if form.validate_on_submit():
        item = Feedback(complaint_id=complaint.id, reporter_id=current_user.id, rating=form.rating.data, comment=form.comment.data)
        db.session.add(item)
        notify_admins("Feedback submitted", f"{complaint.reference_number} received a rating of {form.rating.data}.", complaint)
        from app.services.complaint_service import audit

        audit(current_user, "feedback", "Complaint", complaint.id, f"Feedback submitted for {complaint.reference_number}")
        db.session.commit()
        flash("Feedback submitted.", "success")
        return redirect(url_for("reporter.complaint_detail", complaint_id=complaint.id))
    return render_template("reporter/feedback.html", form=form, complaint=complaint)


@reporter_bp.route("/notifications")
@login_required
@role_required("reporter")
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template("notifications.html", notifications=items)


@reporter_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
@role_required("reporter")
def mark_notification(notification_id):
    item = db.session.get(Notification, notification_id) or abort(404)
    if item.user_id != current_user.id:
        abort(403)
    item.is_read = True
    db.session.commit()
    return redirect(url_for("reporter.notifications"))


@reporter_bp.route("/profile")
@login_required
@role_required("reporter")
def profile():
    return render_template("profile.html")
