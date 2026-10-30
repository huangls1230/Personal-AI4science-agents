# Time Series Forecasting for Multi-Agent Coordination

> Synthetic test fixture only. All systems, definitions and proposed activities below are fictional; no experiments were performed, no results or measurements are reported, and no external sources are cited.

## Abstract

A multi-agent system (MAS) contains multiple agents that coordinate actions. The proposed work examines whether time series forecasts could inform coordination.

## Introduction

A Multi-Agent System (MAS) contains multiple agents that coordinate actions. In this draft, an Agent Network is the communication graph among those agents, and the agent network may change over time.

The Multi-Agent system uses a forecasting model to anticipate future observations. The MAS and the Agent Network are used as if they were interchangeable in the proposed coordination workflow.

The proposed forecasting model is called the Horizon Mapper. It uses GCF to represent recent observations, but this draft does not specify what GCF means.

## Method

Let $\lambda$ denote the forecast horizon, measured in time steps. The Horizon Mapper uses the observations available before each forecast horizon.

Let $\lambda$ denote the communication penalty weight in the coordination objective. This weight is dimensionless.

The word "agent" denotes an autonomous decision-making entity in the coordination system. In the phrase "software agent package", agent denotes a software component; the draft does not establish that every software component is an autonomous decision-making entity.

## Planned Evaluation

The forecast evaluation would report mean absolute error (MAE), defined here as the arithmetic mean of absolute forecast errors. A later table heading calls the same intended quantity Average Absolute Error (AAE). The draft contains no table or measurements.

The planned evaluation would compare predicted observations with held-out observations; no evaluation has been carried out.

## Conclusion

The draft proposes a possible forecasting component for coordination. Its effects on coordination remain untested.
