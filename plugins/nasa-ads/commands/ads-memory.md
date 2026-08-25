---
description: "Search, inspect, and update the local full-text literature memory"
argument-hint: '<lookup, search, show, stats, or paper identifier and topics>'
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Literature Memory

Use the persistent literature database for: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/literature-memory.md` completely.
2. Try `python3`, `python`, then `py -3` to run `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/literature_db.py`. Do not read or edit the SQLite database or object store directly.
3. Map the request to the narrow command:
   - known paper plus scientific topics: `lookup <identifier> --topic '<topic>' ...`
   - local concept or finding: `search '<query>' --scope summary`
   - exact article phrase or unmodeled detail: `search '<query>' --scope fulltext`
   - complete current digest and provenance: `show <identifier>`
   - collection health and counts: `stats`
4. When the user asks to add or refresh a paper, read `references/fulltext.md`, use `fulltext.py`, read the article, create a layered digest with all material facets, run `validate-digest`, then run `ingest`. Use `--merge` only after inspecting the current digest and adding targeted facets. Never ingest an abstract-only record.
5. Return paper identifiers, version labels and hashes, reading coverage, digest revision, matched facets, evidence locators, and stored article paths when useful. Cite the original paper in scientific answers; database snippets are not independent sources.
6. The bundled CLI has no delete operation. Do not clear, relocate, or manually rewrite the database without the user's explicit confirmation and a recoverable backup.
