from pathlib import Path

import pandas as pd

from app.models import CATEGORIES, PRIORITIES


def validate_dataset(path: str = "data/complaints.csv") -> None:
    data_path = Path(path)
    frame = pd.read_csv(data_path)
    print("Missing values")
    print(frame.isna().sum())
    print(f"Duplicates: {frame.duplicated().sum()}")
    invalid_categories = sorted(set(frame["category"]) - set(CATEGORIES))
    invalid_priorities = sorted(set(frame["priority"]) - set(PRIORITIES))
    print(f"Invalid categories: {invalid_categories}")
    print(f"Invalid priorities: {invalid_priorities}")
    print("Category counts")
    print(frame["category"].value_counts())
    print("Priority counts")
    print(frame["priority"].value_counts())


if __name__ == "__main__":
    validate_dataset()
