# Held-out checks for the synthetic methodology review

This file is for the evaluator **after** the review has been produced. Do not provide it to the reviewer or treat its labels as scientific evidence. The only source for the review is the corresponding synthetic manuscript. Results are explicitly illustrative and are not real experimental findings.

## Main manuscript

- The explicitly supplied `y[t+5]` at decision time `t` is a verified future-information leak for that described evaluation, not proof of a separately implemented system's actual behavior.
- The fixed 20-agent setup does not substantiate a claim about scalability to larger populations. Phrase as unsupported by the supplied evaluation, not proof the method cannot scale.
- Single deliberately weak comparison limits the evidence for forecasting or coordination gains; matching arrivals and clock is a positive control but not sufficient to isolate the forecast mechanism.
- Payload-only reporting excludes topology update costs, limiting the total communication-cost claim. Do not equate absence of reported maintenance costs to zero cost.
- Accurate-enough predictions are explicitly assumed, while forecast quality and sensitivity are unreported. An implicit decision-time availability assumption is contradicted by the reported use of future demand. Separate explicit versus inferred assumptions.
- Undefined edge-level aggregation is insufficient information, not a confirmed algorithm error.
- Forecast-window length, shared simulator clock, and paired task arrivals are reported, concrete strengths; the paired protocol in particular is relevant to fair comparison.
- Suggestions for new comparison or perturbation experiments should target a claim, identify the evidence gap and alternative explanation, and offer a lower-cost option when applicable.
- No code or raw trace is available; do not assert reproduction or validation of the synthetic values.

## Boundary manuscript

- Do not call its predictor a verified future-information leak merely because the data are time series.
- Do not assert a missing no-forecast baseline, absent evaluation of error sensitivity, or unsupported universal scalability claim.
- The reported configuration and per-trace logs are not supplied to the reviewer; distinguish absent material and unverified descriptions from demonstrated implementation or findings.
- It is acceptable to report restricted availability and reproducibility gaps, but do not present such gaps as verified experimental defects.
