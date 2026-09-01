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

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/fulltext.md` completely. Read `references/literature-memory.md` before opening article content and `references/digest-schema.md` when the exact version requires ingest.
2. Parse the requested identifiers from `$ARGUMENTS`. Run `literature_db.py lookup` with requested scientific topics before opening article content. Reuse an exact complete stored version with suitable facet coverage. An explicit refresh request performs a current source check.
3. For a database miss, changed version, or uncovered topic, try `python3`, `python`, then `py -3` to run the bundled full-text CLI. Pass every identifier as its own shell-quoted argument. Use the CLI's discovery, download, cache, and extraction pipeline.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/fulltext.py" fetch \
  '<identifier-1>' \
  '<identifier-2>'
```

4. Inspect every result status and selected version. For each `fulltext` result, run `outline`, reconcile headings with the artifact, and follow the reading procedure. Follow the visual workflow for `needs_visual_reading` and the evidence boundary for `abstract_only`. Use `--format pdf` when layout, equations, figures, tables, or pagination matter.
5. Complete the exact-version ingest or targeted merge described in `digest-schema.md` before using newly opened article details. Process the papers opened for the current request and leave unrelated database records unchanged.
6. Return a content-based synthesis with source/version labels, article links, evidence locators, and the full-text/database-reuse coverage counts required by the method note.
7. Keep ADS credentials inside ADS API requests. Use lawful public article sources and label abstract-only evidence accurately.
