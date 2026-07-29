---
description: "Find suggested citations, related papers, or links to full text and data for ADS bibcodes"
argument-hint: "[suggest <bibcodes...> | links <bibcode> | similar <bibcode>]"
allowed-tools:
  - Bash
---

# NASA ADS Citation Helper & Resolver

Find related papers and external resource links.

## Arguments

The subcommand and arguments: $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`, and ask them to retry or provide a token for the current session. Never hardcode, print, or log the token. Avoid verbose HTTP output that can reveal request headers.

2. Parse the subcommand from `$ARGUMENTS`:

### `suggest <bibcode1> [bibcode2] ...` (default)
Suggest missing citations via "friends of friends" analysis:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/citation_helper" \
  -d '{"bibcodes":["bibcode1","bibcode2"]}'
```
Display each suggestion: title, author, bibcode, score. Label it as an algorithmic suggestion and inspect topical relevance before recommending it.

### `links <bibcode>`
Get links to full text, data archives, and other external resources:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/resolver/<bibcode>"
```
Display available link types (PDF, HTML, data sources, etc.).

### `similar <bibcode>`
Find similar papers via the search API:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsSG "https://api.adsabs.harvard.edu/v1/search/query" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'q=similar(bibcode:<bibcode>)' \
  --data-urlencode 'fl=bibcode,title,author,year,citation_count' \
  --data-urlencode 'rows=10'
```

3. Check the HTTP status before parsing. Present results clearly in markdown format with ADS links.
