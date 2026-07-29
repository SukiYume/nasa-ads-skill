---
description: "List, edit, annotate, share, transfer, combine, or delete NASA ADS libraries"
argument-hint: "[list|view|create|add|remove|update|delete|query-add|query-remove|permissions|grant|note-get|note-set|note-delete|transfer|operate] ..."
allowed-tools:
  - Bash
---

# NASA ADS Library Manager

Manage your NASA ADS libraries.

## Arguments

The subcommand and arguments: $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set `ADS_API_TOKEN` or `ADS_DEV_KEY`, and ask them to retry or provide a token for the current session. Never hardcode, print, or log the token. Avoid verbose HTTP output that can reveal request headers, and never use `-L` or `--location`.

2. Parse the subcommand from `$ARGUMENTS`:

### `list [--access all|owner|collaborator]` (default if no args)
List all user libraries:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries?sort=date_last_modified&order=desc&access_type=all"
```
Use only the documented `access_type` values `all`, `owner`, or `collaborator`. Display: name, id, num_documents, description, public/private, permission, and date_last_modified.

### `view <library_id>`
Get contents of a specific library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries/<library_id>?rows=20&fl=bibcode,title&notes=true"
```
The endpoint supports `start`, `rows`, `sort`, `fl`, `raw`, and `notes`. Display metadata and documents; use `raw=true` when the user needs the exact stored bibcodes.

### `create <name> [--desc "description"] [--public] [bibcodes...]`
Create a new library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/libraries" \
  -d '{"name":"<name>","description":"<desc>","public":<bool>,"bibcode":[...]}'
```

### `add <library_id> <bibcode1> [bibcode2] ...`
Add papers to a library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"bibcode":["bibcode1","bibcode2"],"action":"add"}'
```

### `remove <library_id> <bibcode1> [bibcode2] ...`
Remove papers from a library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"bibcode":["bibcode1","bibcode2"],"action":"remove"}'
```

### `update <library_id> [--name <name>] [--desc <description>] [--public true|false]`
Update library metadata:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X PUT "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"name":"<name>","description":"<desc>","public":true}'
```
Only include the fields the user wants to change.

### `delete <library_id>`
Delete the library record and its contents. Confirm with the user before executing:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -X DELETE "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>"
```

### `query-add <library_id> <query>` / `query-remove <library_id> <query>`
Add or remove papers matched by an ADS search query:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/query/<library_id>" \
  -d '{"params":{"q":"black holes","fq":"database:astronomy"},"action":"add"}'
```
Use `"action":"remove"` for `query-remove`. Include `start`, `rows`, or `sort` inside `params` if the user asks for them.

### `permissions <library_id>`
Show sharing permissions for a library:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/permissions/<library_id>"
```

### `grant <library_id> <email> [--read] [--write] [--admin]`
Grant or adjust permissions for another ADS user:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/permissions/<library_id>" \
  -d '{"email":"user@example.com","permission":{"read":true,"write":true}}'
```
Only include the permission keys the user wants to set.

### `note-get <library_id> <bibcode>`
Read the note attached to one document:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/notes/<library_id>/<bibcode>"
```

### `note-set <library_id> <bibcode> <content>`
Read the current note first. Use `POST` when none exists; use `PUT` to replace an existing note, with immediate confirmation before replacement:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/notes/<library_id>/<bibcode>" \
  -d '{"content":"Why this paper belongs in the library"}'
```

### `note-delete <library_id> <bibcode>`
Confirm immediately before deleting the note:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -X DELETE "https://api.adsabs.harvard.edu/v1/biblib/notes/<library_id>/<bibcode>"
```

### `transfer <library_id> <new-owner-email>`
Confirm immediately before transferring ownership:
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/transfer/<library_id>" \
  -d '{"email":"new-owner@example.com"}'
```

### `operate <library_id> <action> [secondary_ids...]`
Run library set operations (`union`, `intersection`, `difference`, `copy`, `empty`):
```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"
curl -fsS -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/libraries/operations/<library_id>" \
  -d '{"action":"union","libraries":["<secondary_id>"],"name":"Result Library"}'
```
Use `empty` with no `libraries` field. For `union`, `intersection`, and `difference`, include `name` and optionally `description` or `public`.

3. Confirm immediately before `delete`, `empty`, bulk `remove`/`query-remove`, `grant`, replacing or deleting a note, or transferring ownership. A command argument identifies the requested operation; the confirmation still protects destructive data changes and access.

4. Check the HTTP status and reject a top-level `Error` or `error` field before parsing. Present results clearly in markdown format and identify every mutation that ADS accepted.
