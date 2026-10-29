---
name: zotero-citation
description: Inspect Zotero records, verify citation metadata, export references and prepare authorized reading-status or note-link proposals.
---

Use `docs/literature-citation.md` for the current project tool, commands and runtime limitations. Check actual Zotero readiness first; query only the required library, keys and bounded pages. The user-library ID `users/0` is a local API selector, not necessarily the numeric Better BibTeX internal library ID. Treat returned records as source assertions; do not invent a DOI, citation key, missing field or completed export.

For DOI verification, use the project's Crossref lookup when external disclosure is authorized; compare fields and preserve conflicts. A DOI/title match does not verify every field or prove a scientific claim. Classify probable duplicates and preprint/published versions for review, never merge or delete them. Obtain citation keys from Better BibTeX only when actually available; Zotero's exported BibTeX key is not automatically a stable BBT key. Ask Zotero or an existing CSL processor for formatting, reporting missing formats/styles without hand-written substitutes.

Use the workspace ReadingResult and note hash to propose a project-internal record link; do not edit reading analysis, access Obsidian, or write external notes. Reading-status changes are dry-run only in this version. User understanding and a specific authorized action must be established before any future `research-verified` write; API authorization alone is insufficient. Preserve versions, exact changes, errors and unknown usage; return structured results and artifact references to the parent without loading an entire library.
