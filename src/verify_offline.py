"""Verify saved results, group isolation, selection, and binary compatibility."""
import hashlib
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from src.offline_data import ROOT, TARGETS, audit_dataset
from src.train import MODEL_NAMES, SLUGS


def main():
    reports = ROOT / "reports/offline_evaluation"
    details = json.loads((reports / "experiment_details.json").read_text(encoding="utf-8"))
    summary = json.loads((reports / "dataset_summary.json").read_text(encoding="utf-8"))
    frame, _ = audit_dataset(ROOT / "data/complaints.csv")
    source = frame.set_index("row_id")
    manifest = pd.read_csv(reports / "split_manifest.csv")
    predictions = pd.read_csv(reports / "test_predictions.csv")
    folds = pd.read_csv(reports / "cv_folds.csv")
    train = manifest.loc[manifest.split.eq("train")]
    test = manifest.loc[manifest.split.eq("test")]
    assert set(train.group_id).isdisjoint(test.group_id)
    assert manifest.row_id.is_unique and predictions.row_id.is_unique
    assert predictions.row_id.tolist() == test.row_id.tolist()
    assert len(predictions) == summary["split"]["test_rows"]
    assert folds.groupby("group_id").validation_fold.nunique().eq(1).all()
    assert set(folds.row_id) == set(train.row_id)
    for fold in sorted(folds.validation_fold.unique()):
        valid_ids = folds.loc[folds.validation_fold.eq(fold), "row_id"]
        fit_ids = folds.loc[~folds.validation_fold.eq(fold), "row_id"]
        for target in TARGETS:
            assert set(source.loc[valid_ids, target]) == set(summary["labels"][target])
            assert set(source.loc[fit_ids, target]) == set(summary["labels"][target])
    for target in TARGETS:
        table = pd.read_csv(reports / f"{target}_model_comparison.csv").set_index("model")
        truth = predictions[f"true_{target}"]
        assert truth.tolist() == source.loc[predictions.row_id, target].tolist()
        for name, slug in zip(MODEL_NAMES, SLUGS):
            predicted = predictions[f"{target}_{slug}"]
            scores = {"accuracy": accuracy_score(truth, predicted),
                "macro_precision": precision_score(truth, predicted, labels=summary["labels"][target], average="macro", zero_division=0),
                "macro_recall": recall_score(truth, predicted, labels=summary["labels"][target], average="macro", zero_division=0),
                "macro_f1": f1_score(truth, predicted, labels=summary["labels"][target], average="macro", zero_division=0)}
            if target == "priority":
                scores["emergency_recall"] = recall_score(truth, predicted, labels=["Emergency"], average=None, zero_division=0)[0]
            for metric, value in scores.items():
                assert np.isclose(table.loc[name, metric], value), (target, name, metric)
        selected = details["targets"][target]["selected_model"]
        assert selected == max(MODEL_NAMES[:3], key=lambda name: details["targets"][target]["cv_results"][name]["mean_macro_f1"])
        model = joblib.load(ROOT / f"models/offline_evaluation/{target}_model.pkl")
        slug = SLUGS[MODEL_NAMES.index(selected)]
        assert list(model.predict(source.loc[predictions.row_id, "normalized_text"])) == predictions[f"{target}_{slug}"].tolist()
        vocabulary = set(model.named_steps["tfidf"].vocabulary_)
        train_words = set(" ".join(source.loc[train.row_id, "normalized_text"]).split())
        test_words = set(" ".join(source.loc[test.row_id, "normalized_text"]).split())
        assert not vocabulary.intersection(test_words - train_words), "TF-IDF includes a test-only unigram"
    for relative, expected in details["protected_file_hashes_before"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    print("PASS: saved metrics recomputed; all group partitions isolated; class-complete CV; selected binaries reproduce held-out predictions; no test-only vocabulary; protected website files unchanged.")


if __name__ == "__main__":
    main()
