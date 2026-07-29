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

1. Use `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py`. Try `python3`, then `python`, then `py -3`. Do not recreate a supported call with curl, PowerShell, or temporary code. If the CLI reports a missing token, direct the user to https://ui.adsabs.harvard.edu/#user/settings/token and ask them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`.

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

3. If all Python 3 commands are unavailable, read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/http-fallback.md`. The CLI checks `ADS_API_TOKEN` and then `ADS_DEV_KEY`; never print or log the token. Check the exit status before parsing and present results with ADS links.
