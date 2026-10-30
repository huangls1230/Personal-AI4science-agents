# Provenance and local changes

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills/tree/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-writing
- Upstream commit: `5f2bc0341354fd5590aef76a533ada1e1e5b4e62`
- Upstream skill version: 2.3
- License: MIT, Copyright (c) 2025 K-Dense Inc.; complete license in `LICENSE.md`.
- Local adaptation: 2026-10-29; only this skill was copied.

## Changes

- `assets/source_manifest_template.json`: default confidentiality to `unknown`, add an empty public-access attestation.
- `scripts/validate_manifest.py`: accept `unknown`; require an independently recorded human, date and basis before accepting `public`. Existing public records without a record must be reviewed. These fields do not prove access rights.
- `scripts/_common.py`: anchor file access to the project root derived from the installed skill location; reject traversal, links, external paths and oversized/non-regular inputs; use directory-relative no-follow and exclusive operations. It fails closed where these OS primitives are unavailable.
- `scripts/scaffold_manuscript.py`: create output directories using the same confined operations.
- `SKILL.md` and `references/evidence_workflow.md`: explain classification, external authorization and workspace handling; move compatibility text to metadata for the installed validator; avoid automatically adding an upstream citation.
- `SKILL.md`, `references/authorship_ai_confidentiality.md`, `references/citation_styles.md`, `references/cli_reference.md`, `references/evidence_workflow.md`, and `references/reporting_guidelines.md`: make CLI examples relative to the project root.

External files must be explicitly authorized and copied into the project workspace using approved Codex tools before CLI processing. The scripts do not enlarge the permitted root. These checks do not replace Codex permissions, approval, OS sandboxing or human decisions: output redirection and concurrent directory relocation are outside their guarantee. Do not treat the attestation as proof of permission to transmit. CLI reports and logs can contain sensitive metadata.
