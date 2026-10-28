from app.extensions import db
from app.models import Complaint, Feedback, User
from app.services.complaint_service import assign_complaint, change_status
from tests.conftest import login


def resolve(app):
    admin = User.query.filter_by(role="admin").first()
    staff = User.query.filter_by(role="maintenance").first()
    c = db.session.get(Complaint, app.test_ids["c1"])
    assign_complaint(admin, c, staff.id)
    change_status(staff, c, "In Progress")
    change_status(staff, c, "Resolved")
    return c


def test_feedback_submission(client, app):
    with app.app_context():
        c = resolve(app)
    login(client, "reporter@test.local")
    response = client.post(f"/reporter/complaints/{app.test_ids['c1']}/feedback", data={"rating": 5, "comment": "Fixed"}, follow_redirects=True)
    assert b"Feedback submitted" in response.data


def test_duplicate_feedback_prevention(client, app):
    with app.app_context():
        c = resolve(app)
        reporter = User.query.filter_by(email="reporter@test.local").first()
        db.session.add(Feedback(complaint_id=c.id, reporter_id=reporter.id, rating=4, comment="Ok"))
        db.session.commit()
    login(client, "reporter@test.local")
    assert client.get(f"/reporter/complaints/{app.test_ids['c1']}/feedback").status_code == 403
