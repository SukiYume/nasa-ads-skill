---
description: "Fetch and read lawful full text for ADS bibcodes, DOIs, or arXiv IDs"
argument-hint: "<bibcode, DOI, or arXiv ID...>"
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Full Text

Fetch and read article full text for: $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` and apply its shared reading scope, Core Invariants, and completion criteria.

## Instructions

1. Parse the requested papers, versions, and scientific question from `$ARGUMENTS`. Follow local lookup in `references/literature-memory.md` to select stored evidence and identify missing work.
2. Use `references/fulltext.md` for needed retrieval and reading. Pass each identifier as a separate shell-quoted argument. Inspect every manifest status, version, and access attempt; route text, visual reading, and abstract-only evidence according to that reference.
3. Use `references/digest-schema.md` for new digests or targeted merges. Complete capture-run source summaries through the library reference.
4. Apply the shared research completion checks and return the requested content with source links, relevant versions, evidence locations, and unresolved limitations. Use the shared failure routing for recovery.
