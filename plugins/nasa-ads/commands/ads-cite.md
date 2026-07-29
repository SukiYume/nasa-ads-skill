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

1. Use the bundled Python CLI at `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py`. It checks `ADS_API_TOKEN` and then `ADS_DEV_KEY`. If it reports that both are absent, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set one of those variables, and ask them to retry or provide a token for the current session. Never hardcode, print, or log the token. Use `python3`; if that command is unavailable, try `python`, then `py -3`.

2. Parse the subcommand from `$ARGUMENTS`:

### `suggest <bibcode1> [bibcode2] ...` (default)
Suggest missing citations via "friends of friends" analysis:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" suggest \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A
```
Display each suggestion: title, author, bibcode, score. Label it as an algorithmic suggestion and inspect topical relevance before recommending it.

### `links <bibcode>`
Get links to full text, data archives, and other external resources:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" resolve \
  2016PhRvL.116f1102A
```
Display available link types (PDF, HTML, data sources, etc.).

### `similar <bibcode>`
Find similar papers via the search API:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" search \
  --query 'similar(bibcode:2016PhRvL.116f1102A)' \
  --fields 'bibcode,title,author,year,citation_count' \
  --rows 10
```

3. Use the direct HTTP fallback in the shared `SKILL.md` only when Python 3 is unavailable. Check the CLI exit status before parsing. Present results clearly in markdown format with ADS links.
