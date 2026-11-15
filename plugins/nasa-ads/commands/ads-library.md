---
description: "List, edit, annotate, share, transfer, combine, or delete libraries in the SciX account"
argument-hint: "[list|view|create|add|remove|update|delete|query-add|query-remove|permissions|grant|note-get|note-set|note-delete|transfer|operate] ..."
allowed-tools:
  - Bash
  - Read
---

# SciX Library Manager

Subcommand and arguments: $ARGUMENTS

These are remote libraries in the SciX account. The personal local library uses `/nasa-ads:ads-memory`.

1. Read the Setup section of `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md`, then `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/libraries.md` completely, together with the request rules it links in `references/http-fallback.md`.
2. Parse the subcommand, library IDs, bibcodes, query, metadata, note content, access type, email, and permission flags.
3. Apply the Safety Boundaries of `libraries.md` before any mutation.
4. Report as its Results section specifies.
