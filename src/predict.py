from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    import joblib
except ImportError:  # pragma: no cover - optional until ML dependencies are installed
    joblib = None

from app.models import CATEGORIES, PRIORITIES
from src.preprocess import complaint_text

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_MODEL_PATH = ROOT / "models" / "category_model.pkl"
PRIORITY_MODEL_PATH = ROOT / "models" / "priority_model.pkl"

CATEGORY_KEYWORDS = {
    "Electrical": ("light", "fan", "power", "switch", "socket", "wire", "electric", "bulb", "sparking"),
    "Plumbing": ("tap", "pipe", "leak", "water", "toilet", "flush", "drain", "sink"),
    "Network": ("wifi", "wi fi", "internet", "network", "lan", "router", "signal", "server"),
    "Furniture": ("chair", "desk", "table", "bench", "cupboard", "door", "window"),
    "Sanitation": ("trash", "garbage", "dirty", "clean", "smell", "sanitation", "washroom", "waste"),
    "Laboratory Equipment": ("lab", "microscope", "oscilloscope", "projector", "equipment", "apparatus", "computer"),
}
EMERGENCY_TERMS = ("fire", "shock", "sparking", "flood", "burst", "hazard", "danger", "smoke", "urgent")
HIGH_TERMS = ("leak", "broken", "not working", "failed", "unsafe", "blocked", "overflow")
LOW_TERMS = ("minor", "loose", "slow", "flicker", "request", "replace")


def confidence_label(confidence: float) -> str:
    if confidence >= 80:
        return "High confidence"
    if confidence >= 60:
        return "Please verify"
    return "Low confidence, select manually"


@lru_cache(maxsize=2)
def _load_model(path: Path) -> Any | None:
    if joblib is None or not path.exists():
        return None
    return joblib.load(path)


def _predict_with_model(path: Path, text: str) -> tuple[str, float] | None:
    model = _load_model(path)
    if model is None or not hasattr(model, "predict_proba"):
        return None
    probabilities = model.predict_proba([text])[0]
    index = int(probabilities.argmax())
    label = str(model.classes_[index])
    return label, round(float(probabilities[index]) * 100, 2)


def _keyword_category(text: str) -> tuple[str | None, float]:
    scores = {category: sum(1 for keyword in keywords if keyword in text) for category, keywords in CATEGORY_KEYWORDS.items()}
    category, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        return None, 45.0
    return category, min(92.0, 58.0 + score * 12.0)


def _keyword_priority(text: str) -> tuple[str | None, float]:
    if any(term in text for term in EMERGENCY_TERMS):
        return "Emergency", 88.0
    if any(term in text for term in HIGH_TERMS):
        return "High", 76.0
    if any(term in text for term in LOW_TERMS):
        return "Low", 66.0
    return "Medium", 58.0


def predict_complaint(title: str | None, description: str | None) -> dict[str, Any]:
    text = complaint_text(title, description)
    model_category = _predict_with_model(CATEGORY_MODEL_PATH, text)
    model_priority = _predict_with_model(PRIORITY_MODEL_PATH, text)
    category, category_confidence = model_category or _keyword_category(text)
    priority, priority_confidence = model_priority or _keyword_priority(text)

    if category not in CATEGORIES:
        category = None
    if priority not in PRIORITIES:
        priority = None

    return {
        "category": category,
        "category_confidence": category_confidence,
        "category_confidence_label": confidence_label(category_confidence),
        "priority": priority,
        "priority_confidence": priority_confidence,
        "priority_confidence_label": confidence_label(priority_confidence),
        "message": "AI suggestion. Please check before submitting.",
        "low_confidence": category_confidence < 60 or priority_confidence < 60,
    }
