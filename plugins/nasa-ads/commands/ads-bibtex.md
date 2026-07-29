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

1. Use `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py`. Try `python3`, `python`, then `py -3`; do not recreate a supported export. On a missing token, direct the user to https://ui.adsabs.harvard.edu/#user/settings/token and ask them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`.

2. Parse bibcode(s) and optional `--format` from `$ARGUMENTS`; default to `bibtex`. Current CLI formats: `bibtex`, `bibtexabs`, `ads`, `aastex`, `mnras`, `icarus`, `soph`, `endnote`, `ris`, `refworks`, `medlars`, `procite`, `ieee`, `votable`, `dcxml`, `refxml`, `refabsxml`, `rss`. If current ADS documentation lists another format, use the skill's HTTP fallback.

3. Run the bundled CLI with all parsed bibcodes.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" export \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --format bibtex
```
The CLI normalizes single- and multi-record responses to citation text. If Python 3 is unavailable, read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/http-fallback.md`. Never expose the token.

4. Check the CLI exit status before formatting the result. Display the output in a code block. Offer to save to a file (`.bib`, `.ris`, etc.) if the user wants.
