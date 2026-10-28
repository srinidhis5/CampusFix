from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


ROLES = ("reporter", "admin", "maintenance")
CATEGORIES = ("Electrical", "Plumbing", "Network", "Furniture", "Sanitation", "Laboratory Equipment", "Other")
PRIORITIES = ("Low", "Medium", "High", "Emergency")
STATUSES = ("Submitted", "Assigned", "In Progress", "Resolved", "Closed", "Reopened")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="reporter")
    department = db.Column(db.String(120), nullable=False, default="")
    phone = db.Column(db.String(30))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    reported_complaints = db.relationship("Complaint", foreign_keys="Complaint.reporter_id", back_populates="reporter")
    assigned_complaints = db.relationship("Complaint", foreign_keys="Complaint.assignee_id", back_populates="assignee")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    building = db.Column(db.String(120), nullable=False)
    room_location = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Submitted", index=True)
    image_filename = db.Column(db.String(255))
    completion_image_filename = db.Column(db.String(255))
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    due_at = db.Column(db.DateTime, nullable=False)
    reopen_count = db.Column(db.Integer, nullable=False, default=0)

    reporter = db.relationship("User", foreign_keys=[reporter_id], back_populates="reported_complaints")
    assignee = db.relationship("User", foreign_keys=[assignee_id], back_populates="assigned_complaints")
    updates = db.relationship("ComplaintUpdate", back_populates="complaint", cascade="all, delete-orphan", order_by="ComplaintUpdate.created_at")
    feedback = db.relationship("Feedback", back_populates="complaint", cascade="all, delete-orphan", uselist=False)
    prediction_log = db.relationship("PredictionLog", back_populates="complaint", cascade="all, delete-orphan", uselist=False)

    @property
    def is_overdue(self):
        return self.status not in ("Resolved", "Closed") and datetime.utcnow() > self.due_at


class ComplaintUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    old_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    complaint = db.relationship("Complaint", back_populates="updates")
    actor = db.relationship("User")


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), unique=True, nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    complaint = db.relationship("Complaint", back_populates="feedback")
    reporter = db.relationship("User")


class PredictionLog(db.Model):
    __tablename__ = "predictions_log"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), unique=True)
    predicted_category = db.Column(db.String(40))
    final_category = db.Column(db.String(40), nullable=False)
    predicted_priority = db.Column(db.String(20))
    final_priority = db.Column(db.String(20), nullable=False)
    category_confidence = db.Column(db.Float)
    priority_confidence = db.Column(db.Float)
    was_corrected = db.Column(db.Boolean, nullable=False, default=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    complaint = db.relationship("Complaint", back_populates="prediction_log")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    related_complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="notifications")
    related_complaint = db.relationship("Complaint")


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    actor = db.relationship("User")
