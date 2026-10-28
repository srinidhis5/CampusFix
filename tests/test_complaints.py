from datetime import datetime, timedelta

from app.extensions import db
from app.models import AuditLog, Complaint
from tests.conftest import login


def test_complaint_submission(client):
    login(client, "reporter@test.local")
    response = client.post("/reporter/complaints/new", data={"title": "WiFi issue", "description": "No signal", "category": "Network", "building": "C", "room_location": "303", "priority": "Low"}, follow_redirects=True)
    assert b"Complaint submitted successfully" in response.data


def test_missing_complaint_field(client):
    login(client, "reporter@test.local")
    response = client.post("/reporter/complaints/new", data={"title": "", "description": "No signal", "category": "Network", "building": "C", "room_location": "303", "priority": "Low"})
    assert b"This field is required" in response.data


def test_duplicate_complaint_warning(client):
    login(client, "reporter@test.local")
    response = client.post("/reporter/complaints/new", data={"title": "Another light", "description": "Same place", "category": "Electrical", "building": "A", "room_location": "101", "priority": "Low"})
    assert b"Possible duplicate" in response.data


def test_dashboard_counts(client):
    login(client, "reporter@test.local")
    response = client.get("/reporter/dashboard")
    assert b"Total" in response.data and b"Submitted" in response.data


def test_overdue_complaint_calculation(app):
    with app.app_context():
        c = db.session.get(Complaint, app.test_ids["c1"])
        c.due_at = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()
        assert c.is_overdue


def test_audit_log_creation(app):
    with app.app_context():
        assert AuditLog.query.filter_by(action="create").count() >= 1
