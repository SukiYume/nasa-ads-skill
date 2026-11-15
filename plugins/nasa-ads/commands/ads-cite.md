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

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md`, then the section of `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/ads-cli.md` that the subcommand names:

| Subcommand | Command | Section |
|---|---|---|
| `suggest` (default) | `ads_api.py suggest <bibcode> <bibcode> ...` | Suggestions and Resource Links |
| `similar` | `ads_api.py search --query 'similar(bibcode:<bibcode>)'` | Search |
| `links` | `ads_api.py resolve <bibcode>` | Suggestions and Resource Links |
| `refs` | `ads_api.py reference <reference> ...` or `--references-file <file>` | References, Objects, and Journals |

Present results with SciX links. A suggested or matched paper whose content the answer relies on joins the investigation set of the Reading Scope.
