---
description: "Export BibTeX (or other citation formats) for one or more ADS bibcodes"
argument-hint: "<bibcode1> [bibcode2] ... [--format bibtex|aastex|mnras|ris|endnote]"
allowed-tools:
  - Bash
---

# NASA ADS Citation Export

Export citation entries for the given ADS bibcodes.

## Arguments

The bibcode(s) and optional format: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/ads-cli.md`, then use its bundled CLI, launch order, token boundary, and failure handling.

2. Parse bibcode(s) and optional `--format` from `$ARGUMENTS`; default to `bibtex`. Accept only formats exposed by the current CLI.

3. Run the bundled CLI with all parsed bibcodes.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" export \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --format bibtex
```
The CLI normalizes single- and multi-record responses to citation text.

4. Check the CLI exit status before formatting the result. Display the output in a code block. Offer to save to a file (`.bib`, `.ris`, etc.) if the user wants.
