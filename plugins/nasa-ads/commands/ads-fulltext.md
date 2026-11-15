---
description: "Read lawful full text for SciX bibcodes, DOIs, or arXiv IDs, or a PDF you supply, and store a digest of the whole article"
argument-hint: "<bibcode, DOI, or arXiv ID...> [local PDF or HTML file] [question about the paper]"
allowed-tools:
  - Bash
  - Read
  - Write
---

# SciX Full Text

Papers and question: $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md`; bundled scripts and references live under `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/`.

1. Parse the papers, versions, local files, and scientific question from `$ARGUMENTS`.
2. Apply the Reading Scope to each paper, loading the Local Lookup and Reading section of `references/literature-memory.md`, then `references/fulltext.md` for retrieval and reading, with its Import a Local Copy section for a local file, and `references/digest-schema.md` for the digest.
3. Run the verification step of Literature Research for these papers and return the result named in Completion and Handoff.
