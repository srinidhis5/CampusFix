from app.extensions import db
from app.models import Complaint
from app.services.complaint_service import assign_complaint
from tests.conftest import login


def test_reporter_cannot_access_admin_pages(client):
    login(client, "reporter@test.local")
    assert client.get("/admin/dashboard").status_code == 403


def test_reporter_cannot_view_another_reporters_complaint(client, app):
    login(client, "reporter@test.local")
    assert client.get(f"/reporter/complaints/{app.test_ids['c2']}").status_code == 403


def test_maintenance_can_view_assigned_complaint(client, app):
    with app.app_context():
        admin = db.session.get(__import__("app.models").models.User, app.test_ids["admin"])
        c = db.session.get(Complaint, app.test_ids["c1"])
        assign_complaint(admin, c, app.test_ids["staff"])
    login(client, "staff@test.local")
    assert client.get(f"/maintenance/complaints/{app.test_ids['c1']}").status_code == 200


def test_maintenance_cannot_view_another_employee_complaint(client, app):
    with app.app_context():
        admin = db.session.get(__import__("app.models").models.User, app.test_ids["admin"])
        c = db.session.get(Complaint, app.test_ids["c1"])
        assign_complaint(admin, c, app.test_ids["staff2"])
    login(client, "staff@test.local")
    assert client.get(f"/maintenance/complaints/{app.test_ids['c1']}").status_code == 403
