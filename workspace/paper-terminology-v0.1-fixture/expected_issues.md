# Synthetic fixture: expected terminology observations

Input: `workspace/paper-terminology-v0.1-fixture/manuscript.md`  
SHA-256: `c339f56ab7f085348c3bc2c057083129d858a1b68b8a5a7ff753f2f48b36dc1c`

The fixture is invented solely for testing. No experiments, measurements or external citations exist; findings below are an independent acceptance guide, not replacements or verified scientific definitions.

| Location | Expected observation | Appropriate treatment |
| --- | --- | --- |
| 7, 11, 13 | `multi-agent system`, `Multi-Agent System`, `Multi-Agent system` vary in capitalization. | Propose a context-sensitive capitalization convention; do not silently alter the source. |
| 7, 11 | `MAS` is defined in both abstract and main text. | Identify repeated definitions, but acknowledge that separate abstract and main-text definitions can be appropriate under venue rules; do not automatically remove either. |
| 11, 13 | The system and its communication graph are described distinctly at line 11 but treated interchangeably at line 13. | Flag a potential concept conflict; ask the author to clarify the intended workflow rather than merging the terms. |
| 11 | `Agent Network` and `agent network` differ in capitalization. | Propose a convention only if both denote the same concept in context. |
| 15 | `Horizon Mapper` is an author-defined model name; `GCF` has no definition. | Preserve the model name; ask the author to define GCF, without inventing an expansion. |
| 19, 21 | `$\lambda$` denotes both a horizon in time steps and a dimensionless penalty weight. | Flag a high-risk symbol conflict; request author approval for any proposed symbol or formula changes. |
| 23 | `agent` can mean an autonomous entity or a component in `software agent package`. | Preserve the distinction, record ambiguity and request clarification if necessary; never blindly normalize. |
| 27 | `mean absolute error (MAE)` and `Average Absolute Error (AAE)` are explicitly said to name the same intended quantity in this fixture. | Suggest confirming the intended definition and consistent name/acronym; do not treat similar metric names as equivalent outside this supplied context. |

A useful glossary should include model names, abbreviations, the conflicting symbol, metric candidates, location and context, and leave inferred or unverified definitions unverified. No automatic application or source overwrite is authorized by this fixture.
