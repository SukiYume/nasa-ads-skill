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

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` for shared task routing, reading scope, and completion criteria. Use `references/literature-memory.md` for captured summaries and local reuse. Citation-helper suggestions selected for investigation may need metadata from `bigquery` before the shared research workflow.


1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/ads-cli.md`, then use its bundled CLI, launch order, token boundary, and failure handling.

2. Parse the subcommand from `$ARGUMENTS`:

### `suggest <bibcode1> <bibcode2> [bibcode3] ...` (default)
Suggest missing citations via "friends of friends" analysis:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" suggest \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A
```
Label algorithmic suggestions and include the identifiers and scores useful to the question. Assess scientific relevance through the shared research workflow before recommending a paper as evidence.
The service models an existing bibliography, so require at least two distinct bibcodes. For a single seed paper, use `similar` instead.

### `links <bibcode>`
Get links to full text, data archives, and other external resources:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" resolve \
  2016PhRvL.116f1102A
```
Display available link types (PDF, HTML, data sources, etc.).

Resolver labels identify candidates. When the user asks to retrieve or read article content, use `/nasa-ads:ads-fulltext` or follow `references/fulltext.md`; an arXiv `/abs/` page is metadata only.

### `similar <bibcode>`
Find similar papers via the search API. This example requests one page; choose retrieval parameters for the task:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" search \
  --query 'similar(bibcode:2016PhRvL.116f1102A)' \
  --fields 'bibcode,title,author,year,citation_count' \
  --rows 10
```

3. Check the CLI exit status before parsing and present results with ADS links.
