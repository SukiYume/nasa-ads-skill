---
description: Export BibTeX (or other citation formats) for one or more ADS bibcodes
argument-hint: <bibcode1> [bibcode2] ... [--format bibtex|aastex|mnras|ris|endnote]
allowed-tools: [Bash, Read, Write]
---

# NASA ADS Citation Export

Export citation entries for the given ADS bibcodes.

## Arguments

The bibcode(s) and optional format: $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, ask the user.

2. Parse bibcode(s) and optional `--format` flag from `$ARGUMENTS`. Default format is `bibtex`. Supported: `bibtex`, `bibtexabs`, `aastex`, `mnras`, `icarus`, `soph`, `endnote`, `ris`, `ieee`, `custom`.

3. If single bibcode, use GET:
```bash
curl -s -H "Authorization: Bearer $ADS_API_TOKEN" \
  "https://api.adsabs.harvard.edu/v1/export/<format>/<bibcode>"
```

4. If multiple bibcodes, use POST:
```bash
curl -s -H "Authorization: Bearer $ADS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/export/<format>" \
  -d '{"bibcode":["bibcode1","bibcode2"]}'
```

5. Display the output in a code block. Offer to save to a file (`.bib`, `.ris`, etc.) if the user wants.
