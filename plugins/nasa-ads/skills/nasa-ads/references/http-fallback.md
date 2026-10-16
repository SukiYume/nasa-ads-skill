# Direct HTTP Fallback

Read this file only when Python 3 cannot run the bundled CLI or a requested non-library endpoint, option, or format is outside the CLI.

## Safety

- Read `ADS_API_TOKEN`.
- Send the token only in `Authorization: Bearer <token>` to `https://api.scixplorer.org/v1`.
- Reject redirects for authenticated requests.
- Never print the token or place it in a URL, source file, or verbose HTTP trace.
- Use the current [SciX API documentation](https://scixplorer.org/scixhelp/api/) for an unsupported endpoint’s method and body.
- Treat `401`, `403`, `404`, `429`, and server failures as API results. Changing HTTP clients does not correct them.
- Treat a top-level `Error` or `error` response as a failed operation even when the HTTP status is `200`.

When Python is available for a fallback endpoint, apply [screening before capture](literature-memory.md#screening-before-capture), save retained paper metadata, and use `literature_db.py capture --results <file>` with [source-summary completion](literature-memory.md#automatic-capture-and-summary-completion). Include abstracts in metadata requests when available. Apply the shared [Core Invariants](../SKILL.md#core-invariants), including reading scope and the no-library-write exception. When Python is unavailable, preserve screened responses and authored summaries for later import and follow [failure routing](../SKILL.md#failure-routing) for unavailable persistence.

## Credential Preflight

POSIX shell:

```bash
if [ -z "${ADS_API_TOKEN:-}" ]; then
  echo "Set ADS_API_TOKEN, then retry." >&2
  exit 2
fi
```

PowerShell:

```powershell
if (-not $env:ADS_API_TOKEN) {
  throw 'Set ADS_API_TOKEN, then retry.'
}
```

## curl

Use `curl -fsS`. Add `-G` and `--data-urlencode` for every query parameter. Avoid `-v`, `-L`, and `--location`.

```bash
curl -fsSG 'https://api.scixplorer.org/v1/search/query' \
  -H "Authorization: Bearer $ADS_API_TOKEN" \
  --data-urlencode 'q=title:"gravitational waves"' \
  --data-urlencode 'fl=bibcode,title,author,year,pub,doi,identifier,citation_count' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=citation_count desc'
```

For a JSON request, add `Content-Type: application/json`, set the documented method, and pass a valid JSON body:

```bash
curl -fsS 'https://api.scixplorer.org/v1/<documented-path>' \
  -H "Authorization: Bearer $ADS_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -X POST \
  -d '<documented-json-body>'
```

## PowerShell

Encode every query parameter separately:

```powershell
$scixQuery = [uri]::EscapeDataString('title:"gravitational waves"')
$scixFields = [uri]::EscapeDataString(
  'bibcode,title,author,year,pub,doi,identifier,citation_count'
)
$scixSort = [uri]::EscapeDataString('citation_count desc')
$scixUri = "https://api.scixplorer.org/v1/search/query?q=$scixQuery&fl=$scixFields&rows=10&sort=$scixSort"

Invoke-RestMethod `
  -Method Get `
  -Uri $scixUri `
  -Headers @{ Authorization = "Bearer $env:ADS_API_TOKEN" } `
  -MaximumRedirection 0
```

For a JSON request, construct an object and convert it with sufficient depth:

```powershell
$scixBody = @{
  documented_field = @('documented-value')
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method Post `
  -Uri 'https://api.scixplorer.org/v1/<documented-path>' `
  -Headers @{ Authorization = "Bearer $env:ADS_API_TOKEN" } `
  -ContentType 'application/json' `
  -Body $scixBody `
  -MaximumRedirection 0
```

## Response Handling

Check the HTTP status before parsing, then reject a top-level `Error` or `error` field. Preserve the response’s actual shape and inspect rate-limit headers when quota matters. Report the fallback reason in the final method note.
