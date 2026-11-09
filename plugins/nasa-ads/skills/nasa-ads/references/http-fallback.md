# Direct HTTP Fallback

Load this reference when Python cannot run the bundled CLI, when a requested bibliographic endpoint, option, or format is outside the CLI, or for [SciX Libraries](libraries.md), which share these request rules. Other account services stay outside the skill, as [Setup](../SKILL.md#setup) states.

## Safety

- Read `ADS_API_TOKEN`.
- Send the token only in `Authorization: Bearer <token>` to `https://api.scixplorer.org/v1`.
- Reject redirects for authenticated requests.
- Never print the token or place it in a URL, source file, or verbose HTTP trace.
- Find a bibliographic endpoint’s method and body in the machine-readable [OpenAPI specification](https://github.com/adsabs/adsabs-dev-api/tree/master/openapi), whose `services/*.yaml` files describe each service, or in the [SciX API documentation](https://scixplorer.org/scixhelp/api/). Paths are relative to `https://api.scixplorer.org/v1`.
- Treat `401`, `403`, `404`, `429`, and server failures as API results. Changing HTTP clients does not correct them.
- Treat a top-level `Error` or `error` response as a failed operation even when the HTTP status is `200`.

Paper metadata retrieved this way still enters the library. When Python is available, apply [screening before capture](literature-memory.md#screening-before-capture), request abstracts, save the retained records, and run `literature_db.py capture --results <file>` followed by [summary completion](literature-memory.md#automatic-capture-and-summary-completion). When Python is unavailable, keep screened responses and authored summaries for later import, and report full-text preparation, storage, and Web browsing as unavailable per [failure routing](../SKILL.md#failure-routing).

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
