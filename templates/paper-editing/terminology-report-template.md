# Terminology report

- Task ID, executor and actual execution mode:
- Input: workspace-relative manuscript path, SHA-256, review scope and version selection:
- Existing authorized glossary and its SHA-256, or none:
- Research domain/topic, target venue and limitations (unknown when not supplied):
- Analyze/Propose status, quality status and author approval status:

## Core term inventory

Summarize the observed technical concepts, model and algorithm names, datasets, metrics, abbreviations, and mathematical symbols. The full context-bound inventory is in `terminology_glossary.yaml`; missing information is unknown rather than invented.

## Terminology, acronyms and symbols

For each issue, list its ID, exact manuscript line and original anchor, context, suggested term or author question, rationale, priority, semantic risk and approval requirement. Explain potentially distinct concepts before proposing any normalization. Check abstract and body acronym definitions against venue policy without assuming they are duplicates to remove. Mention whether tables, figures or units were present and assessable.

## Ambiguities and author decisions

Record unresolved senses, terms not to interchange, unverified definitions, formula/variable/algorithm changes requiring author approval, and any issues outside this role's scope for the parent. Do not infer that an approval was given.

## Language handoff

Separate approved terminology constraints from proposed and unresolved entries, retain acronyms and symbols, and link `language_handoff.md`. A proposal is not an approved term.
