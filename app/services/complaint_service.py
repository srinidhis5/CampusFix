import csv
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import AuditLog, Complaint, ComplaintUpdate, PredictionLog, User
from app.services.notification_service import notify, notify_admins

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
DUE_HOURS = {"Emergency": 4, "High": 24, "Medium": 72, "Low": 168}
VALID_TRANSITIONS = {
    "Submitted": {"Assigned"},
    "Assigned": {"In Progress"},
    "In Progress": {"Resolved"},
    "Resolved": {"Closed", "Reopened"},
    "Reopened": {"Assigned"},
}


class WorkflowError(ValueError):
    pass


def due_for_priority(priority):
    return datetime.utcnow() + timedelta(hours=DUE_HOURS[priority])


def next_reference():
    year = datetime.utcnow().year
    count = Complaint.query.filter(Complaint.reference_number.like(f"CMP-{year}-%")).count() + 1
    return f"CMP-{year}-{count:04d}"


def duplicate_candidates(category, building, room_location):
    return Complaint.query.filter(
        Complaint.category == category,
        Complaint.building == building,
        Complaint.room_location == room_location,
        Complaint.status != "Closed",
    ).all()


def allowed_file(file_storage: FileStorage):
    filename = secure_filename(file_storage.filename or "")
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    head = file_storage.stream.read(512)
    file_storage.stream.seek(0)
    is_png = head.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = head.startswith(b"\xff\xd8\xff")
    return is_png or is_jpeg


def save_upload(file_storage, upload_folder):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage):
        raise ValueError("Only PNG, JPG and JPEG images are allowed.")
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, filename))
    return filename


def audit(actor, action, entity_type, entity_id, description):
    db.session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
        )
    )


def _prediction_was_corrected(data):
    predicted_category = data.get("predicted_category")
    predicted_priority = data.get("predicted_priority")
    return bool(
        (predicted_category and predicted_category != data["category"])
        or (predicted_priority and predicted_priority != data["priority"])
    )


def create_complaint(reporter, data, image_filename=None):
    complaint = Complaint(
        reference_number=next_reference(),
        title=data["title"],
        description=data["description"],
        category=data["category"],
        building=data["building"],
        room_location=data["room_location"],
        priority=data["priority"],
        reporter_id=reporter.id,
        image_filename=image_filename,
        due_at=due_for_priority(data["priority"]),
    )
    db.session.add(complaint)
    db.session.flush()
    db.session.add(
        PredictionLog(
            complaint_id=complaint.id,
            predicted_category=data.get("predicted_category"),
            final_category=data["category"],
            predicted_priority=data.get("predicted_priority"),
            final_priority=data["priority"],
            category_confidence=data.get("category_confidence"),
            priority_confidence=data.get("priority_confidence"),
            was_corrected=_prediction_was_corrected(data),
        )
    )
    db.session.add(
        ComplaintUpdate(
            complaint_id=complaint.id,
            actor_id=reporter.id,
            old_status=None,
            new_status="Submitted",
            note="Complaint submitted.",
        )
    )
    notify_admins("New complaint submitted", f"{complaint.reference_number}: {complaint.title}", complaint)
    notify(reporter, "Complaint submitted", f"{complaint.reference_number} was submitted.", complaint)
    audit(reporter, "create", "Complaint", complaint.id, f"Created {complaint.reference_number}")
    db.session.commit()
    return complaint


def export_review_queue(path="data/review_queue.csv"):
    rows = PredictionLog.query.filter_by(was_corrected=True).order_by(PredictionLog.timestamp.desc()).all()
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "complaint_id",
                "complaint_text",
                "predicted_category",
                "final_category",
                "predicted_priority",
                "final_priority",
                "category_confidence",
                "priority_confidence",
                "timestamp",
            ]
        )
        for row in rows:
            text = ""
            if row.complaint:
                text = f"{row.complaint.title} {row.complaint.description}".strip()
            writer.writerow(
                [
                    row.complaint_id,
                    text,
                    row.predicted_category or "",
                    row.final_category,
                    row.predicted_priority or "",
                    row.final_priority,
                    row.category_confidence if row.category_confidence is not None else "",
                    row.priority_confidence if row.priority_confidence is not None else "",
                    row.timestamp.isoformat(),
                ]
            )
    return output_path


