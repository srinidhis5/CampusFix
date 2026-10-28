from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import role_required
from app.extensions import db
from app.maintenance.forms import ProgressForm
from app.models import CATEGORIES, PRIORITIES, STATUSES, Complaint, Notification
from app.services.complaint_service import WorkflowError, add_progress, change_status, save_upload

maintenance_bp = Blueprint("maintenance", __name__)


def assigned_or_403(complaint_id):
    complaint = db.session.get(Complaint, complaint_id) or abort(404)
    if complaint.assignee_id != current_user.id:
        abort(403)
    return complaint


@maintenance_bp.route("/dashboard")
@login_required
@role_required("maintenance")
def dashboard():
    query = Complaint.query.filter_by(assignee_id=current_user.id)
    all_items = query.all()
    return render_template(
        "maintenance/dashboard.html",
        total=len(all_items),
        assigned=query.filter_by(status="Assigned").count(),
        progress=query.filter_by(status="In Progress").count(),
        overdue=len([c for c in all_items if c.is_overdue]),
        recent=query.order_by(Complaint.updated_at.desc()).limit(5).all(),
    )


@maintenance_bp.route("/complaints")
@login_required
@role_required("maintenance")
def complaints():
    query = Complaint.query.filter_by(assignee_id=current_user.id)
    for field in ("status", "category", "priority"):
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(Complaint, field) == value)
    return render_template(
        "maintenance/complaints.html",
        complaints=query.order_by(Complaint.updated_at.desc()).all(),
        statuses=STATUSES,
        categories=CATEGORIES,
        priorities=PRIORITIES,
    )


@maintenance_bp.route("/complaints/<int:complaint_id>", methods=["GET", "POST"])
@login_required
@role_required("maintenance")
def complaint_detail(complaint_id):
    complaint = assigned_or_403(complaint_id)
    if request.method == "POST" and request.form.get("action") == "start":
        try:
            change_status(current_user, complaint, "In Progress", "Work started.")
            flash("Complaint moved to In Progress.", "success")
        except WorkflowError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("maintenance.complaint_detail", complaint_id=complaint.id))
    return render_template("maintenance/detail.html", complaint=complaint)


@maintenance_bp.route("/complaints/<int:complaint_id>/progress", methods=["GET", "POST"])
@login_required
@role_required("maintenance")
def progress(complaint_id):
    complaint = assigned_or_403(complaint_id)
    form = ProgressForm()
    if form.validate_on_submit():
        try:
            filename = save_upload(form.completion_image.data, current_app.config["UPLOAD_FOLDER"]) if form.completion_image.data else None
            add_progress(current_user, complaint, form.note.data, filename, form.mark_resolved.data)
            flash("Progress update saved.", "success")
            return redirect(url_for("maintenance.complaint_detail", complaint_id=complaint.id))
        except (ValueError, WorkflowError) as exc:
            flash(str(exc), "danger")
    return render_template("maintenance/progress.html", form=form, complaint=complaint)


@maintenance_bp.route("/notifications")
@login_required
@role_required("maintenance")
def notifications():
    return render_template("notifications.html", notifications=Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all())


@maintenance_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
@role_required("maintenance")
def mark_notification(notification_id):
    item = db.session.get(Notification, notification_id) or abort(404)
    if item.user_id != current_user.id:
        abort(403)
    item.is_read = True
    db.session.commit()
    return redirect(url_for("maintenance.notifications"))


@maintenance_bp.route("/profile")
@login_required
@role_required("maintenance")
def profile():
    return render_template("profile.html")
