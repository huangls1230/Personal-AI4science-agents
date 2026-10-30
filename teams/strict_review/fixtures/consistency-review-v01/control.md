# Controlled Synthetic Reporting Example

**Synthetic test fixture:** this document contains invented values solely for testing.

## Scope and results

In a single 20-agent ring simulation, the baseline sent 100 messages and FAC sent 82 messages. The baseline-relative reduction is 18%. FAC completed 84% of submitted tasks; the baseline completed 70%. These are observations for the stated simulation, with no claim about statistical significance or other operating conditions.

| Coordinator | Messages | Completion rate |
| --- | ---: | ---: |
| Baseline | 100 | 70% |
| FAC | 82 | 84% |

The latency for the same 20-agent ring is 6.7 ms to one decimal place, using the more precise value of 6.67 ms. A separate 40-agent star observation is 10.0 ms; these different conditions are not directly compared.
