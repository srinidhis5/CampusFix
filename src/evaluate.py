"""Recompute offline metrics from frozen held-out predictions, without retraining."""
from __future__ import annotations

import hashlib
import json
import logging
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay, precision_recall_fscore_support, recall_score

from src.offline_data import ROOT, TARGETS

MODEL_NAMES = ("Logistic Regression", "Multinomial Naive Bayes", "Linear SVM", "Majority baseline")
SLUGS = ("logistic_regression", "multinomial_nb", "linear_svm", "majority_baseline")


def evaluate(reports):
    summary = json.loads((reports / "dataset_summary.json").read_text(encoding="utf-8"))
    details = json.loads((reports / "experiment_details.json").read_text(encoding="utf-8"))
    if hashlib.sha256((reports / "test_predictions.csv").read_bytes()).hexdigest() != details["test_predictions_sha256"]:
        raise ValueError("Held-out prediction file changed since training")
    predictions = pd.read_csv(reports / "test_predictions.csv")
    split = pd.read_csv(reports / "split_manifest.csv")
    heldout = split.loc[split.split.eq("test")]
    if list(predictions.row_id) != list(heldout.row_id):
        raise ValueError("Prediction row identifiers do not match the frozen test partition")
    if set(heldout.group_id) & set(split.loc[split.split.eq("train"), "group_id"]):
        raise ValueError("Near-duplicate group leakage detected")
    for target in TARGETS:
        if predictions[f"true_{target}"].tolist() != heldout[target].tolist():
            raise ValueError(f"True {target} labels differ from frozen split")
    output = {"source": "Offline evaluation only; website metrics unchanged", "targets": {}}
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)
    report = ["# CampusFix offline ML experimental results", "", "**Synthetic-data experiment.** All scores below were calculated from saved held-out predictions.", "",
        f"Dataset: {summary['total_rows']} raw rows; {summary['usable_rows']} usable; {summary['split']['train_rows']} training; {summary['split']['test_rows']} test.",
        f"Independent groups: {summary['split']['train_groups']} training, {summary['split']['test_groups']} test.", "",
        details["selection_method"], "", "Scores are fractions (0-1); macro averages include every supported class with zero_division=0."]
    for target, ax in zip(TARGETS, axes):
        selected = details["targets"][target]["selected_model"]
        truth = predictions[f"true_{target}"]
        labels = summary["labels"][target]
        rows = []
        report.extend(["", f"## {target.title()}", "", f"Selected model: **{selected}**.", "",
            "| Model | Accuracy | Macro precision | Macro recall | Macro F1 | Emergency recall |", "|---|---:|---:|---:|---:|---:|"])
        for name, slug in zip(MODEL_NAMES, SLUGS):
            predicted = predictions[f"{target}_{slug}"]
            precision, recall, f1, _ = precision_recall_fscore_support(truth, predicted, labels=labels, average="macro", zero_division=0)
            cv = details["targets"][target]["cv_results"][name]
            row = {"model": name, "accuracy": float(accuracy_score(truth, predicted)),
                "macro_precision": float(precision), "macro_recall": float(recall), "macro_f1": float(f1),
                "cv_macro_f1_mean": cv["mean_macro_f1"], "cv_macro_f1_std": cv["std_macro_f1"], "selected": name == selected}
            emergency = "-"
            if target == "priority":
                row["emergency_recall"] = float(recall_score(truth, predicted, labels=["Emergency"], average=None, zero_division=0)[0])
                emergency = f"{row['emergency_recall']:.4f}"
            rows.append(row)
            report.append(f"| {name} | {row['accuracy']:.4f} | {row['macro_precision']:.4f} | {row['macro_recall']:.4f} | {row['macro_f1']:.4f} | {emergency} |")
            if name == selected:
                selected_report = classification_report(truth, predicted, labels=labels, output_dict=True, zero_division=0)
                (reports / f"{target}_classification_report.json").write_text(json.dumps(selected_report, indent=2), encoding="utf-8")
                (reports / f"{target}_classification_report.txt").write_text(classification_report(truth, predicted, labels=labels, digits=4, zero_division=0), encoding="utf-8")
                matrix = confusion_matrix(truth, predicted, labels=labels)
                pd.DataFrame(matrix, index=labels, columns=labels).rename_axis("True label").to_csv(reports / f"{target}_confusion_matrix.csv")
                cmfig, cmax = plt.subplots(figsize=(12, 9), constrained_layout=True)
                ConfusionMatrixDisplay(matrix, display_labels=labels).plot(ax=cmax, cmap="Blues", colorbar=False, xticks_rotation=35, values_format="d")
                cmax.set_xlabel("Predicted label")
                cmax.set_ylabel("True label")
                cmax.set_title(f"{target.title()}: {name}\nSynthetic complaints; held-out template groups; n={len(truth)}")
                cmfig.savefig(reports / f"{target}_confusion_matrix.png", dpi=180)
                plt.close(cmfig)
                output["targets"][target] = dict(row, selected_model=name)
        pd.DataFrame(rows).to_csv(reports / f"{target}_model_comparison.csv", index=False)
        output["targets"][target]["comparisons"] = rows
        for i, metric in enumerate(("accuracy", "macro_precision", "macro_recall", "macro_f1")):
            ax.bar(np.arange(4) + (i - 1.5) * .19, [r[metric] for r in rows], width=.19, label=metric.replace("_", " ").title())
        ax.set(xticks=np.arange(4), xticklabels=["Logistic\nRegression", "Multinomial\nNaive Bayes", "Linear\nSVM", "Majority\nbaseline"], ylim=(0, 1.05), title=target.title(), ylabel="Held-out score (0-1)")
        ax.legend(fontsize=8)
    fig.suptitle(f"CampusFix: synthetic complaints, grouped test set (n={len(predictions)})\nModel selection uses training-only grouped cross-validation")
    fig.savefig(reports / "model_comparison.png", dpi=180)
    plt.close(fig)
    (reports / "offline_metrics.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    report.extend(["", "## Data audit and limitations", ""] + [f"- {item}" for item in summary["limitations"]])
    report.extend(["", summary["grouping_limitations"], "", "See dataset_summary.json for cleaning counts, all class counts, and independent group counts.",
        "", "## Reproduce from project root (PowerShell)", "", "```powershell", ".\\venv\\Scripts\\python.exe -m pip install -r requirements-offline.txt", ".\\venv\\Scripts\\python.exe -m src.train", ".\\venv\\Scripts\\python.exe -m src.evaluate", "```", "",
        "The evaluation command recomputes metrics from the frozen predictions; it does not refit models.",
        "Selected binaries are in models/offline_evaluation/. Results stay in reports/offline_evaluation/ so the website does not discover the figures or load the offline models.",
        "", "## Files for report writing", "", "Upload CampusFix_ML_Report_Results.zip. It contains this summary, both comparison tables, matrices, chart, classification reports, pseudonymous per-row predictions, audit, experiment configuration, run log, scripts and dependency pins.",
        "The archive intentionally excludes complaint text, source CSV, database, credentials, web screenshots and model binaries. To retrain, use the original project's data/complaints.csv whose checksum appears in dataset_summary.json."])
    (reports / "REPORT_RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    logging.getLogger("offline").info("Held-out metrics and figures generated from %d identical complaint rows for all models/tasks", len(predictions))
    return output


def package_results(reports):
    # Explicit allowlist: no broad directory archiving or raw complaint text.
    names = ["dataset_summary.json", "category_model_comparison.csv", "priority_model_comparison.csv",
        "category_confusion_matrix.png", "priority_confusion_matrix.png", "category_confusion_matrix.csv", "priority_confusion_matrix.csv",
        "model_comparison.png", "category_classification_report.json", "priority_classification_report.json",
        "category_classification_report.txt", "priority_classification_report.txt", "test_predictions.csv",
        "split_manifest.csv", "cv_folds.csv", "experiment_details.json", "training_run.log", "offline_metrics.json", "REPORT_RESULTS.md"]
    scripts = ["src/train.py", "src/evaluate.py", "src/offline_data.py", "src/preprocess.py", "src/verify_offline.py", "requirements-offline.txt", "data/provenance.json"]
    destination = ROOT / "CampusFix_ML_Report_Results.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.write(reports / name, f"reports/offline_evaluation/{name}")
        for relative in scripts:
            archive.write(ROOT / relative, relative)
    print(f"Report bundle: {destination}")


def main():
    reports = ROOT / "reports/offline_evaluation"
    evaluate(reports)
    package_results(reports)


if __name__ == "__main__":
    main()
