# Actual model evaluation

All examples are synthetic templates with randomly assigned priority labels. Related templates occur across splits. Scores do not establish real-campus generalization or emergency reliability.

Rows: 1500 raw; 1306 usable; 1044 training; 262 test.

Highest training-only 3-fold stratified CV macro F1; ties use declared model order

Metrics are fractions (0-1).

## Category

Selected: Logistic Regression

| Model | Accuracy | Macro precision | Macro recall | Macro F1 | Emergency recall |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 1.0000 | 1.0000 | 1.0000 | 1.0000 | - |
| Multinomial Naive Bayes | 1.0000 | 1.0000 | 1.0000 | 1.0000 | - |
| Linear SVM | 1.0000 | 1.0000 | 1.0000 | 1.0000 | - |

## Priority

Selected: Multinomial Naive Bayes

| Model | Accuracy | Macro precision | Macro recall | Macro F1 | Emergency recall |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.4656 | 0.4988 | 0.5291 | 0.4931 | 1.0000 |
| Multinomial Naive Bayes | 0.4580 | 0.4950 | 0.5334 | 0.5014 | 1.0000 |
| Linear SVM | 0.4389 | 0.4526 | 0.4870 | 0.4323 | 0.9565 |
