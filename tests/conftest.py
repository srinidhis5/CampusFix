import pytest

from app import create_app
from app.extensions import db
from app.models import User
from app.services.complaint_service import create_complaint
from config import TestingConfig


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(full_name="Admin", email="admin@test.local", role="admin", department="Admin")
        admin.set_password("Password@123")
        reporter = User(full_name="Reporter", email="reporter@test.local", role="reporter", department="CSE")
        reporter.set_password("Password@123")
        other = User(full_name="Other", email="other@test.local", role="reporter", department="ECE")
        other.set_password("Password@123")
        inactive = User(full_name="Inactive", email="inactive@test.local", role="reporter", department="CSE", is_active=False)
        inactive.set_password("Password@123")
        staff = User(full_name="Staff", email="staff@test.local", role="maintenance", department="Electrical")
        staff.set_password("Password@123")
        staff2 = User(full_name="Staff Two", email="staff2@test.local", role="maintenance", department="Plumbing")
        staff2.set_password("Password@123")
        db.session.add_all([admin, reporter, other, inactive, staff, staff2])
        db.session.commit()
        c1 = create_complaint(reporter, {"title": "Light broken", "description": "Tube light not working", "category": "Electrical", "building": "A", "room_location": "101", "priority": "High"})
        c2 = create_complaint(other, {"title": "Pipe leak", "description": "Leak", "category": "Plumbing", "building": "B", "room_location": "202", "priority": "Medium"})
        app.test_ids = {"c1": c1.id, "c2": c2.id, "admin": admin.id, "reporter": reporter.id, "staff": staff.id, "staff2": staff2.id}
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password="Password@123"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)
