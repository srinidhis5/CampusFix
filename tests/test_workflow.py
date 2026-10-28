import pytest

from app.extensions import db
from app.models import Complaint, User
from app.services.complaint_service import WorkflowError, assign_complaint, change_status


def test_admin_can_assign_complaint(app):
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        staff = User.query.filter_by(role="maintenance").first()
        c = db.session.get(Complaint, app.test_ids["c1"])
        assign_complaint(admin, c, staff.id)
        assert c.status == "Assigned"
        assert c.assignee_id == staff.id


def test_valid_status_transition(app):
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        staff = User.query.filter_by(role="maintenance").first()
        c = db.session.get(Complaint, app.test_ids["c1"])
        assign_complaint(admin, c, staff.id)
        change_status(staff, c, "In Progress")
        assert c.status == "In Progress"


def test_invalid_status_transition(app):
    with app.app_context():
        staff = User.query.filter_by(role="maintenance").first()
        c = db.session.get(Complaint, app.test_ids["c1"])
        with pytest.raises(WorkflowError):
            change_status(staff, c, "Resolved")
