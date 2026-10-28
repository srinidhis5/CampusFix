from __future__ import annotations

import csv
import random
from pathlib import Path


RANDOM_SEED = 42
OUTPUT_PATH = Path("data/complaints.csv")

CATEGORY_EXAMPLES = {
    "Electrical": [
        ("Tube light flickering in {place}", "The light keeps flickering during class and needs checking."),
        ("Power socket not working in {place}", "Students cannot use the socket near the desk."),
        ("Fan stopped working in {place}", "The ceiling fan is not rotating and the room is getting uncomfortable."),
        ("Sparking switch near {place}", "There are small sparks from the switch board and it feels unsafe."),
        ("Burning smell from wiring in {place}", "A burning smell is coming from the electrical panel."),
    ],
    "Plumbing": [
        ("Water leaking near {place}", "Water is dripping continuously and the floor is getting wet."),
        ("Tap broken in {place}", "The tap handle is loose and water is being wasted."),
        ("Toilet flush not working in {place}", "The flush is not working properly."),
        ("Pipe burst near {place}", "Water is flowing heavily from a broken pipe."),
        ("Drain blocked in {place}", "The drain is clogged and water is collecting."),
    ],
    "Network": [
        ("WiFi not available in {place}", "The signal drops often and students cannot access online resources."),
        ("LAN port down in {place}", "The wired internet connection is not working."),
        ("Slow internet in {place}", "The network is very slow during lab hours."),
        ("Router offline near {place}", "The router lights are off and there is no connection."),
        ("Network outage in {place}", "No systems are able to connect to the internet."),
    ],
    "Furniture": [
        ("Broken chair in {place}", "The chair leg is damaged and cannot be used safely."),
        ("Desk drawer stuck in {place}", "The drawer is jammed and needs repair."),
        ("Classroom bench damaged in {place}", "The bench surface is cracked."),
        ("Cupboard door loose in {place}", "The cupboard door hinge is coming off."),
        ("Window latch broken in {place}", "The latch does not close properly."),
    ],
    "Sanitation": [
        ("Trash overflowing near {place}", "The bin is full and waste is spilling outside."),
        ("Washroom needs cleaning in {place}", "The washroom has bad smell and requires cleaning."),
        ("Garbage not cleared near {place}", "Waste has not been collected since yesterday."),
        ("Water stagnation near {place}", "Dirty water is standing in the corridor."),
        ("Sanitation issue in {place}", "The area is unhygienic and needs attention."),
    ],
    "Laboratory Equipment": [
        ("Projector not working in {place}", "The projector does not turn on before lab session."),
        ("Microscope lens damaged in {place}", "The microscope lens is scratched and unclear."),
        ("Lab computer not starting in {place}", "The system does not boot."),
        ("Oscilloscope display issue in {place}", "The screen is flickering during experiments."),
        ("Equipment calibration needed in {place}", "The lab equipment is giving inconsistent readings."),
    ],
    "Other": [
        ("Notice board damaged near {place}", "The board is loose and needs fixing."),
        ("Lost key issue in {place}", "The room key is missing and access is blocked."),
        ("Door name plate missing in {place}", "The room label needs replacement."),
        ("General maintenance request for {place}", "The area needs inspection by the maintenance team."),
        ("Access issue near {place}", "The entry point is difficult to use and needs checking."),
    ],
}

PLACES = [
    "Block A Room 101",
    "Block B corridor",
    "CSE lab",
    "library first floor",
    "main auditorium",
    "hostel washroom",
    "seminar hall",
    "mechanical workshop",
    "admin office",
    "chemistry lab",
    "cafeteria entrance",
    "sports complex",
]

NOISE_PREFIXES = ["", "", "", "pls check", "urgent:", "Need help -", "issue:", "maintenance req:"]
NOISE_SUFFIXES = ["", "", "", " asap", " today", " please", "!!!", " - reported by class rep"]


def priority_for(title: str, description: str, category: str) -> str:
    text = f"{title} {description}".lower()
    if any(word in text for word in ("sparking", "burning", "burst", "outage", "unsafe")):
        return "Emergency" if random.random() < 0.72 else "High"
    if any(word in text for word in ("leaking", "blocked", "not working", "stopped", "offline", "damaged")):
        return random.choices(["High", "Medium", "Low"], weights=[0.42, 0.42, 0.16], k=1)[0]
    if category in ("Other", "Furniture"):
        return random.choices(["Low", "Medium", "High"], weights=[0.52, 0.38, 0.10], k=1)[0]
    return random.choices(["Low", "Medium", "High"], weights=[0.34, 0.48, 0.18], k=1)[0]


def varied_text(title: str, description: str) -> tuple[str, str]:
    prefix = random.choice(NOISE_PREFIXES)
    suffix = random.choice(NOISE_SUFFIXES)
    if prefix:
        title = f"{prefix} {title}"
    if random.random() < 0.12:
        title = title.upper()
    if random.random() < 0.16:
        description = description.replace("working", "wrkng").replace("connection", "conection")
    return title.strip(), f"{description}{suffix}".strip()


def build_rows(total: int = 1500) -> list[dict[str, str]]:
    random.seed(RANDOM_SEED)
    category_weights = {
        "Electrical": 0.19,
        "Plumbing": 0.17,
        "Network": 0.16,
        "Furniture": 0.14,
        "Sanitation": 0.14,
        "Laboratory Equipment": 0.11,
        "Other": 0.09,
    }
    categories = list(category_weights)
    weights = list(category_weights.values())
    rows = []
    seen = set()
    while len(rows) < total:
        category = random.choices(categories, weights=weights, k=1)[0]
        title_template, description = random.choice(CATEGORY_EXAMPLES[category])
        place = random.choice(PLACES)
        title = title_template.format(place=place)
        title, description = varied_text(title, description)
        priority = priority_for(title, description, category)
        complaint_text = f"{title} {description}".strip()
        key = (complaint_text.lower(), category, priority)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"complaint_text": complaint_text, "category": category, "priority": priority})
    return rows


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["complaint_text", "category", "priority"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
