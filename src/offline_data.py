"""Dataset auditing and label-independent near-duplicate grouping for offline ML."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold

from src.preprocess import clean_text

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
TARGETS = ("category", "priority")


def project_labels():
    # Read constants without importing Flask or initializing the application.
    tree = ast.parse((ROOT / "app/models.py").read_text(encoding="utf-8"))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for name in node.targets:
                if isinstance(name, ast.Name) and name.id in ("CATEGORIES", "PRIORITIES"):
                    constants[name.id] = list(ast.literal_eval(node.value))
    return {"category": constants["CATEGORIES"], "priority": constants["PRIORITIES"]}


def generator_constants():
    """Inspect existing generator metadata only; never generate new records."""
    result = {}
    tree = ast.parse((ROOT / "src/generate_dataset.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for name in node.targets:
                if isinstance(name, ast.Name) and name.id in ("PLACES", "NOISE_PREFIXES", "NOISE_SUFFIXES"):
                    result[name.id] = ast.literal_eval(node.value)
    return result


def group_key(text, metadata):
    text = clean_text(text).replace("wrkng", "working").replace("conection", "connection")
    for place in sorted(metadata.get("PLACES", []), key=len, reverse=True):
        text = text.replace(clean_text(place), " location ")
    for prefix in sorted(set(metadata.get("NOISE_PREFIXES", [])), key=len, reverse=True):
        prefix = clean_text(prefix)
        if prefix and text.startswith(prefix + " "):
            text = text[len(prefix):].strip()
    for suffix in sorted(set(metadata.get("NOISE_SUFFIXES", [])), key=len, reverse=True):
        suffix = clean_text(suffix)
        if suffix and text.endswith(" " + suffix):
            text = text[:-len(suffix)].strip()
    return re.sub(r"\s+", " ", text).strip()


def near_duplicate_groups(texts):
    """Union canonical template variants and word-bigram Jaccard >= 0.80.

    Uses no fitted vocabulary, labels or learned transformation. Connected
    components keep transitive similarity links together. Metadata comes from
    the existing synthetic source, not from prediction targets.
    """
    metadata = generator_constants()
    keys = [group_key(text, metadata) for text in texts]
    unique = sorted(set(keys))
    parent = list(range(len(unique)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    shingles = [set(zip(key.split(), key.split()[1:])) for key in unique]
    for i, first in enumerate(shingles):
        for j in range(i):
            second = shingles[j]
            union = first | second
            similarity = len(first & second) / len(union) if union else float(unique[i] == unique[j])
            if similarity >= .80:
                parent[find(i)] = find(j)
    lookup = {key: f"G{find(i):04d}" for i, key in enumerate(unique)}
    return [lookup[key] for key in keys]


def counts(frame):
    return {target: frame[target].value_counts().sort_index().to_dict() for target in TARGETS}


def audit_dataset(path):
    if not path.is_file():
        raise ValueError("Provide a labelled CSV with complaint_text, category, priority; no dataset was generated.")
    frame = pd.read_csv(path, keep_default_na=False, dtype=str)
    required = ["complaint_text", *TARGETS]
    if not set(required).issubset(frame.columns):
        raise ValueError(f"Required columns: {required}")
    labels = project_labels()
    frame["row_id"] = [f"CSV-{n:06d}" for n in range(2, len(frame) + 2)]
    frame["normalized_text"] = frame.complaint_text.map(clean_text)
    missing_text = frame.normalized_text.eq("")
    missing_label = frame[list(TARGETS)].apply(lambda col: col.str.strip().eq("")).any(axis=1)
    invalid = pd.Series(False, index=frame.index)
    invalid_values = {}
    for target in TARGETS:
        invalid |= ~frame[target].isin(labels[target])
        invalid_values[target] = frame.loc[~frame[target].isin(labels[target]), target].value_counts().to_dict()
    valid = frame.loc[~(missing_text | missing_label | invalid)].copy()
    groups = valid.groupby("normalized_text")[list(TARGETS)].nunique()
    conflicts = set(groups.index[groups.gt(1).any(axis=1)])
    conflicting = valid.normalized_text.isin(conflicts)
    unambiguous = valid.loc[~conflicting]
    cleaned = unambiguous.drop_duplicates("normalized_text").copy().reset_index(drop=True)
    if cleaned.empty:
        raise ValueError("No unambiguous valid complaints remain after cleaning.")
    cleaned["group_id"] = near_duplicate_groups(cleaned.complaint_text)
    source_path = ROOT / "data/provenance.json"
    source = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() and path.resolve() == (ROOT / "data/complaints.csv").resolve() else {"source": "unknown"}
    summary = {"dataset_file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name, "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source": source, "labels": labels, "total_rows": len(frame), "raw_class_counts": counts(frame),
        "cleaning": {"missing_text_rows": int(missing_text.sum()), "missing_label_rows": int(missing_label.sum()),
            "invalid_label_rows": int(invalid.sum()), "invalid_label_values": invalid_values,
            "invalid_or_missing_rows_removed": int((missing_text | missing_label | invalid).sum()),
            "exact_raw_duplicate_text_rows": int(frame.complaint_text.duplicated().sum()),
            "normalized_duplicate_text_rows_before_cleaning": int(valid.normalized_text.duplicated().sum()),
            "conflicting_normalized_text_groups": len(conflicts), "conflicting_rows_removed": int(conflicting.sum()),
            "remaining_normalized_duplicate_rows_removed": len(unambiguous) - len(cleaned)},
        "usable_rows": len(cleaned), "cleaned_class_counts": counts(cleaned),
        "near_duplicate_groups": int(cleaned.group_id.nunique()),
        "near_duplicate_groups_with_multiple_labels": {t: int(cleaned.groupby("group_id")[t].nunique().gt(1).sum()) for t in TARGETS},
        "grouping_method": "Source-metadata location/boilerplate removal and documented typo normalization; connected components of canonical word-bigram Jaccard similarity >=0.80. Labels are never used for grouping.",
        "grouping_limitations": "Heuristic grouping cannot guarantee detection of every semantic paraphrase. Cleaning/grouping are label-audit and partition operations; model TF-IDF is fitted only on training folds.",
        "limitations": ["Existing dataset is entirely synthetic, generated from 35 scenario templates; no new examples were generated for this experiment.",
            "Priorities were assigned using keyword-conditioned random choices, not human-verified severity annotations.",
            "Conflicting exact inputs are removed as complete groups; this changes the evaluated population.",
            "Near-duplicate/template groups are held together in both holdout and CV; performance concerns unseen scenarios, not independent real-world complaints.",
            "Few independent templates per class make estimates unstable; sample counts overstate independent evidence.",
            "No real-campus generalization or emergency reliability claim is supported."]}
    return cleaned, summary


def split_dataset(frame, labels):
    """Choose a near-20% group split using only size/class support, never scores."""
    splitter = GroupShuffleSplit(n_splits=3000, test_size=.2, random_state=SEED)
    best = None
    for train_idx, test_idx in splitter.split(frame, groups=frame.group_id):
        train, test = frame.iloc[train_idx], frame.iloc[test_idx]
        adequate = all(set(train[t]) == set(labels[t]) and set(test[t]) == set(labels[t])
            and train.groupby(t).group_id.nunique().min() >= 3 for t in TARGETS)
        if not adequate:
            continue
        score = 5 * abs(len(test) / len(frame) - .2)
        for target in TARGETS:
            overall = frame[target].value_counts(normalize=True)
            heldout = test[target].value_counts(normalize=True).reindex(overall.index, fill_value=0)
            score += float((heldout - overall).abs().mean())
        if best is None or score < best[0]:
            best = (score, train_idx, test_idx)
    if best is None:
        raise ValueError("Insufficient independent groups for class-complete holdout and 3-fold CV. Provide more diverse labelled complaints; do not split duplicates across partitions.")
    _, train_idx, test_idx = best
    return train_idx, test_idx


def training_folds(train, labels):
    joint = train.category + "|" + train.priority
    # Fixed deterministic search on training labels/support only, never model performance.
    for offset in range(100):
        cv = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED + offset)
        folds = list(cv.split(train, joint, groups=train.group_id))
        if all(set(train.iloc[a][t]) == set(labels[t]) and set(train.iloc[b][t]) == set(labels[t])
               for a, b in folds for t in TARGETS):
            return folds, SEED + offset
    raise ValueError("Cannot create class-complete group CV folds. More independent complaint groups are needed.")
