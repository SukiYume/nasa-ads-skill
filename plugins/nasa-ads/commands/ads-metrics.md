---
description: "Get citation metrics (h-index, citations, reads) for one or more ADS bibcodes"
argument-hint: "<bibcode1> [bibcode2] ..."
allowed-tools:
  - Bash
---

# NASA ADS Metrics

Retrieve citation metrics and bibliometric indicators for papers.

## Arguments

The bibcode(s): $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`, and ask them to retry or provide a token for the current session. Never hardcode, print, or log the token. Avoid verbose HTTP output that can reveal request headers, and never use `-L` or `--location`.

2. Parse bibcode(s) from `$ARGUMENTS`.

3. Fetch metrics:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/metrics" \
  -d '{"bibcodes":["bibcode1","bibcode2"],"types":["basic","citations","indicators"]}'
```

4. Check the HTTP status and reject a top-level `Error` or `error` field before interpreting the response. Read the actual response keys before formatting. ADS uses keys containing spaces, including `basic stats`, `basic stats refereed`, `citation stats`, `citation stats refereed`, `indicators`, and `indicators refereed`.

5. Display key metrics:
   - **Total papers / Refereed papers**
   - **Total citations / Refereed citations**
   - **h-index / g-index / i10-index**
   - **Mean citations per paper**
   - **Total reads**

6. Present results in a clean markdown table. State which bibcodes form the metric set, and avoid labeling a subset h-index as an author-level h-index.
