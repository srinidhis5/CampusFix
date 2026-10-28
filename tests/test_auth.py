from app.models import User
from app.extensions import db
from tests.conftest import login


def test_reporter_registration(client, app):
    response = client.post("/register", data={"full_name": "New Student", "email": "new@test.local", "password": "Password@123", "confirm_password": "Password@123", "department": "CSE"}, follow_redirects=True)
    assert b"Registration successful" in response.data
    with app.app_context():
        assert User.query.filter_by(email="new@test.local").first()


def test_valid_login(client):
    response = login(client, "reporter@test.local")
    assert b"Reporter dashboard" in response.data


def test_invalid_login(client):
    response = client.post("/login", data={"email": "reporter@test.local", "password": "bad"}, follow_redirects=True)
    assert b"Invalid email or password" in response.data


def test_deactivated_user_login(client):
    response = login(client, "inactive@test.local")
    assert b"deactivated" in response.data
