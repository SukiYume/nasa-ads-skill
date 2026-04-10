---
description: List, view, create, or manage NASA ADS libraries
argument-hint: [list | view <library_id> | create <name> | add <library_id> <bibcodes...> | remove <library_id> <bibcodes...>]
allowed-tools: [Bash, Read, Write]
---

# NASA ADS Library Manager

Manage your NASA ADS libraries.

## Arguments

The subcommand and arguments: $ARGUMENTS

## Instructions

1. Check for ADS API token in environment variable `ADS_API_TOKEN` or `ADS_DEV_KEY`. If not found, ask the user.

2. Parse the subcommand from `$ARGUMENTS`:

### `list` (default if no args)
List all user libraries:
```bash
curl -s -H "Authorization: Bearer $ADS_API_TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries?sort=date_last_modified&order=desc"
```
Display: name, id, num_documents, description, public/private, date_last_modified.

### `view <library_id>`
Get contents of a specific library:
```bash
curl -s -H "Authorization: Bearer $ADS_API_TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries/<library_id>"
```
Display metadata and list of bibcodes. Optionally search for paper details using the bibcodes.

### `create <name> [--desc "description"] [--public] [bibcodes...]`
Create a new library:
```bash
curl -s -H "Authorization: Bearer $ADS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/libraries" \
  -d '{"name":"<name>","description":"<desc>","public":<bool>,"bibcode":[...]}'
```

### `add <library_id> <bibcode1> [bibcode2] ...`
Add papers to a library:
```bash
curl -s -H "Authorization: Bearer $ADS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"bibcode":["bibcode1","bibcode2"],"action":"add"}'
```

### `remove <library_id> <bibcode1> [bibcode2] ...`
Remove papers from a library:
```bash
curl -s -H "Authorization: Bearer $ADS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/biblib/documents/<library_id>" \
  -d '{"bibcode":["bibcode1","bibcode2"],"action":"remove"}'
```

3. Present results clearly in markdown format.
