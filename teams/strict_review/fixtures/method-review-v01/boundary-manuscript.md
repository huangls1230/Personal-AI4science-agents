# A Bounded Evaluation of Forecast-Informed Task Allocation

## Research Question and Scope

Can a demand forecast available at decision time improve allocation over a non-forecast load-balancing policy in one simulator with 20 agents? Our claims are limited to this setting and the tested simulated demand traces; we do not claim general scalability or performance in deployed networks.

## Method

At time t, a linear forecasting model receives only demand observations at or before t and outputs an estimate for t+1. A fixed allocation rule uses this estimate to distribute tasks; the comparison uses the same rule and substitutes the current observation for the forecast. Both policies have the same message budget, simulator, agent roles, and initial topology. The model is fitted exclusively on the training period, using parameters selected on the validation period.

## Evaluation

For each of three synthetic demand traces, timestamps 1–500 are used for training, 501–700 for validation, and 701–1000 for testing. No future observation is supplied to the predictor at a decision time. Each method is evaluated on the same test arrivals for that trace. The reported completion rate is the fraction of arriving tasks finished before a deadline; communication cost counts both allocation and prediction-related messages.

To assess sensitivity, we additionally perturb forecasts by adding zero-mean noise at three fixed levels and report results for each level. The synthetic test specifies random seeds, coefficients and task-generation settings in its accompanying configuration; that configuration is not supplied in this fixture. There is no assertion that an independent reproduction has been conducted.

## Results

In these illustrative synthetic observations, the forecast-informed policy completes 78% of tasks versus 75% for the non-forecast policy on the stated test traces. Both completion and total message counts are reported for each trace in the corresponding experiment log, which is not included here. The finding is a limited comparison in the described simulator; this description does not establish statistical significance or performance under real deployment conditions.
