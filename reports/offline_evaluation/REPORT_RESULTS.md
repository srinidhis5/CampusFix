# CampusFix offline ML experimental results

**Synthetic-data experiment.** All scores below were calculated from saved held-out predictions.

Dataset: 1500 raw rows; 1306 usable; 1040 training; 266 test.
Independent groups: 28 training, 7 test.

Independently choose the highest mean training-side 3-fold grouped CV macro F1 among the three trained classifiers. Baseline is reported, excluded from selection. Ties use declared model order. No tuning or test-based selection.

Scores are fractions (0-1); macro averages include every supported class with zero_division=0.

## Category

Selected model: **Linear SVM**.

| Model | Accuracy | Macro precision | Macro recall | Macro F1 | Emergency recall |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.4737 | 0.4131 | 0.4539 | 0.3774 | - |
| Multinomial Naive Bayes | 0.4286 | 0.2786 | 0.4048 | 0.3207 | - |
| Linear SVM | 0.5414 | 0.4048 | 0.5309 | 0.4345 | - |
| Majority baseline | 0.1917 | 0.0274 | 0.1429 | 0.0460 | - |

## Priority

Selected model: **Linear SVM**.

| Model | Accuracy | Macro precision | Macro recall | Macro F1 | Emergency recall |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.3609 | 0.2504 | 0.2581 | 0.2022 | 0.0000 |
| Multinomial Naive Bayes | 0.3910 | 0.2123 | 0.2754 | 0.2044 | 0.0000 |
| Linear SVM | 0.3496 | 0.2547 | 0.2560 | 0.2196 | 0.0000 |
| Majority baseline | 0.3722 | 0.0930 | 0.2500 | 0.1356 | 0.0000 |

## Data audit and limitations

- Existing dataset is entirely synthetic, generated from 35 scenario templates; no new examples were generated for this experiment.
- Priorities were assigned using keyword-conditioned random choices, not human-verified severity annotations.
- Conflicting exact inputs are removed as complete groups; this changes the evaluated population.
- Near-duplicate/template groups are held together in both holdout and CV; performance concerns unseen scenarios, not independent real-world complaints.
- Few independent templates per class make estimates unstable; sample counts overstate independent evidence.
- No real-campus generalization or emergency reliability claim is supported.

Heuristic grouping cannot guarantee detection of every semantic paraphrase. Cleaning/grouping are label-audit and partition operations; model TF-IDF is fitted only on training folds.

See dataset_summary.json for cleaning counts, all class counts, and independent group counts.

## Reproduce from project root (PowerShell)

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-offline.txt
.\venv\Scripts\python.exe -m src.train
.\venv\Scripts\python.exe -m src.evaluate
```

The evaluation command recomputes metrics from the frozen predictions; it does not refit models.
Selected binaries are in models/offline_evaluation/. Results stay in reports/offline_evaluation/ so the website does not discover the figures or load the offline models.

## Files for report writing

Upload CampusFix_ML_Report_Results.zip. It contains this summary, both comparison tables, matrices, chart, classification reports, pseudonymous per-row predictions, audit, experiment configuration, run log, scripts and dependency pins.
The archive intentionally excludes complaint text, source CSV, database, credentials, web screenshots and model binaries. To retrain, use the original project's data/complaints.csv whose checksum appears in dataset_summary.json.
