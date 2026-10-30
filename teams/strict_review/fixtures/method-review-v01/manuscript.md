# Forecast-Aware Coordination for Distributed Multi-Agent Systems

## Abstract

Distributed agents can use demand forecasts to select communication partners before tasks arrive. We present Forecast-Aware Coordination (FAC), which predicts demand and updates a communication topology. In a simulated task-allocation setting, FAC achieves a mean task completion rate of 84% compared with 70% for a static scheduling rule. We argue that FAC scales to larger agent populations while reducing communication cost.

## Introduction

Our research question is whether forecasting future task demand improves task allocation and communication efficiency for distributed agents. Our objective is to design a coordination rule that uses a demand forecast to decide which agents communicate. We hypothesize that forecast-aware topology updates improve completion rates over coordination without forecasting, and that the design scales as the number of agents increases.

The contributions are a demand-forecasting module, a forecast-driven topology update rule, and a simulation-based evaluation. The proposed method assumes that the demand forecasts are accurate enough for choosing appropriate communication partners. Its effect when predictions are inaccurate is outside the reported analysis.

## Method

At each decision time, each agent creates a forecast for the next five steps using the shared forecasting module. A candidate communication edge is added when the predicted demand on that edge exceeds a fixed threshold of 0.5; all other candidate edges are omitted. Each agent then allocates tasks over the resulting edges. The exact aggregation rule used to turn agent-level predictions into edge-level demand is not specified.

The forecasting module is trained with a sliding window of 12 historical demand observations. The feature vector also includes the observed demand at the final step of the forecast horizon, y[t+5]. During evaluation, the recorded value y[t+5] is supplied to the module before the agents make their decision at time t. All decisions are timestamped at t.

The simulator uses a discrete clock and delivers messages sent at time t no earlier than t+1. All methods use the same simulator clock and the same task arrival sequences in each paired evaluation. This shared protocol makes completion-rate comparisons less sensitive to differences in task arrivals.

## Experimental Setup

We use one synthetic demand trace and 20 agents arranged in a fixed initial ring. The first 70% of timestamps are used for training and the remaining 30% for testing. The prediction horizon is five steps. Test points are evaluated in chronological order; y[t+5] from the recorded trace is provided as described above.

The only comparison is a static scheduler that assigns all tasks to one designated agent, does not redistribute tasks, and has no forecast input. FAC and this scheduler receive identical task sequences and clock settings. We do not compare against a load-balancing coordination policy without a forecast.

FAC rebuilds candidate communication edges at every decision step. We report only payload messages used for task allocation, excluding messages and computation used to collect forecasts and update topology. No topology maintenance timings or bytes are reported.

The experiment uses exactly 20 agents. The evaluation does not include other population sizes or network topologies. The forecast accuracy, the change in completion rate under forecast perturbations, and the relationship between prediction errors and allocation outcomes are not reported.

## Results and Conclusion

On the test portion of this single trace, FAC completes 84% of tasks and the static scheduler completes 70%. FAC uses 25% fewer task-allocation payload messages than the scheduler. These are synthetic example values for this fixture, not findings from real experiments. The evidence supports an improvement over the static scheduler in this configuration; we additionally claim that FAC scales to larger agent populations and reduces total communication cost.

## Materials

The fixture contains no code, raw trace, model configuration, or run logs. The topology update threshold and forecast window are specified above; other hyperparameters and implementation settings are not reported.
