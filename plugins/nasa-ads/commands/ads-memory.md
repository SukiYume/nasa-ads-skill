---
description: "Search, inspect, maintain, and update the local full-text literature memory"
argument-hint: '<lookup, search, show, stats, audit, backup, enrich, or paper identifier and topics>'
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Literature Memory

Use the persistent literature database for: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/literature-memory.md` completely. Read `references/digest-schema.md` when the request creates, validates, ingests, merges, or replaces a digest.
2. Try `python3`, `python`, then `py -3` to run `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/literature_db.py`. Manage the SQLite database and object store exclusively through this CLI.
3. Map the request to the narrow command:
   - known paper plus scientific topics: `lookup <identifier> --topic '<topic>' ...`
   - local concept or finding: `search '<query>' --scope summary`
   - exact article phrase or unmodeled detail: `search '<query>' --scope fulltext`
   - complete stored digest and provenance: `show <identifier>`
   - collection health and counts: `stats`
   - full read-only health review: `audit`
   - recoverable maintenance snapshot: `backup`
   - refreshed metadata for an existing record: `enrich --manifest '<manifest.json>'`
4. Run `lookup` before opening article content. Follow `references/fulltext.md` and `references/digest-schema.md` when the exact version requires complete ingest or targeted facet expansion. Process the papers opened for the current request and leave unrelated records unchanged.
5. Return paper identifiers, version labels and hashes, reading coverage, matched facets, evidence locators, and stored article paths when useful. Cite the original paper in scientific answers; database snippets are not independent sources.
6. The bundled CLI exposes no delete operation. An approved repair or relocation starts with a CLI backup. Clearing, relocating, or manually rewriting the library requires the user's explicit confirmation.
