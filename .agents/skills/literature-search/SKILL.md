---
name: literature-search
description: Discover and screen research literature for a defined topic, recording search coverage and candidate sources; use for literature discovery rather than full-text interpretation or library mutation.
---

Define the question, time range, inclusion criteria and permitted sources from the task. Expand search terms and search only sources actually available and authorized. Record queries, dates, source coverage, candidate identifiers, relevance and uncertainty. Deduplicate cautiously; preserve conflicting metadata for verification. Distinguish search snippets, metadata, abstracts and full text. Return a compact evidence-linked handoff to the parent and keep detailed artifacts in assigned workspace paths. Do not claim exhaustive coverage or fabricate citations. This skill supplies guidance, not a search connector.

## Project search tool

For an authorized public query, run `PYTHONPATH=src python3 -m ai4science.literature_cli` from the project root; read `docs/literature-search.md` for options and source-specific syntax. First formulate the research question, keyword synonyms, intended Boolean strategy and a source-compatible query; Crossref's bibliographic endpoint does not implement general Boolean logic; Semantic Scholar relevance search takes plain text and hyphens can prevent matches. Provide source-specific overrides where needed. Use small pages and a bounded verification count. Do not send internal or sensitive queries to public APIs.

Inspect the resulting JSON or a targeted subset and explain why top candidates match the question and methods; distinguish evidence quality, novelty and recency from what metadata can establish. The tool's lexical levels are provisional, not an academic quality score. If further assessment is requested, save it separately in the assigned workspace and preserve source outputs and hashes. Return status, errors, retrieved time, source coverage, concise findings and artifact references to the parent; report missing or failed sources and never imply full text was read. The Python tool does not itself invoke an LLM or connect the native delegation to the project's budget guard.
