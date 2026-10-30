# Provenance and local modifications

- Upstream: https://github.com/K-Dense-AI/scientific-agent-skills/tree/5f2bc0341354fd5590aef76a533ada1e1e5b4e62/skills/peer-review
- Commit: `5f2bc0341354fd5590aef76a533ada1e1e5b4e62`; version: 2.4.
- Copyright (c) 2025 K-Dense Inc.; MIT: see LICENSE.md.
- `_common.py`: anchor access to project `workspace/`; exact read-only allowlist for the two internal assets used by scripts; directory-fd / no-follow checks; reject traversal, symlinks and hard-linked inputs; create outputs with O_EXCL; reject --force. Opened, bounded reads prevent check-then-open path races. Outputs may remain partial after write errors. This does not sandbox processes or shell redirection.
- `SKILL.md`: move upstream `compatibility` into `metadata.compatibility` without changing its content for local metadata validator compatibility; document local boundary, default template flags are unverified, hosted model is external processing, and no network/citation insertion without explicit authority. Retain all upstream confidentiality and intake restrictions. The unchanged intake validator always blocks external-service use and cannot authorize a hosted review.
- `references/tool_reference.md`: document adapted paths, exclusive writes, disabled --force and template semantics. Sample paths now refer to workspace copies.
- `references/ethical_review_practice.md`: require authorized retention/deletion, no automatic workspace emptying.
- CLI parser help in each script: accurately report disabled --force. No change to upstream review/intake validation logic.
- Not a sandbox, not a guarantee of model or tool-provider confidentiality; verification remains human responsibility. Only two script-required internal assets are direct read exceptions; copy other templates explicitly into workspace first.
