# Results: Rajshahi extreme-heat hindcast


Data: `openmeteo`, 1991-01-01 to 2025-12-31.

## Primary hindcast (275 forecasts, base rate 13%)

| Model | Brier ↓ | BSS vs A ↑ (95% CI) | P(better than A) | Log loss ↓ | AUC ↑ | Reliability ↓ | Resolution ↑ | Sharpness (SD of p) |
|---|---|---|---|---|---|---|---|---|
| A: climatology | 0.112 | reference | – | 0.382 | 0.704 | 0.0030 | 0.0028 | 0.028 |
| A2: climatology + trend | 0.115 | -0.025 (-0.107, +0.146) | 34% | 0.392 | 0.485 | 0.0034 | 0.0053 | 0.023 |
| B: anomaly logistic | 0.079 | +0.295 (+0.081, +0.433) | 99% | 0.270 | 0.928 | 0.0141 | 0.0495 | 0.158 |
| B2: anomaly + trend logistic | 0.082 | +0.267 (+0.133, +0.380) | 100% | 0.271 | 0.911 | 0.0077 | 0.0379 | 0.136 |

Over the 275 April–May issue dates in 2021–2025, the anomaly-adjusted model (B) scored a Brier score of 0.079 against 0.112 for climatology (A): a Brier skill score of +0.29 (95% block-bootstrap interval +0.08 to +0.43). That is a clear improvement on climatology (the 95% interval excludes zero).

## Brier score by test year

| Year | Event days (of issue dates) | A | A2 | B | B2 |
|---|---|---|---|---|---|
| 2021 | 0 | 0.033 | **0.017** | 0.052 | 0.046 |
| 2022 | 0 | 0.031 | **0.013** | 0.029 | 0.020 |
| 2023 | 12 | 0.163 | 0.180 | **0.118** | 0.128 |
| 2024 | 24 | 0.299 | 0.345 | **0.163** | 0.191 |
| 2025 | 0 | 0.034 | **0.019** | 0.034 | 0.026 |

## Extended hindcast 2001–2025 (1375 forecasts)

| Model | Brier ↓ | BSS vs A ↑ (95% CI) | P(better than A) | Log loss ↓ | AUC ↑ | Reliability ↓ | Resolution ↑ | Sharpness (SD of p) |
|---|---|---|---|---|---|---|---|---|
| A: climatology | 0.137 | reference | – | 0.448 | 0.466 | 0.0026 | 0.0001 | 0.034 |
| A2: climatology + trend | 0.139 | -0.015 (-0.046, +0.021) | 20% | 0.460 | 0.449 | 0.0045 | 0.0008 | 0.052 |
| B: anomaly logistic | 0.110 | +0.198 (+0.115, +0.272) | 100% | 0.358 | 0.800 | 0.0015 | 0.0249 | 0.167 |
| B2: anomaly + trend logistic | 0.113 | +0.174 (+0.090, +0.252) | 100% | 0.367 | 0.787 | 0.0018 | 0.0220 | 0.167 |

## Latency sweep (extended period, BSS vs A)

| Latency (days) | B2: anomaly + trend logistic | B: anomaly logistic |
|---|---|---|
| 1 | +0.174 | +0.198 |
| 2 | +0.095 | +0.116 |
| 3 | +0.049 | +0.065 |
| 5 | +0.018 | +0.030 |
| 7 | +0.005 | +0.016 |
| 10 | -0.006 | +0.000 |

Figures are in `results/figures/`.
