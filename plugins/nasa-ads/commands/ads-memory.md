---
description: "Search, reuse, organize, and maintain the personal literature library, including stored findings and parameters"
argument-hint: '<lookup, search, findings, parameters, passage, show, collections, annotate, citations, adslib, check, audit, backup, or a request>'
allowed-tools:
  - Bash
  - Read
  - Write
---

# Personal Literature Library

Request: $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` for routing and Core Invariants. Run `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/literature_db.py` with the first working Python command; manage the database and object store only through this CLI. Local operations need no SciX token.

Map the request to the narrowest operation and load its reference section:

| Need | Commands | Reference |
|---|---|---|
| Find stored papers, findings, or text | `lookup`, `show`, `search`, `list`, `passage` | `references/literature-memory.md` (Local Lookup, Read Stored Passages, Query Stored Evidence) |
| Reuse or cite a stored result, inference, or value | `findings "<topic>"`, `parameters "<quantity>"`, `--paper`, `--entity`, `--kind`, `--status`, `--format csv`; `passage --finding <finding_id>` to recheck the source paragraph | `references/literature-memory.md` (Query Stored Evidence, Read Stored Passages) |
| Finish summaries and reading | `pending`, `summarize`, `check --run-id`, `check --recent`, `reading-check` | `references/literature-memory.md` |
| Organize | `collections`, `annotate`, `organize` | `references/literature-memory.md` (Classification) |
| Citations | `citations`, `--fetch`, `--output` | `references/literature-memory.md` (Citation Export) |
| Web library | `adslib` or `scripts/adslib.py`; `install` registers the command | `references/literature-memory.md` (Web Library) |
| Health, backup, restore, metadata refresh, duplicates, upgrade from the previous release | `stats`, `audit`, `backup`, `restore`, `enrich`, `import-citations`, `reindex`, `compact`, `migrate` | `references/library-maintenance.md` |

Content questions follow the Reading Scope with `references/fulltext.md` and `references/digest-schema.md`. Return the handoff from Completion and Handoff in `SKILL.md`.
