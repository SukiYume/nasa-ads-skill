---
description: "Research NASA ADS literature with full reading and silent personal-library reuse"
argument-hint: '<search query, e.g. "author:Einstein gravitational waves">'
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Search

Search the NASA Astrophysics Data System for academic papers.

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` and follow its task routing, Core Invariants, and completion criteria.

## Arguments

The user's search query: $ARGUMENTS

## Instructions

1. Interpret `$ARGUMENTS` as a research question or native ADS query, preserving explicit source, time, and selection constraints. Check reusable local evidence through `references/literature-memory.md`.
2. Use `references/ads-cli.md` for online discovery when needed. Choose query families, fields, sorting, page sizes, and filters for the task; its commands illustrate syntax. Record the searched scope and distinguish total matches from returned records.
3. Follow the shared Literature Research workflow for source summaries, the investigation set, reading, and completion checks. Load `references/research-writing.md` for review or manuscript-specific evidence criteria.
4. Export citations through the local citation workflow when the task needs them. Use ADS export for additional formats.
5. Return the requested synthesis, article detail, or search results in a format suited to the question, with traceable sources and relevant evidence limits. A search with no matches reports its queries, filters, and resulting coverage gap. Apply the shared failure routing to unfinished work.
