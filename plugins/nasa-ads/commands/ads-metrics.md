---
description: "Get citation metrics (h-index, citations, reads) for SciX bibcodes"
argument-hint: "<bibcode> [bibcode ...]"
allowed-tools:
  - Bash
  - Read
---

# SciX Metrics

Bibcodes: $ARGUMENTS

Read the Setup section of `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` and the Metrics section of `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/ads-cli.md`.

1. Run `ads_api.py metrics <bibcodes>`.
2. Interpret the response keys and the paper set as the Metrics section describes.
3. Return the metrics relevant to the question, in a table for comparisons, and report missing values and response errors.
