from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import csrf
from src.predict import predict_complaint

ml_bp = Blueprint("ml", __name__)


@ml_bp.route("/predict", methods=["POST"])
@login_required
@csrf.exempt
def predict():
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "")
    description = payload.get("description", "")
    if len(f"{title} {description}".strip()) < 15:
        return jsonify({"error": "Enter at least 15 characters for a suggestion."}), 400
    return jsonify(predict_complaint(title, description))
