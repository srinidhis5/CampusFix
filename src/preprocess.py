import re


def clean_text(value: str | None) -> str:
    """Normalize complaint text without dropping meaning-bearing words."""
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def complaint_text(title: str | None, description: str | None) -> str:
    """Combine title and description for the ML classifiers."""
    return clean_text(f"{title or ''} {description or ''}")
