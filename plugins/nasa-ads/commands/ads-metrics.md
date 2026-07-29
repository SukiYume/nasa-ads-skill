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

1. Use `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py`. Try `python3`, then `python`, then `py -3`. Do not recreate a supported metrics call with curl, PowerShell, or temporary code. If the CLI reports a missing token, direct the user to https://ui.adsabs.harvard.edu/#user/settings/token and ask them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`.

2. Parse bibcode(s) from `$ARGUMENTS`.

3. Fetch metrics with the bundled CLI. It checks `ADS_API_TOKEN` and then `ADS_DEV_KEY`.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" metrics \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --type basic \
  --type citations \
  --type indicators
```
If all Python 3 commands are unavailable, read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/http-fallback.md`. Never print or log the token.

4. Read the actual response keys before formatting. ADS uses keys containing spaces, including `basic stats`, `basic stats refereed`, `citation stats`, `citation stats refereed`, `indicators`, and `indicators refereed`.

5. Display key metrics:
   - **Total papers / Refereed papers**
   - **Total citations / Refereed citations**
   - **h-index / g-index / i10-index**
   - **Mean citations per paper**
   - **Total reads**

6. Present results in a clean markdown table. State which bibcodes form the metric set, and avoid labeling a subset h-index as an author-level h-index.
