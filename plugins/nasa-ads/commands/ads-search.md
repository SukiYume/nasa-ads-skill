---
description: "Research a question or SciX query with full reading and silent personal-library reuse"
argument-hint: '<research question or SciX query, e.g. "repeating FRB polarization since 2022">'
allowed-tools:
  - Bash
  - Read
  - Write
---

# SciX Literature Search

Research request: $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md`; bundled scripts and references live under `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`.

1. Treat `$ARGUMENTS` as a research question or a native SciX query, keeping its explicit source, time, and selection constraints.
2. Select its row in Task Routing: a research question follows the Literature Research workflow with the references each step links, and an identifier or metadata query runs `ads_api.py search` as in `references/ads-cli.md`.
3. Return the result named in Completion and Handoff.
