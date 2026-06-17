---
description: "Search NASA ADS for papers by keyword, author, title, bibcode, or arxiv ID and display results with metadata"
argument-hint: '<search query, e.g. "author:Einstein gravitational waves">'
allowed-tools:
  - Bash
---

# NASA ADS Search

Search the NASA Astrophysics Data System for academic papers.

## Arguments

The user's search query: $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variables `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`, and ask them to retry or provide a token for the current session. Never hardcode or log the token.

2. Parse the user's query from `$ARGUMENTS`. Interpret natural language:
   - "papers by Einstein on relativity" -> `q=author:"Einstein" title:"relativity"`
   - "gravitational waves 2020-2024" -> `q=gravitational+waves year:2020-2024`
   - A bibcode like "2016PhRvL.116f1102A" -> `q=bibcode:2016PhRvL.116f1102A`
   - An arxiv ID like "1602.03837" -> `q=arxiv:1602.03837`
   - "refereed papers about dark matter" -> `q=dark+matter&fq=property:refereed`
   - "papers citing 2016PhRvL.116f1102A" -> `q=citations(bibcode:2016PhRvL.116f1102A)`

3. Execute the search using curl. Always pass `q`, `fq`, `sort`, and other query parameters with `--data-urlencode`; ADS bibcodes and queries can contain characters such as `&` that break raw URLs.
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -sG "https://api.adsabs.harvard.edu/v1/search/query" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'q=<ads_query>' \
  --data-urlencode 'fl=bibcode,title,author,abstract,year,pub,doi,identifier,citation_count' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=citation_count desc'
```

4. For each result, display in a clean format:
   - **Title**
   - **Authors** (first 5, then "et al." if more)
   - **Year** | **Journal** | **Citations**: count
   - **ADS**: `https://ui.adsabs.harvard.edu/abs/<bibcode>`
   - **arXiv**: extract from identifier array if available
   - **DOI**: if available

5. If the user asks for BibTeX, fetch it via `/export/bibtex`.

6. Present results clearly in markdown format.
