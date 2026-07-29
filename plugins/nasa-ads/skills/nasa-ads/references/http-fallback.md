# Direct HTTP Fallback

Read this file only when Python 3 cannot run the bundled CLI or a requested non-library endpoint, option, or format is outside the CLI.

## Safety

- Read `ADS_API_TOKEN`, then `ADS_DEV_KEY`.
- Send the token only in `Authorization: Bearer <token>` to `https://api.adsabs.harvard.edu/v1`.
- Never print the token or place it in a URL, source file, or verbose HTTP trace.
- Use the current ADS documentation for an unsupported endpoint’s method and body.
- Treat `401`, `403`, `404`, `429`, and server failures as API results. Changing HTTP clients does not correct them.

## Credential Preflight

POSIX shell:

```bash
NASA_ADS_TOKEN="${ADS_API_TOKEN:-${ADS_DEV_KEY:-}}"
if [ -z "$NASA_ADS_TOKEN" ]; then
  echo "Set ADS_API_TOKEN or ADS_DEV_KEY, then retry." >&2
  exit 2
fi
```

PowerShell:

```powershell
$nasaAdsToken = if ($env:ADS_API_TOKEN) {
  $env:ADS_API_TOKEN
} else {
  $env:ADS_DEV_KEY
}

if (-not $nasaAdsToken) {
  throw 'Set ADS_API_TOKEN or ADS_DEV_KEY, then retry.'
}
```

## curl

Use `curl -fsS`. Add `-G` and `--data-urlencode` for every query parameter. Avoid `-v`.

```bash
curl -fsSG 'https://api.adsabs.harvard.edu/v1/search/query' \
  -H "Authorization: Bearer $NASA_ADS_TOKEN" \
  --data-urlencode 'q=title:"gravitational waves"' \
  --data-urlencode 'fl=bibcode,title,author,year,pub,doi,identifier,citation_count' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=citation_count desc'
```

For a JSON request, add `Content-Type: application/json`, set the documented method, and pass a valid JSON body:

```bash
curl -fsS 'https://api.adsabs.harvard.edu/v1/<documented-path>' \
  -H "Authorization: Bearer $NASA_ADS_TOKEN" \
  -H 'Content-Type: application/json' \
  -X POST \
  -d '<documented-json-body>'
```

## PowerShell

Encode every query parameter separately:

```powershell
$nasaAdsQuery = [uri]::EscapeDataString('title:"gravitational waves"')
$nasaAdsFields = [uri]::EscapeDataString(
  'bibcode,title,author,year,pub,doi,identifier,citation_count'
)
$nasaAdsSort = [uri]::EscapeDataString('citation_count desc')
$nasaAdsUri = "https://api.adsabs.harvard.edu/v1/search/query?q=$nasaAdsQuery&fl=$nasaAdsFields&rows=10&sort=$nasaAdsSort"

Invoke-RestMethod -Method Get -Uri $nasaAdsUri -Headers @{
  Authorization = "Bearer $nasaAdsToken"
}
```

For a JSON request, construct an object and convert it with sufficient depth:

```powershell
$nasaAdsBody = @{
  documented_field = @('documented-value')
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method Post `
  -Uri 'https://api.adsabs.harvard.edu/v1/<documented-path>' `
  -Headers @{ Authorization = "Bearer $nasaAdsToken" } `
  -ContentType 'application/json' `
  -Body $nasaAdsBody
```

## Response Handling

Check the HTTP status before parsing. Preserve the response’s actual shape and inspect rate-limit headers when quota matters. Report the fallback reason in the final method note.
