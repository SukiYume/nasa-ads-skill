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

1. Use the bundled Python CLI at `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py`. It checks `ADS_API_TOKEN` and then `ADS_DEV_KEY`. If it reports that both are absent, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set one of those variables, and ask them to retry or provide a token for the current session. Never hardcode, print, or log the token.

2. Parse bibcode(s) and optional `--format` flag from `$ARGUMENTS`. Default format is `bibtex`. Supported: `bibtex`, `bibtexabs`, `ads`, `aastex`, `mnras`, `icarus`, `soph`, `endnote`, `ris`, `refworks`, `medlars`, `procite`, `ieee`, `votable`, `dcxml`, `refxml`, `refabsxml`, `rss`.

3. Run the bundled CLI with all parsed bibcodes. Use `python3`; if that command is unavailable, try `python`, then `py -3`.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" export \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --format bibtex
```
The CLI uses `GET` for one bibcode and `POST` for multiple bibcodes, then prints citation text for both response forms. Use the direct HTTP fallback in the shared `SKILL.md` only when Python 3 is unavailable.

4. Check the CLI exit status before formatting the result. Display the output in a code block. Offer to save to a file (`.bib`, `.ris`, etc.) if the user wants.
