"""Offline-only experiments: python -m src.train. Never loads the web app."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from src.offline_data import ROOT, SEED, TARGETS, audit_dataset, counts, split_dataset, training_folds

REPORTS = ROOT / "reports/offline_evaluation"
MODELS = ROOT / "models/offline_evaluation"
MODEL_NAMES = ("Logistic Regression", "Multinomial Naive Bayes", "Linear SVM", "Majority baseline")
SLUGS = ("logistic_regression", "multinomial_nb", "linear_svm", "majority_baseline")


def candidates():
    def pipe(classifier):
        # No stop words: preserve not/no/never; transformations fitted per fold.
        return Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True,
            stop_words=None, lowercase=False)), ("classifier", classifier)])
    return {
        "Logistic Regression": pipe(LogisticRegression(C=1.0, solver="lbfgs", max_iter=2000, random_state=SEED)),
        "Multinomial Naive Bayes": pipe(MultinomialNB(alpha=1.0)),
        "Linear SVM": pipe(LinearSVC(C=1.0, dual="auto", random_state=SEED, max_iter=5000)),
        "Majority baseline": DummyClassifier(strategy="most_frequent"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/complaints.csv")
    args = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(REPORTS / "training_run.log", mode="w", encoding="utf-8"), logging.StreamHandler(sys.stdout)], force=True)
    log = logging.getLogger("offline")
    # Guard existing website files against accidental changes by the offline run.
    protected = [ROOT / "models/metrics.json", ROOT / "src/predict.py", ROOT / "src/preprocess.py"]
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    try:
        log.info("Starting offline experiment; random seed=%d; no database or website imports", SEED)
        frame, summary = audit_dataset(args.data.resolve())
        log.info("Dataset source: %s", summary["source"])
        log.info("Raw=%d; usable=%d; independent near-duplicate groups=%d", summary["total_rows"], len(frame), summary["near_duplicate_groups"])
        log.info("Cleaning audit: %s", summary["cleaning"])
        log.info("Raw class counts: %s", summary["raw_class_counts"])
        (REPORTS / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        train_idx, test_idx = split_dataset(frame, summary["labels"])
        train, test = frame.iloc[train_idx].reset_index(drop=True), frame.iloc[test_idx].reset_index(drop=True)
        folds, fold_seed = training_folds(train, summary["labels"])
        assert not set(train.group_id) & set(test.group_id)
        summary["split"] = {"seed": SEED, "train_rows": len(train), "test_rows": len(test),
            "test_fraction": len(test) / len(frame), "train_groups": train.group_id.nunique(), "test_groups": test.group_id.nunique(),
            "train_class_counts": counts(train), "test_class_counts": counts(test),
            "train_class_group_counts": {t: train.groupby(t).group_id.nunique().to_dict() for t in TARGETS},
            "test_class_group_counts": {t: test.groupby(t).group_id.nunique().to_dict() for t in TARGETS},
            "method": "3000 seed-42 GroupShuffleSplit candidates; minimize 5*test-fraction deviation + mean marginal class-distribution deviations. Require every class in both partitions and >=3 training groups per class. No model scores used.",
            "train_test_group_overlap": 0}
        summary["class_coverage"] = "All supported classes are present in training, test and every CV training/validation fold. Template-group counts, not row counts, limit evidence."
        (REPORTS / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        split_rows = pd.concat([train.assign(split="train"), test.assign(split="test")])
        split_rows[["row_id", "group_id", "category", "priority", "split"]].to_csv(REPORTS / "split_manifest.csv", index=False)
        fold_rows = []
        for n, (a, b) in enumerate(folds):
            assert not set(train.iloc[a].group_id) & set(train.iloc[b].group_id)
            for i in b:
                fold_rows.append({"row_id": train.iloc[i].row_id, "group_id": train.iloc[i].group_id, "validation_fold": n + 1})
        pd.DataFrame(fold_rows).to_csv(REPORTS / "cv_folds.csv", index=False)
        log.info("Split: %d training rows/%d groups; %d test rows/%d groups", len(train), train.group_id.nunique(), len(test), test.group_id.nunique())
        predictions = test[["row_id", "group_id"]].copy()
        for t in TARGETS:
            predictions[f"true_{t}"] = test[t]
        details = {"random_seed": SEED, "cv_seed": fold_seed, "cv_folds": 3,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "package_versions": {p: importlib.metadata.version(p) for p in ("scikit-learn", "numpy", "scipy", "pandas", "matplotlib", "joblib")},
            "python_version": platform.python_version(), "dataset_sha256": summary["dataset_sha256"],
            "selection_method": "Independently choose the highest mean training-side 3-fold grouped CV macro F1 among the three trained classifiers. Baseline is reported, excluded from selection. Ties use declared model order. No tuning or test-based selection.",
            "cv_method": "Same training-side class-complete StratifiedGroupKFold partitions for both targets and every model; seed search 42..141 uses class coverage only.",
            "probability_calibration": "None: offline SVM uses decision/predict only; no probability output required.",
            "preprocessing": "Existing clean_text: lowercase, replace non-alphanumeric with spaces, collapse whitespace. Negation words retained. TF-IDF stop_words=None, fitted only inside each training fold and then on full training partition.",
            "website_metrics_schema_observed": list(json.loads((ROOT / "models/metrics.json").read_text(encoding="utf-8")).keys()),
            "protected_file_hashes_before": before, "targets": {}}
        for target in TARGETS:
            scores = {}
            fitted = candidates()
            for name, model in fitted.items():
                fold_scores = []
                for a, b in folds:
                    estimator = clone(model)
                    estimator.fit(train.iloc[a].normalized_text, train.iloc[a][target])
                    predicted = estimator.predict(train.iloc[b].normalized_text)
                    fold_scores.append(float(f1_score(train.iloc[b][target], predicted,
                        labels=summary["labels"][target], average="macro", zero_division=0)))
                scores[name] = {"fold_macro_f1": fold_scores, "mean_macro_f1": float(np.mean(fold_scores)), "std_macro_f1": float(np.std(fold_scores))}
                log.info("%s | %s | CV macro F1 %.6f +/- %.6f", target, name, scores[name]["mean_macro_f1"], scores[name]["std_macro_f1"])
            selected = max(MODEL_NAMES[:3], key=lambda name: scores[name]["mean_macro_f1"])
            details["targets"][target] = {"selected_model": selected, "cv_results": scores,
                "parameters": {name: {key: repr(value) for key, value in model.get_params(deep=True).items()} for name, model in fitted.items()}}
            log.info("%s selected using CV: %s (test data not used)", target, selected)
            for name, slug in zip(MODEL_NAMES, SLUGS):
                model = fitted[name]
                model.fit(train.normalized_text, train[target])
                predictions[f"{target}_{slug}"] = model.predict(test.normalized_text)
                if name == selected:
                    joblib.dump(model, MODELS / f"{target}_model.pkl")
        predictions.to_csv(REPORTS / "test_predictions.csv", index=False)
        details["test_predictions_sha256"] = hashlib.sha256((REPORTS / "test_predictions.csv").read_bytes()).hexdigest()
        details["protected_file_hashes_after"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        assert details["protected_file_hashes_after"] == before, "Protected website file modified"
        (REPORTS / "experiment_details.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
        from src.evaluate import evaluate, package_results
        evaluate(REPORTS)
        log.info("SUCCESS: six classifier evaluations plus two majority baselines completed. Protected website files unchanged.")
        for handler in logging.getLogger().handlers:
            handler.flush()
        package_results(REPORTS)
    except Exception:
        log.exception("Offline experiment FAILED; no successful training claim should be made")
        raise


if __name__ == "__main__":
    main()