def can_transition(actor, complaint, new_status):
    old = complaint.status
    if new_status not in VALID_TRANSITIONS.get(old, set()):
        return False
    if old in ("Submitted", "Reopened") and new_status == "Assigned":
        return actor.role == "admin"
    if old == "Assigned" and new_status == "In Progress":
        return actor.role == "admin" or (actor.role == "maintenance" and complaint.assignee_id == actor.id)
    if old == "In Progress" and new_status == "Resolved":
        return actor.role == "admin" or (actor.role == "maintenance" and complaint.assignee_id == actor.id)
    if old == "Resolved" and new_status in ("Closed", "Reopened"):
        return actor.role == "admin" or (actor.role == "reporter" and complaint.reporter_id == actor.id)
    return False


def change_status(actor, complaint, new_status, note=""):
    if not can_transition(actor, complaint, new_status):
        raise WorkflowError("Invalid or unauthorized status transition.")
    old_status = complaint.status
    if new_status == "Reopened" and complaint.reopen_count >= 1:
        raise WorkflowError("A complaint can be reopened only once.")
    complaint.status = new_status
    complaint.updated_at = datetime.utcnow()
    if new_status == "Assigned":
        complaint.assigned_at = datetime.utcnow()
    if new_status == "Resolved":
        complaint.resolved_at = datetime.utcnow()
    if new_status == "Closed":
        complaint.closed_at = datetime.utcnow()
    if new_status == "Reopened":
        complaint.reopen_count += 1
    db.session.add(ComplaintUpdate(complaint_id=complaint.id, actor_id=actor.id, old_status=old_status, new_status=new_status, note=note))
    recipients = [complaint.reporter, complaint.assignee]
    for user in recipients:
        if user and user.id != actor.id:
            notify(user, "Complaint status changed", f"{complaint.reference_number} changed to {new_status}.", complaint)
    notify_admins("Complaint status changed", f"{complaint.reference_number}: {old_status} to {new_status}", complaint)
    audit(actor, "status_change", "Complaint", complaint.id, f"{old_status} to {new_status}")
    db.session.commit()


def assign_complaint(actor, complaint, assignee_id, note=""):
    assignee = db.session.get(User, int(assignee_id))
    if not assignee or assignee.role != "maintenance" or not assignee.is_active:
        raise WorkflowError("Select an active maintenance staff member.")
    old_assignee = complaint.assignee
    complaint.assignee_id = assignee.id
    if complaint.status in ("Submitted", "Reopened"):
        old_status = complaint.status
        complaint.status = "Assigned"
        complaint.assigned_at = datetime.utcnow()
        db.session.add(ComplaintUpdate(complaint_id=complaint.id, actor_id=actor.id, old_status=old_status, new_status="Assigned", note=note or "Complaint assigned."))
    else:
        db.session.add(ComplaintUpdate(complaint_id=complaint.id, actor_id=actor.id, old_status=complaint.status, new_status=complaint.status, note=note or "Complaint reassigned."))
    complaint.updated_at = datetime.utcnow()
    notify(assignee, "Complaint assigned", f"{complaint.reference_number} is assigned to you.", complaint)
    notify(complaint.reporter, "Complaint assigned", f"{complaint.reference_number} was assigned to {assignee.full_name}.", complaint)
    action = "reassign" if old_assignee else "assign"
    audit(actor, action, "Complaint", complaint.id, f"{complaint.reference_number} assigned to {assignee.email}")
    db.session.commit()


def add_progress(actor, complaint, note, completion_image_filename=None, mark_resolved=False):
    if actor.role not in ("admin", "maintenance") or (actor.role == "maintenance" and complaint.assignee_id != actor.id):
        raise WorkflowError("Not allowed to update this complaint.")
    if completion_image_filename:
        complaint.completion_image_filename = completion_image_filename
    db.session.add(ComplaintUpdate(complaint_id=complaint.id, actor_id=actor.id, old_status=complaint.status, new_status=complaint.status, note=note))
    notify(complaint.reporter, "Progress note added", f"Update added on {complaint.reference_number}.", complaint)
    audit(actor, "progress_note", "Complaint", complaint.id, f"Progress added to {complaint.reference_number}")
    db.session.commit()
    if mark_resolved and complaint.status == "In Progress":
        change_status(actor, complaint, "Resolved", note or "Complaint resolved.")
