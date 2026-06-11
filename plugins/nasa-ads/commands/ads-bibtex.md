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

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, tell the user to create one at https://ui.adsabs.harvard.edu/#user/settings/token by signing in or registering, opening account settings > **API Token**, clicking **Generate a new key**, and saving it as `ADS_API_TOKEN` or `ADS_DEV_KEY`; then ask them to retry or provide a token for the current session.

2. Parse bibcode(s) and optional `--format` flag from `$ARGUMENTS`. Default format is `bibtex`. Supported: `bibtex`, `bibtexabs`, `ads`, `aastex`, `mnras`, `icarus`, `soph`, `endnote`, `ris`, `refworks`, `medlars`, `procite`, `ieee`, `votable`, `dcxml`, `refxml`, `refabsxml`, `rss`.

3. If single bibcode, use GET:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/export/<format>/<bibcode>"
```
Single-bibcode GET returns raw citation text in the requested format.

4. If multiple bibcodes, use POST:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/export/<format>" \
  -d '{"bibcode":["bibcode1","bibcode2"]}'
```
Multi-bibcode POST returns JSON with an `export` field.

5. Display the output in a code block. Offer to save to a file (`.bib`, `.ris`, etc.) if the user wants.
