---
description: "Export BibTeX, journal-style reference lists, or other citation formats for SciX bibcodes, DOIs, or arXiv IDs"
argument-hint: "<identifier> [identifier ...] [--format bibtex|aastex|mnras|ris|endnote|csl --style <journal>|custom|...]"
allowed-tools:
  - Bash
  - Read
  - Write
---

# SciX Citation Export

Identifiers and format: $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md`; bundled scripts and references live under `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`.

1. Parse the identifiers and optional `--format`; the default is `bibtex`.
2. BibTeX follows the Citation Export section of `references/literature-memory.md`. Other formats, a fresh remote export, and the no-write opt-out follow the Citation Export section of `references/ads-cli.md`, where `csl` with `--style <journal>` gives a journal-style reference list and `custom` gives custom keys or layouts.
3. Return the citation export result named in Completion and Handoff, in a code block or the requested file.
