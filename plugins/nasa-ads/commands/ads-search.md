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

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` and follow its Literature Research workflow, Core Invariants, and completion criteria. Bundled scripts and references live under `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`.

1. Treat `$ARGUMENTS` as a research question or a native SciX query, keeping its explicit source, time, and selection constraints.
2. Check local evidence first with `search`, `parameters`, and `lookup` from `references/literature-memory.md`.
3. Discover missing or current work with `references/ads-cli.md`: preview with `--no-store`, screen, then capture retained records and complete their summaries and topics.
4. Load `references/research-writing.md` for reviews or manuscript sections.
5. Read every paper in the investigation set in full, as the Reading Scope requires.
6. Return the synthesis or results with traceable sources, the searched scope (total matches, returned records, retained candidates), and evidence limits. A search without matches reports its queries, filters, and coverage gap.
