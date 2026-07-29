# ADS Libraries

Use direct HTTP for library operations:

- Resolve `ADS_API_TOKEN`, then `ADS_DEV_KEY`; stop with the token-settings link from `SKILL.md` if both are absent.
- Send the token only as `Authorization: Bearer <token>` to `https://api.adsabs.harvard.edu/v1`.
- Use an available system client, URL-encode query parameters, send documented JSON bodies, and check the HTTP response before interpreting it.
- Never print the token, use verbose HTTP tracing, or change semantics after an API failure.

## Safety Boundaries

Keep read-only calls as the default. Confirm immediately before:

- deleting or emptying a library;
- bulk removal or query-based removal;
- granting, revoking, or changing another user’s permissions.

A command argument identifies the requested action and does not replace this confirmation.

Use the library ID returned by ADS. A library name is not an endpoint identifier.

## Operations

| Task | Method and path | Body or notes |
|---|---|---|
| List libraries | `GET /biblib/libraries` | Optional `start`, `rows`, `sort`, `order` |
| View a library | `GET /biblib/libraries/<id>` | Add `raw=true` for exact stored bibcodes |
| Create a library | `POST /biblib/libraries` | `name`, `description`, `public`, `bibcode` |
| Add or remove papers | `POST /biblib/documents/<id>` | `bibcode` plus `action` |
| Update metadata | `PUT /biblib/documents/<id>` | Include only changed fields |
| Delete a library | `DELETE /biblib/documents/<id>` | Confirm immediately before the call |
| Add or remove by query | `POST /biblib/query/<id>` | `params` plus `action` |
| Set operations | `POST /biblib/libraries/operations/<id>` | See the rules below |
| View permissions | `GET /biblib/permissions/<id>` | Read-only |
| Change permissions | `POST /biblib/permissions/<id>` | `email` plus changed permission flags |

Create:

```json
{
  "name": "Reading List",
  "description": "Optional description",
  "public": false,
  "bibcode": ["2016PhRvL.116f1102A"]
}
```

Add or remove papers:

```json
{
  "bibcode": ["2016PhRvL.116f1102A"],
  "action": "add"
}
```

Use `"action": "remove"` only after applying the confirmation rule when the removal is bulk.

Add or remove by query:

```json
{
  "params": {
    "q": "black holes",
    "fq": "database:astronomy"
  },
  "action": "add"
}
```

Include documented `start`, `rows`, or `sort` inside `params` when requested.

Change permissions:

```json
{
  "email": "user@example.com",
  "permission": {
    "read": true,
    "write": true
  }
}
```

Include only permission flags the user requested.

Set operations:

```json
{
  "action": "union",
  "libraries": ["secondary-library-id"],
  "name": "Combined Library"
}
```

- `union`, `intersection`, and `difference` create a result library; include a unique `name` when the user supplied one.
- `copy` sets `libraries` to one destination library ID. ADS appends the primary library’s contents without emptying the destination.
- `empty` omits `libraries` and requires immediate confirmation.

## Results

For reads, present library metadata and requested documents or permissions. For mutations, identify the exact operation ADS accepted and any returned library ID. Never imply success from the request alone; verify the response.
