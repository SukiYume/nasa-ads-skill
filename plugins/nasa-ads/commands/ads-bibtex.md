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

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` for shared routing and Core Invariants. Bundled scripts and references live under `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`. Citation-only requests do not open article content.

1. Parse the identifiers and optional `--format`; the default is `bibtex`.
2. For BibTeX, follow the Citation Export section of `references/literature-memory.md`: export with `literature_db.py citations <identifiers>`, add `--fetch` for publication-ready official entries, and retrieve missing papers with `ads_api.py bigquery` before exporting.
3. For other formats, a fresh remote export, or the no-write opt-out, run `ads_api.py export <bibcodes> --format <format>` as described in `references/ads-cli.md`; a journal-style reference list uses `--format csl --style <journal>`, and custom keys or layouts use `--format custom --custom-format <format>`.
4. Check the exit status. Return the entries in a code block or write the requested file and report its path, keys, missing entries, and official or metadata-generated provenance.
