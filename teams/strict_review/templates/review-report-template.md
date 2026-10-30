# Strict review report

- Task ID and project ID:
- Reviewer role and actual execution mode (`native_subagent` or `inline_skill`), executor, and execution record:
- Authorized manuscript: workspace-relative artifact path, SHA-256, version and reviewed scope:
- Other authorized evidence: workspace-relative paths, SHA-256, source and availability:
- Review status, quality status and human approval status (record separately):

## Scope and evidence limits

State what was inspected and what was unavailable or not checked. Distinguish reporting-level review from actual computational replication. A figure reference alone is not a visual inspection; do not claim a result was replicated without the necessary data, code, settings and an executed check. Do not interpret a missing description as proof that an experiment was not performed.

## Evidence-linked findings

For each finding, include a separate `review-finding.schema.json` record and summarize all of its fields below. The finding ID connects the report to the structured record. Select severity and confidence by scientific judgment with justification, not automated wording. An evidence reference carries a workspace-relative artifact path, SHA-256, description and precise locator; independently verify files, hashes and relevance before relying on them.

### Finding [finding_id]

- Reviewer role / issue type / severity / confidence / verification status:
- Source location and original claim or observation:
- Evidence references (path, SHA-256, locator, description), or unavailable:
- Verification method and limitations:
- Reasoning and impact:
- Recommended action:
- Additional material required, or none:

Use `verified` only for the specifically supported observation actually checked, `potential` for an evidence-supported concern needing further verification, `insufficient_information` for an assessment that needs unavailable information, and `not_checked` for work not performed. A status or a nonempty citation is not itself proof. The schema requires at least one evidence reference for `verified` and `potential`.

## Independent scientific logic and disagreements

When applicable, record the independent reconstruction of problem, hypothesis, method, evidence and conclusion from the source manuscript before consulting other reports. Identify each substantive agreement, disagreement, and unresolved issue with source locations and reasons. Do not merely repeat prior findings or claim independent review when it did not occur.

## Questions, follow-up, and handoff

List questions for authors, missing inputs, unexamined items, and uncertainties. Propose handoff to paper editing only with user authorization; do not modify the manuscript. This is an AI-assisted research review, not a journal's formal peer-review decision. Record separate output paths and hashes using the project's `ExecutionResult` / `ArtifactReference` contract; schema-valid records are not a scientific or human approval.
