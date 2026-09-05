---
description: "Export BibTeX (or other citation formats) for one or more ADS bibcodes"
argument-hint: "<bibcode1> [bibcode2] ... [--format bibtex|aastex|mnras|ris|endnote]"
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Citation Export

Export citation entries for the given ADS bibcodes.

## Arguments

The bibcode(s) and optional format: $ARGUMENTS

## Instructions

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` for shared routing, persistence defaults, and failure handling.

1. Parse bibcode(s) and optional `--format` from `$ARGUMENTS`; default to `bibtex`. Accept only formats exposed by the current CLI. Resolve bundled scripts from `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`.

2. For BibTeX, read the Citation Export section of `references/literature-memory.md` and inspect the requested local records. Export through `literature_db.py citations <identifiers>`. Cached official entries and metadata-derived entries work offline; identify their provenance. Fetch official entries with `citations --fetch` when requested or needed for publication-ready citations. For missing records, use ADS `bigquery`, complete that run's source summaries and scientific topics, then export. Citation-only requests follow this route without opening article content.

3. For online work, load `references/ads-cli.md` and follow its token boundary and error handling. The shared no-library-write exception governs explicit opt-outs. For another format or an explicit fresh remote export, run the ADS CLI with the parsed bibcodes. This example exports two papers as RIS:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" export \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --format ris
```
The CLI normalizes single- and multi-record responses to citation text.

4. Check the CLI exit status. Return citation text in the matching code block, or write the requested `.bib`, `.ris`, or other output file and report its path. Include any missing entries and provenance limits.
