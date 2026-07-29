---
name: nasa-ads
description: Search and investigate NASA ADS astronomy and astrophysics literature. Use when a user asks to find papers, check whether a claim or topic appears in published literature, retrieve titles/authors/abstracts/DOIs/arXiv IDs, export BibTeX or other citations, manage ADS libraries, inspect citation metrics, find related papers, or resolve full-text and data links. Trigger on terms such as paper, literature, citation, bibliography, BibTeX, arXiv, ADS, published, related work, references, library, h-index, astronomy, and astrophysics, plus Chinese requests including 文献, 论文, 查文献, 查论文, 文献调研, 论文调研, 论文检索, 有没有人发表, 有没有文献提到, 是否有相关论文, 已有研究, 引用导出, 获取 BibTeX, ADS 文献, arXiv 论文, 天文文献, 天文论文, and 天体物理论文.
---

# NASA ADS

Use the NASA Astrophysics Data System Developer API for literature search, metadata retrieval, citation export, library management, bibliometrics, related-paper discovery, and resource-link resolution.

## Core Rules

1. Check `ADS_API_TOKEN`, then `ADS_DEV_KEY`, before every workflow.
2. Stop and give the token setup steps below when both variables are absent.
3. Treat the token as a secret. Never print it, log it, commit it, store it in a source file, or place it in a URL.
4. Use `https://api.adsabs.harvard.edu/v1` as the API base and send `Authorization: Bearer <token>` in the request header.
5. URL-encode every search parameter. ADS queries and bibcodes can contain `&`, spaces, quotes, parentheses, and other reserved characters.
6. Check the HTTP status before parsing a response. Surface a concise error and corrective action when a request fails.
7. Keep research calls read-only by default. Confirm immediately before library deletion, library emptying, bulk removal, permission changes, or another destructive/shared-library operation.
8. Describe an empty search as “no matching records found for these queries.” A single query cannot establish that no relevant literature exists.
9. Use the official [ADS API documentation](https://ui.adsabs.harvard.edu/help/api/) for endpoints outside the workflows covered here.

## Operating Workflow

1. Translate the request into one or more focused ADS queries or endpoint calls.
2. Run the credential preflight without displaying the credential.
3. Use an HTTP client already available on the system: `curl`, PowerShell `Invoke-RestMethod`, or Python’s standard library.
4. Request only the fields and row count needed for the task.
5. Inspect response status, response shape, pagination, and rate-limit headers when relevant.
6. For literature research, refine weak queries, deduplicate by bibcode, inspect abstracts, and distinguish direct evidence from adjacent work.
7. Return a reader-facing synthesis with links and a short search-method note. Avoid raw JSON dumps unless the user requests them.

## Token Setup

When neither supported variable is set, tell the user to:

1. Open [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token).
2. Register for ADS or sign in.
3. Open account settings and choose **API Token** if the direct link lands elsewhere.
4. Select **Generate a new key**.
5. Copy the token and keep it private.
6. Set it for the current terminal session:

```bash
export ADS_API_TOKEN='paste-your-token-here'
```

```powershell
$env:ADS_API_TOKEN = 'paste-your-token-here'
```

7. Retry the request in that terminal, or restart the host assistant after setting a persistent user environment variable.

If the user provides a token for the current session, keep it in process memory only and avoid commands that echo command lines or headers.

### Safe Credential Preflight

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

## HTTP Request Patterns

Prefer `curl -fsS` on POSIX shells. Use `-G` with `--data-urlencode` for search parameters. Avoid `curl -v` because verbose output can reveal the authorization header.

```bash
curl -fsSG 'https://api.adsabs.harvard.edu/v1/search/query' \
  -H "Authorization: Bearer $NASA_ADS_TOKEN" \
  --data-urlencode 'q=title:"gravitational waves"' \
  --data-urlencode 'fl=bibcode,title,author,year,pub,doi,identifier,citation_count' \
  --data-urlencode 'rows=10' \
  --data-urlencode 'sort=citation_count desc'
```

Use `Invoke-RestMethod` in PowerShell:

```powershell
$nasaAdsQuery = [uri]::EscapeDataString('title:"gravitational waves"')
$nasaAdsFields = [uri]::EscapeDataString(
  'bibcode,title,author,year,pub,doi,identifier,citation_count'
)
$nasaAdsUri = "https://api.adsabs.harvard.edu/v1/search/query?q=$nasaAdsQuery&fl=$nasaAdsFields&rows=10"

Invoke-RestMethod -Method Get -Uri $nasaAdsUri -Headers @{
  Authorization = "Bearer $nasaAdsToken"
}
```

Use `urllib.request` when Python is the only available client. Keep the implementation within the standard library so a fresh system does not require `requests`.

## 1. Search

### Endpoint

```text
GET /search/query
```

### Main Parameters

| Parameter | Purpose |
|---|---|
| `q` | Required ADS query |
| `fl` | Comma-separated return fields; ADS otherwise returns only `id` |
| `rows` | Results per page; default 10, maximum 2000 |
| `start` | Pagination offset |
| `sort` | Sort expression such as `date desc` or `citation_count desc` |
| `fq` | Filter query such as `database:astronomy`, `property:refereed`, or `doctype:article` |

Use this practical field set:

```text
bibcode,title,author,abstract,year,pub,doi,identifier,citation_count,read_count,property,doctype
```

Useful query forms:

```text
author:"Einstein, A"                         exact author
author:"^Einstein, A"                        first author
title:"gravitational waves"                  title phrase
abs:"dark matter"                            abstract
full:"machine learning"                      full text
bibcode:2016PhRvL.116f1102A                  bibcode
arxiv:1602.03837                             arXiv ID
doi:10.1103/PhysRevLett.116.061102           DOI
year:2020-2024                               year range
object:M31                                   astronomical object
bibstem:ApJ                                  journal abbreviation
orcid:0000-0002-1825-0097                    ORCID
citations(bibcode:2016PhRvL.116f1102A)       citing papers
references(bibcode:2016PhRvL.116f1102A)      cited references
trending(exoplanets)                         trending papers
useful(bibcode:2016PhRvL.116f1102A)          useful papers
similar(bibcode:2016PhRvL.116f1102A)         similar papers
```

Pass `fq` separately from `q`. Apply it only when the user requests that restriction or it clearly improves the research task.

### Literature-Research Query Ladder

For a topic review or published-claim check:

1. Search the key phrase in `title:` and `abs:`.
2. Search synonyms, abbreviations, spelling variants, author names, and relevant astronomical objects.
3. Add year, refereed-status, collection, or document-type filters when useful.
4. Review both recent results (`date desc`) and influential results (`citation_count desc`).
5. Page beyond the first ten results when the result set or user request requires it.
6. Deduplicate on `bibcode`; treat alternate bibcodes as versions of the same work when appropriate.
7. Read abstracts before describing a paper as evidence for the claim.
8. State the exact query families and material limits when reporting a negative search result.

### Batch Bibcode Lookup

Use big query for up to 2000 bibcodes:

```text
POST /search/bigquery?q=*:*&fl=bibcode,title&rows=2000&fq={!bitset}
Content-Type: big-query/csv
```

Request body:

```text
bibcode
1907AN....174...59.
1908PA.....16..445.
```

## 2. Citation Export

Use `GET` for one bibcode and `POST` for multiple bibcodes:

```text
GET  /export/<format>/<bibcode>
POST /export/<format>
```

Single-record `GET` responses contain raw citation text. Multi-record `POST` responses contain JSON with an `export` field.

```json
{"bibcode":["2016PhRvL.116f1102A","2017ApJ...848L..12A"],"sort":"first_author asc"}
```

Supported standard formats:

| Group | Formats |
|---|---|
| BibTeX/tagged | `bibtex`, `bibtexabs`, `ads`, `endnote`, `procite`, `ris`, `refworks`, `medlars` |
| LaTeX | `aastex`, `icarus`, `mnras`, `soph` |
| XML/feed | `dcxml`, `refxml`, `refabsxml`, `votable`, `rss` |
| Other | `ieee` |

Return citation exports in a fenced code block. Offer an appropriate extension such as `.bib` or `.ris` when the user wants a file.

## 3. Libraries

Use the library ID returned by ADS; a library name is not an endpoint identifier.

| Task | Method and path | Body or notes |
|---|---|---|
| List libraries | `GET /biblib/libraries` | Supports `start`, `rows`, `sort`, `order` |
| View library | `GET /biblib/libraries/<id>` | Add `raw=true` for exact stored bibcodes |
| Create library | `POST /biblib/libraries` | `name`, `description`, `public`, `bibcode[]` |
| Add/remove papers | `POST /biblib/documents/<id>` | `{"bibcode":[...],"action":"add"}` or `remove` |
| Update metadata | `PUT /biblib/documents/<id>` | Include only changed fields |
| Delete library | `DELETE /biblib/documents/<id>` | Confirm immediately before the call |
| Add/remove by query | `POST /biblib/query/<id>` | `params` plus `action` |
| Set operations | `POST /biblib/libraries/operations/<id>` | `union`, `intersection`, `difference`, `copy`, `empty` |
| View permissions | `GET /biblib/permissions/<id>` | Read-only |
| Change permissions | `POST /biblib/permissions/<id>` | `email` plus changed `read`/`write`/`admin` flags |

Confirm immediately before:

- deleting a library;
- emptying a library;
- bulk-removing documents;
- granting, revoking, or changing another user’s permissions.

For `union`, `intersection`, and `difference`, provide a result-library name when the user supplied one. For `copy`, identify the secondary destination library. For `empty`, omit `libraries`.

## 4. Metrics

```text
POST /metrics
```

```json
{
  "bibcodes": ["2016PhRvL.116f1102A"],
  "types": ["basic", "citations", "indicators"]
}
```

Available type values are `basic`, `citations`, `indicators`, `histograms`, and `timeseries`.

The response uses keys containing spaces, including:

- `basic stats`
- `basic stats refereed`
- `citation stats`
- `citation stats refereed`
- `indicators`
- `indicators refereed`

Read the returned keys before formatting the result. Report the denominator and paper set for aggregate metrics. Avoid presenting an h-index from a small arbitrary subset as an author-level h-index.

## 5. Suggested and Related Papers

Suggest potentially missing citations:

```text
POST /citation_helper
{"bibcodes":["2016PhRvL.116f1102A"]}
```

The response is an array of suggestions. Present title, author, bibcode, and score when available. Describe the result as an algorithmic suggestion, then assess topical relevance from metadata or abstract before recommending it.

Find related records through search:

```text
q=similar(bibcode:2016PhRvL.116f1102A)
q=useful(bibcode:2016PhRvL.116f1102A)
```

## 6. Full Text and Data Links

```text
GET /resolver/<bibcode>
GET /resolver/<bibcode>/<link_type>
```

Common link types include `esource`, `data`, `citations`, `references`, and `associated`. Resolver results can include publisher pages, arXiv, ADS scans, and archives such as SIMBAD, NED, VizieR, MAST, HEASARC, Zenodo, and GitHub.

Prefer a lawful open-access or author-posted link when several full-text sources are available. Never imply that a resolver link guarantees free access.

## Result Presentation

For literature results, include:

1. A concise answer to the user’s question.
2. A table or list with title, first authors, year, venue, citation count, and bibcode.
3. Clickable ADS links in the form `https://ui.adsabs.harvard.edu/abs/<bibcode>`.
4. DOI links and arXiv links when present.
5. A thematic synthesis for multi-paper research.
6. A search-method note with query families, filters, sorting, pagination, and the search date when completeness matters.
7. A calibrated limitation statement for sparse or negative results.

Extract an arXiv link by finding an `identifier` entry beginning with `arXiv:` and appending the remaining ID to `https://arxiv.org/abs/`.

## Errors and Rate Limits

| Symptom | Response |
|---|---|
| `401 Unauthorized` | Confirm that a current token exists and the header begins with `Bearer ` |
| `403 Forbidden` | Check account/library permissions and the requested operation |
| `404 Not Found` | Recheck bibcode, library ID, endpoint, and URL encoding |
| `429 Too Many Requests` | Read `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`; wait until reset |
| Only `id` is returned | Add the required fields to `fl` |
| Empty citation/reference arrays | Request `citation` or `reference` explicitly in `fl` |
| Query breaks at `&` | Pass the query through `--data-urlencode` or an equivalent encoder |
| Empty result set | Check syntax, remove unnecessary filters, try synonyms, and report the searched forms |

ADS rate limits are endpoint-specific and may change. Use response headers as the current source of truth.
