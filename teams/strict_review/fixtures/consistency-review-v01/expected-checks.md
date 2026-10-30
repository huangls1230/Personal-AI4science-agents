# Evaluation checklist — read only after the blind review is frozen

This file is a test oracle, not manuscript evidence. All values are synthetic.

1. The same fixed-ring communication comparison has 100 baseline versus 82 FAC messages: the defined reduction is 18%; abstract 25% and conclusion 22% disagree with that table and one another. Any simple calculation is `(100-82)/100*100`.
2. Visually inspect figure 1: its latency trend descends, despite the sentence saying it rises. Confirm using chart axes and visible points; CSV alone is not visual inspection.
3. Visually inspect figure 2: its bars and the reported 70% and 84% completion rates agree; no negative finding should be created.
4. Equation (1) defines predicted minus observed, while prose explicitly defines observed minus predicted; the sign conflicts. Variable definitions are otherwise present.
5. Figure 4 is mentioned without an available image or definition. Figure 3 is a referenced image that does not exist. The reviewer must record figure 3 as not visually inspected rather than inventing image content.
6. A general scalability claim exceeds the evidence: no population-size comparison exists for scalability. The separate 40-agent exploratory latency value alone is not a scalability experiment.
7. The 70% versus 84% completion result is supported by figure 2 and the text for the limited simulation, but this does not independently validate raw data, statistical significance, or generalization.
8. 6.7 ms is a correct one-decimal rounding of 6.67 ms. Values from a 20-agent ring and 40-agent star have different conditions and are not intrinsically contradictory.
9. Confirm citation, equation and table/figure references against available manuscript; avoid suggesting an absent item was inspected. Do not mark unrelated items as inconsistent merely for missing citations.
10. Record evidence hashes, source locations, scope and review limitations. No raw manuscript or images may be changed.
