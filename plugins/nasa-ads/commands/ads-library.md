---
description: "List, view, create, update, share, combine, or delete NASA ADS libraries"
argument-hint: "[list | view <library_id> | create <name> | add <library_id> <bibcodes...> | remove <library_id> <bibcodes...> | update <library_id> [--name <name>] [--desc <description>] [--public true|false] | delete <library_id> | query-add <library_id> <query> | query-remove <library_id> <query> | permissions <library_id> | grant <library_id> <email> | operate <library_id> <action> [secondary_ids...]]"
allowed-tools:
  - Bash
---

# NASA ADS Library Manager

Manage your NASA ADS libraries.

## Arguments

The subcommand and arguments: $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, tell the user to create one at https://ui.adsabs.harvard.edu/#user/settings/token by signing in or registering, opening account settings > **API Token**, clicking **Generate a new key**, and saving it as `ADS_API_TOKEN` or `ADS_DEV_KEY`; then ask them to retry or provide a token for the current session.

2. Parse the subcommand from `$ARGUMENTS`:

### `list` (default if no args)
List all user libraries:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries?sort=date_last_modified&order=desc"
```
Display: name, id, num_documents, description, public/private, date_last_modified.

### `view <library_id>`
Get contents of a specific library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries/<library_id>"
```
Display metadata and list of bibcodes. Optionally search for paper details using the bibcodes.

### `create <name> [--desc "description"] [--public] [bibcodes...]`
Create a new library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/libraries" \
  -d '{"name":"<name>","description":"<desc>","public":<bool>,"bibcode":[...]}'
```

### `add <library_id> <bibcode1> [bibcode2] ...`
Add papers to a library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"bibcode":["bibcode1","bibcode2"],"action":"add"}'
```

### `remove <library_id> <bibcode1> [bibcode2] ...`
Remove papers from a library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"bibcode":["bibcode1","bibcode2"],"action":"remove"}'
```

### `update <library_id> [--name <name>] [--desc <description>] [--public true|false]`
Update library metadata:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X PUT "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"name":"<name>","description":"<desc>","public":true}'
```
Only include the fields the user wants to change.

### `delete <library_id>`
Delete the library itself, not just its contents. Confirm with the user before executing:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -X DELETE "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>"
```

### `query-add <library_id> <query>` / `query-remove <library_id> <query>`
Add or remove papers matched by an ADS search query:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/query/<library_id>" \
  -d '{"params":{"q":"black holes","fq":"database:astronomy"},"action":"add"}'
```
Use `"action":"remove"` for `query-remove`. Include `start`, `rows`, or `sort` inside `params` if the user asks for them.

### `permissions <library_id>`
Show sharing permissions for a library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/permissions/<library_id>"
```

### `grant <library_id> <email> [--read] [--write] [--admin]`
Grant or adjust permissions for another ADS user:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/permissions/<library_id>" \
  -d '{"email":"user@example.com","permission":{"read":true,"write":true}}'
```
Only include the permission keys the user wants to set.

### `operate <library_id> <action> [secondary_ids...]`
Run library set operations (`union`, `intersection`, `difference`, `copy`, `empty`):
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/libraries/operations/<library_id>" \
  -d '{"action":"union","libraries":["<secondary_id>"],"name":"Result Library"}'
```
Use `empty` with no `libraries` field. For `union`, `intersection`, and `difference`, include `name` and optionally `description` or `public`.

3. Present results clearly in markdown format, and explicitly label destructive operations such as `delete`.
