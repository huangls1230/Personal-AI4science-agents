# Time Series Forecasting for Multi-Agent Coordination

**Synthetic fixture only:** all systems, observations, claims and results below were created for software testing and do not describe a real experiment.

## Experimental setup

We study whether a forecasting-based coordinator reduces communication and forecast error. We compare a baseline coordinator and a proposed forecasting coordinator on the same four simulated environments. Each environment has one random seed, and both methods are run in that environment. The experimental unit for an across-environment comparison is an environment/seed pair.

For the forecasting metric table, labels and predictions are exported in `forecast.csv`. Each row is one forecast window and uses the same measurement unit, requests per interval. All four windows come from one run with a forecast horizon of two intervals; adjacent windows overlap. We calculate MAE as the arithmetic mean of the absolute prediction errors and RMSE as the square root of the arithmetic mean of squared prediction errors. No scaling or normalization is applied.

The communication table records the total number of messages for the baseline and proposed systems on the same three simulated scenarios. Communication reduction is the percentage difference between the sum of baseline messages and the sum of proposed messages, divided by the sum of baseline messages. The raw measurements are in `communication.csv`.

## Results

The model achieves an MAE of **1.50 requests per interval** and an RMSE of **1.20 requests per interval** across the four forecast windows. Its communication overhead falls by **20.0%** relative to the baseline over the three scenarios.

For the four matched environment/seed pairs in `paired_runs.csv`, the paper treats the baseline and proposed samples as independent and uses an independent-samples test to assess their paired contrast. Lower task error is better. Our method consistently improves performance under all operating conditions.

We regard each of the four overlapping forecast windows from the single run as a separate independent experimental replication when describing variability across runs. This establishes robustness across many independent runs.

## Limitations

The simulation covers only the listed scenarios, and no implementation or raw data from any real system is included. These fixture results are not evidence of real-world performance.
