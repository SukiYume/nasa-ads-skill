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

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/libraries.md` completely, together with the request rules it links in `references/http-fallback.md`.
2. Parse the subcommand, library IDs, bibcodes, query, metadata, note content, access type, email, and permission flags.
3. Confirm authorization before deleting or emptying a library, bulk or query-based removal, permission changes, replacing or deleting a note, or ownership transfer. An explicit request for the exact action and scope is authorization; otherwise prepare the concrete action and ask.
4. Report the exact read result or the mutation SciX accepted, verified from the response.
