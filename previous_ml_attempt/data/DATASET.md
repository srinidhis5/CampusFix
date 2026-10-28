# Dataset record

Local template generator src/generate_dataset.py, build_rows(total=1500), seed 42

**Every row is synthetic.** No real campus reports or human-verified priorities are included.

SHA-256: `a4684e61cdf16d9608a2a7affbb97ec4fc29bea749732265e1ace61aac28a791`

Raw rows: 1500. Removed 169 rows belonging to 80 conflicting normalized-text groups, then 25 duplicate rows.
Usable: 1306. Training: 1044. Test: 262.

Conflicting labels are removed as whole groups rather than arbitrarily keeping one label. Duplicate keys use lowercase alphanumeric text with collapsed whitespace.

| Target | Class | Raw | Train | Test |
|---|---|---:|---:|---:|
| category | Electrical | 290 | 185 | 47 |
| category | Furniture | 212 | 160 | 40 |
| category | Laboratory Equipment | 152 | 113 | 29 |
| category | Network | 250 | 171 | 43 |
| category | Other | 136 | 99 | 25 |
| category | Plumbing | 231 | 162 | 40 |
| category | Sanitation | 229 | 154 | 38 |
| priority | Emergency | 139 | 94 | 23 |
| priority | High | 420 | 290 | 73 |
| priority | Low | 366 | 255 | 64 |
| priority | Medium | 575 | 405 | 102 |

Template/location variants share wording; random priority labels introduce ambiguity. Benchmarks demonstrate training and integration, not real-world performance.

Generator priority_for uses keywords and seeded random weighted choices; priorities are not human-verified severity judgements
