---
description: "List, view, create, update, share, combine, or delete NASA ADS libraries"
argument-hint: "[list | view <library_id> | create <name> | add <library_id> <bibcodes...> | remove <library_id> <bibcodes...> | update <library_id> [--name <name>] [--desc <description>] [--public true|false] | delete <library_id> | query-add <library_id> <query> | query-remove <library_id> <query> | permissions <library_id> | grant <library_id> <email> | operate <library_id> <action> [secondary_ids...]]"
allowed-tools:
  - Bash
---

# NASA ADS Library Manager

Manage ADS libraries with direct HTTP because these calls can change private or shared state.

## Arguments

The subcommand and arguments: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/libraries.md` completely.
2. Parse the requested subcommand, library IDs, bibcodes, query, metadata, and permission flags.
3. Follow the documented method, path, body, credential, and response rules. If the token is missing, direct the user to https://ui.adsabs.harvard.edu/#user/settings/token and ask them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`.
4. Confirm immediately before deleting or emptying a library, bulk removal, query-based removal, or a permission change. The command arguments do not replace confirmation.
5. Identify the exact read result or mutation accepted by ADS. Never report success from the request alone.
