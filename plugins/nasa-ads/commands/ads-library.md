---
description: "List, edit, annotate, share, transfer, combine, or delete NASA ADS libraries"
argument-hint: "[list|view|create|add|remove|update|delete|query-add|query-remove|permissions|grant|note-get|note-set|note-delete|transfer|operate] ..."
allowed-tools:
  - Bash
---

# NASA ADS Library Manager

Manage remote ADS libraries with the documented direct HTTP interface. Personal local collections use `ads-memory`.

## Arguments

The subcommand and arguments: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/libraries.md` completely.
2. Parse the requested subcommand, library IDs, bibcodes, query, metadata, note content, access type, email, and permission flags.
3. Follow the documented method, path, body, credential, and response rules. If the token is missing, direct the user to https://ui.adsabs.harvard.edu/#user/settings/token and ask them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`.
4. Check the user's authorization for deleting or emptying a library, bulk or query-based removal, a permission change, replacing or deleting a note, or transferring ownership. Existing explicit authorization covers the named action and scope. Obtain missing authorization after preparing a concrete, reviewable action.
5. Identify the exact read result or mutation accepted by ADS. Never report success from the request alone.
