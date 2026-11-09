---
description: "Suggest missing citations, find similar papers, resolve full-text and data links, or match reference strings to SciX bibcodes"
argument-hint: "[suggest <bibcode> <bibcode> ... | similar <bibcode> | links <bibcode> | refs <reference> ...]"
allowed-tools:
  - Bash
  - Read
  - Write
---

# SciX Citation Helper and Resolver

Subcommand and arguments: $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` for shared routing and Core Invariants, and `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/ads-cli.md` for the commands below.

| Subcommand | Command | Notes |
|---|---|---|
| `suggest` (default) | `ads_api.py suggest <bibcode> <bibcode> ...` | Needs at least two distinct bibcodes; label results as algorithmic suggestions with their scores |
| `similar` | `ads_api.py search --query 'similar(bibcode:<bibcode>)'` | Use for a single seed paper; choose fields, rows, and sorting for the task |
| `links` | `ads_api.py resolve <bibcode>` | Show available link types; labels name candidate links, and access is checked at retrieval |
| `refs` | `ads_api.py reference <reference> ...` or `--references-file <file>` | Report each reference's bibcode and score; check matches below `1.0` and list unresolved references |

Check the exit status and present results with SciX links. Before recommending a suggested paper as evidence, assess it through the shared Literature Research workflow; retrieve its metadata with `bigquery` when needed. Reading article content follows `references/fulltext.md`.
