# Post-review checks: read only after the independent review is completed

All inputs are synthetic. Compute independently with arithmetic: forecast errors are -1, -2, 1, 2; sum absolute errors 6; sum squared errors 10; MAE 6/4 = 1.5; RMSE sqrt(10/4) = sqrt(2.5), approximately 1.5811388300841898; reported 1.20 differs by approximately -0.3811388300841898 if difference is reported minus recalculated.

Communication totals are 300 baseline and 240 proposed, giving (300 - 240) / 300 * 100 = 20%. Do not use proposed as denominator. Paired task-error differences (proposed minus baseline) are -1, +1, -1, +2: two improvements and two deteriorations. Explicit matching makes an independent-samples procedure inappropriate for the stated paired contrast; design-aware assessment should not imply that a paired test necessarily establishes significance.

The main text improperly treats overlapping windows within a single run as independent experiment replications and overgeneralizes; recommend independent runs and dependence-aware inference, without mechanically requiring a p-value. The report-only case cannot be recalculated. The boundary case has correctly rounded metrics, describes dependencies, limits claims, and should not receive fabricated errors or automatic baseline/significance findings.
