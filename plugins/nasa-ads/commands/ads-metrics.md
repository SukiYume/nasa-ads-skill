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

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, ask the user.

2. Parse bibcode(s) from `$ARGUMENTS`.

3. Fetch metrics:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/metrics" \
  -d '{"bibcodes":["bibcode1","bibcode2"],"types":["basic","citations","indicators"]}'
```

4. Display key metrics:
   - **Total papers / Refereed papers**
   - **Total citations / Refereed citations**
   - **h-index / g-index / i10-index**
   - **Mean citations per paper**
   - **Total reads**

5. Present results in a clean markdown table.
