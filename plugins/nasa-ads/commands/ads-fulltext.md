---
description: "Read lawful full text for SciX bibcodes, DOIs, or arXiv IDs and store a complete digest"
argument-hint: "<bibcode, DOI, or arXiv ID...> [question about the paper]"
allowed-tools:
  - Bash
  - Read
  - Write
---

# SciX Full Text

Papers and question: $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` and apply its Reading Scope, Core Invariants, and completion criteria. Bundled scripts and references live under `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`.

1. Parse the papers, versions, and scientific question from `$ARGUMENTS`.
2. Run `lookup` from `references/literature-memory.md` and reuse intact complete versions through `findings` and `passage`.
3. Retrieve and read missing versions with `references/fulltext.md`, inspecting every manifest status, version, and access attempt.
4. Write the layered digest while reading, with citable findings, headline values, and verbatim quotes, then review, validate, and ingest it with `references/digest-schema.md`. Complete source summaries for capture runs created by the fetch.
5. Run `reading-check` for the papers, then return the requested content with source links, versions, evidence locators, and remaining limitations.
