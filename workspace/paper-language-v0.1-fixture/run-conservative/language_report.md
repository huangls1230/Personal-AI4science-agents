# Academic language revision report

- Task ID, actual execution mode and executor: `paper-language-v0.1-conservative`; `native_subagent`; `paper_language`.
- Project ID, authorized source version, workspace-relative path and SHA-256: `paper-language-synthetic-v01`; synthetic fixture; `paper-language-v0.1-fixture/manuscript.md`; `fa05039c73ebacae4d9f1d76d901521e00d78603ddf703ce91974bf2d45a4501`.
- Editing mode, language variant, requested scope and detected manuscript style: `conservative`, `preserve`; prose on source lines 7, 11, 13, 17, 28 and 36 only. US-style spelling is present (e.g., “analyze”); no spelling conversion was performed. Document type: synthetic manuscript; domain: forecasting in a multi-agent system.
- Authorized glossary path and SHA-256; trusted approvals or unresolved authorization: `paper-language-v0.1-fixture/terminology_glossary.yaml`; `b9984d7799e7ceb01ab603447cc27ab1085fb40d19a8a17333c568b20baad2a0`. Entries marked approved are simulated mock approvals only, not actual author approval; source terms and symbols are preserved.
- Candidate draft, review status, quality status and author approval status: `paper-language-v0.1-fixture/run-conservative/manuscript_edited.md` is an unapproved candidate; independent parent review and author approval are pending. Scientific claims, fictional numbers and references were not independently verified.

## Summary and proposed edits

All candidate wording is unapproved and requires author review.

### L01 — source line 7
- Original: A multi-agent system (MAS) use time series forecasts to coordinate agents.
- Proposed: A multi-agent system (MAS) uses time series forecasts to coordinate agents.
- Issue and reason: agreement; Correct subject–verb agreement.
- Semantic risk: low; approval required: yes; status: proposed; applied to candidate: yes.

### L02 — source line 11
- Original: In order to be able to make decisions at a later time, agents use forecasts that are produced before that time, and these forecasts are produced in advance of the decisions that will be made later.
- Proposed: To make decisions at a later time, agents use forecasts produced before that time.
- Issue and reason: concision; Remove repeated wording while retaining the temporal relationship.
- Semantic risk: low; approval required: yes; status: proposed; applied to candidate: yes.

### L03 — source line 13
- Original: It checks whether the input is available.
- Proposed: It checks whether the input is available.
- Issue and reason: ambiguous reference; The sentence does not identify whether the controller or monitor performs the check; ask the author.
- Semantic risk: high; approval required: yes; status: deferred; applied to candidate: no.

### L04 — source line 17
- Original: The Horizon Mapper produce a forecast from the available observations.
- Proposed: The Horizon Mapper produces a forecast from the available observations.
- Issue and reason: agreement; Correct subject–verb agreement while preserving the model name.
- Semantic risk: low; approval required: yes; status: proposed; applied to candidate: yes.

### L05 — source line 28
- Original: These fictional values indicate a difference in this example, but they do not establish a causal effect.
- Proposed: These fictional values indicate a difference in this example, but they do not establish a causal effect.
- Issue and reason: ambiguous reference; The referent and comparison underlying “values” and “a difference” are not clear from this sentence; ask the author without inferring them.
- Semantic risk: high; approval required: yes; status: deferred; applied to candidate: no.

### L06 — source line 36
- Original: The synthetic result is limited to the described example. The synthetic result is limited to the described example.
- Proposed: The synthetic result is limited to the described example.
- Issue and reason: duplication; Remove an exact repeated sentence while retaining the stated limitation.
- Semantic risk: low; approval required: yes; status: proposed; applied to candidate: yes.

## Deferred questions and specialist handoff

- L03: Which component performs the availability check? Do not resolve the pronoun without author input.
- L05: What values and comparison does the stated difference refer to? The limitation on causal interpretation remains unchanged.
- No terminology or structural change is proposed.

## Preservation and limits

The candidate is constructed by applying the four low-risk replacements only on authorized source lines. All other content, including headings, Markdown layout, tables, fenced code, citations, numbers, units, formulas, names, abbreviations and mock-approved terminology, is retained by construction. Deferred items remain unchanged. These checks are partial; they cannot prove preserved scientific meaning or establish author approval.
