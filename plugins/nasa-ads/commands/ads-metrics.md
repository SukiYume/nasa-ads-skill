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

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/ads-cli.md`, then use its bundled CLI, launch order, token boundary, and failure handling.

2. Parse bibcode(s) from `$ARGUMENTS`.

3. Fetch the default basic, citation, and indicator metrics:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" metrics \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A
```
4. Read the actual response keys before formatting. ADS uses keys containing spaces, including `basic stats`, `basic stats refereed`, `citation stats`, `citation stats refereed`, `indicators`, and `indicators refereed`.

5. Display key metrics:
   - **Total papers / Refereed papers**
   - **Total citations / Refereed citations**
   - **h-index / g-index / i10-index**
   - **Mean citations per paper**
   - **Total reads**

6. Present results in a clean markdown table. State which bibcodes form the metric set, and avoid labeling a subset h-index as an author-level h-index.
