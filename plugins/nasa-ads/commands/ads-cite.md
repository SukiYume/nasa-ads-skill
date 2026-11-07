---
description: "Suggest missing citations, find similar papers, or resolve full-text and data links for SciX bibcodes"
argument-hint: "[suggest <bibcode> <bibcode> ... | similar <bibcode> | links <bibcode>]"
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
| `links` | `ads_api.py resolve <bibcode>` | Show available link types; labels identify candidates, not open access |

Check the exit status and present results with SciX links. Before recommending a suggested paper as evidence, assess it through the shared Literature Research workflow; retrieve its metadata with `bigquery` when needed. Reading article content follows `references/fulltext.md`.
