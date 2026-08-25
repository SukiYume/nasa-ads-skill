---
description: "Fetch and read lawful full text for ADS bibcodes, DOIs, or arXiv IDs"
argument-hint: "<bibcode, DOI, or arXiv ID...>"
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Full Text

Fetch and read article full text for: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/fulltext.md` completely. If the request includes summarizing, investigating, or reusing paper content, also read `references/literature-memory.md`.
2. Parse the requested identifiers from `$ARGUMENTS`. For a content request, run `literature_db.py lookup` first and reuse only an exact stored version with suitable facet coverage. An explicit refresh request still performs a fresh source check.
3. For database misses, changed versions, or uncovered topics, try `python3`, `python`, then `py -3` to run the bundled full-text CLI. Pass every identifier as its own shell-quoted argument. Do not recreate its discovery, download, cache, or extraction logic.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/fulltext.py" fetch \
  '<identifier-1>' \
  '<identifier-2>'
```

4. Inspect every result status and selected version. Read each `fulltext` text path. Follow the visual-reading procedure for `needs_visual_reading`. Report and limit `abstract_only` evidence as specified in the reference.
   When layout, equations, figures, tables, or pagination matter and automatic retrieval selected HTML, rerun that identifier with `--format pdf`; do not download it with an ad hoc command.
5. After reading a material paper, build a layered digest with all material facets, validate it, and ingest it. Use `--merge` for a later targeted reading so previous facets and digest revisions remain available.
6. Return a content-based synthesis with source/version labels, article links, evidence locators, and the full-text/database-reuse coverage counts required by the method note.
7. Never expose an ADS token, send it to an external article host, bypass a paywall, or claim that an abstract page is full text.
