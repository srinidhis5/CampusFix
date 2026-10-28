from app.extensions import db
from app.models import Complaint, PredictionLog
from src.predict import predict_complaint
from tests.conftest import login


def test_predict_complaint_returns_confidence_labels():
    result = predict_complaint("Sparking switch", "There is smoke near the lab power socket")
    assert result["category"] == "Electrical"
    assert result["priority"] == "Emergency"
    assert "confidence" in result["priority_confidence_label"].lower()


def test_predict_route_requires_enough_text(client):
    login(client, "reporter@test.local")
    response = client.post("/predict", json={"title": "short", "description": ""})
    assert response.status_code == 400


def test_prediction_log_created_on_submission(client, app):
    login(client, "reporter@test.local")
    response = client.post(
        "/reporter/complaints/new",
        data={
            "title": "WiFi down in lab",
            "description": "No signal in the computer lab",
            "category": "Network",
            "building": "C",
            "room_location": "303",
            "priority": "High",
            "predicted_category": "Network",
            "predicted_priority": "Medium",
            "category_confidence": "82.5",
            "priority_confidence": "66.0",
        },
        follow_redirects=True,
    )
    assert b"Complaint submitted successfully" in response.data
    with app.app_context():
        complaint = Complaint.query.filter_by(title="WiFi down in lab").one()
        log = PredictionLog.query.filter_by(complaint_id=complaint.id).one()
        assert log.predicted_category == "Network"
        assert log.final_priority == "High"
        assert log.was_corrected is True


def test_admin_ml_insights_page(client):
    login(client, "admin@test.local")
    response = client.get("/admin/ml-insights")
    assert response.status_code == 200
    assert b"ML insights" in response.data
