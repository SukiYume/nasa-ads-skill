---
description: "Find suggested citations, related papers, or links to full text and data for ADS bibcodes"
argument-hint: "[suggest <bibcodes...> | links <bibcode> | similar <bibcode>]"
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Citation Helper & Resolver

Find related papers and external resource links.

## Arguments

The subcommand and arguments: $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, ask the user.

2. Parse the subcommand from `$ARGUMENTS`:

### `suggest <bibcode1> [bibcode2] ...` (default)
Suggest missing citations via "friends of friends" analysis:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/citation_helper" \
  -d '{"bibcodes":["bibcode1","bibcode2"]}'
```
Display each suggestion: title, author, bibcode, score.

### `links <bibcode>`
Get links to full text, data archives, and other external resources:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/resolver/<bibcode>"
```
Display available link types (PDF, HTML, data sources, etc.).

### `similar <bibcode>`
Find similar papers via the search API:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/search/query?q=similar(bibcode:<bibcode>)&fl=bibcode,title,author,year,citation_count&rows=10"
```

3. Present results clearly in markdown format.
