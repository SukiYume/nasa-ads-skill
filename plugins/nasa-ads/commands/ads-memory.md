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

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md`; bundled scripts and references live under `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`.

1. Treat `$ARGUMENTS` as a `literature_db.py` subcommand with its arguments, `adslib`, or a plain-language request about the local library.
2. Select its row in Task Routing and load the section that row names: `references/literature-memory.md` covers lookup, stored passages, stored evidence, summary completion, classification, citations, and the Web library, and `references/library-maintenance.md` covers health checks, backup, restore, metadata refresh, duplicates, and migration.
3. A content question about a paper follows the Reading Scope. Return the result named in Completion and Handoff.
