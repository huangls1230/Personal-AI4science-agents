# Provenance and local changes

- Source: https://github.com/K-Dense-AI/scientific-agent-skills/tree/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/scientific-critical-thinking
- Git commit: `5f2bc0341354fd5590aef76a533ada1e1e5b4e62`.
- Upstream Skill version: 1.5, last reviewed 2026-10-01, skill author K-Dense Inc.
- License: MIT. Copyright (c) 2025 K-Dense Inc. See the unmodified `LICENSE.md` copied from the repository root.
- Upstream tree includes only `SKILL.md` and eight `references/*.md` files; there are no scripts, assets, or Skill-local dependency declarations.
- All nine upstream files and the root license were checked against the fixed Git tree before local changes. Unmodified upstream `SKILL.md` SHA-256: `563af70571b7dcd6a96bf2e303bedfdcba623b4e9f082d58f04aacbc961fdae4`.

## Local patch

1. Removed the unsupported frontmatter key `compatibility` while retaining supported metadata, author, version, license and descriptive content; its optional external-service claim no longer describes project capability.
2. Added explicit project confidentiality, authorization, input/output and hosted-model processing boundaries; these do not replace actual OS/tool permissions.
3. Replaced the executable scientific-schematics/OpenRouter example and recommendation with an explicit disabled-service boundary. Authorized local figures remain possible only when requested. No API key is required.
4. Replaced automatic attribution and online metadata fetching with a proposal-and-verification process contingent on relevance and authorization. Preserved the upstream bibliographic reference for attribution.
5. Added a note to `references/review_sources.md` marking the upstream historical schematic test as non-operative and source links as non-authorizing; the historical note is preserved.

The other seven reference files are unchanged. Teaching examples and clinical assessment frameworks are not manuscript evidence, and clinical frameworks should be applied only where appropriate. No upstream code, installation script, or external service was executed during staging.
