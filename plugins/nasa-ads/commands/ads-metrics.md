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

1. Use the bundled Python CLI at `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py`. It checks `ADS_API_TOKEN` and then `ADS_DEV_KEY`. If it reports that both are absent, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set one of those variables, and ask them to retry or provide a token for the current session. Never hardcode, print, or log the token.

2. Parse bibcode(s) from `$ARGUMENTS`.

3. Fetch metrics with the bundled CLI. Use `python3`; if that command is unavailable, try `python`, then `py -3`.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" metrics \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --type basic \
  --type citations \
  --type indicators
```
Use the direct HTTP fallback in the shared `SKILL.md` only when Python 3 is unavailable.

4. Read the actual response keys before formatting. ADS uses keys containing spaces, including `basic stats`, `basic stats refereed`, `citation stats`, `citation stats refereed`, `indicators`, and `indicators refereed`.

5. Display key metrics:
   - **Total papers / Refereed papers**
   - **Total citations / Refereed citations**
   - **h-index / g-index / i10-index**
   - **Mean citations per paper**
   - **Total reads**

6. Present results in a clean markdown table. State which bibcodes form the metric set, and avoid labeling a subset h-index as an author-level h-index.
