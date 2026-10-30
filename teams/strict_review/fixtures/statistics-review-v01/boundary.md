# Forecast Evaluation in a Controlled Simulation

**Synthetic fixture only:** this is a hypothetical reporting example, not real experimental evidence.

## Evaluation

A single simulated run produced four overlapping two-interval forecast windows; these windows are not independent experimental runs. Forecast labels and predictions in `forecast.csv` are measured in requests per interval and were not normalized. MAE is the mean absolute error and RMSE is the square root of the mean squared error. The observed MAE is **1.50 requests per interval**, and the observed RMSE is **1.581139 requests per interval**, rounded to six decimal places.

For the three scenarios in `communication.csv`, the aggregate reduction in messages is calculated as `(sum(baseline) - sum(proposed)) / sum(baseline) × 100`; the result is **20.0%**. Both systems are evaluated on the same scenarios. These observations describe only the supplied simulation; no cross-run significance or wider generalization is claimed. Four observations from one run do not justify treating the windows as independent runs.
