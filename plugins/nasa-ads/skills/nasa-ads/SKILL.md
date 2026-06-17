---
name: nasa-ads
description: Use when the user asks to search NASA ADS or astronomy/astrophysics literature, check whether something has been published or mentioned in the literature, verify published claims, retrieve paper metadata (title, authors, abstract, arxiv ID, DOI), export BibTeX or other citations, manage ADS libraries, get citation metrics, find related/recommended papers, or query NASA ADS (Astrophysics Data System). Triggers on English terms and intents such as "paper", "literature", "citation", "bibtex", "arxiv", "ADS", "bibliography", "astrophysics", "published", "mentioned in the literature", "related work", "library", "h-index", and "references"; also use for Chinese requests such as "文献", "论文", "查一下文献", "有没有人发表", "有没有文献提到", "是否有相关论文", "已有研究", "文献调研", "论文调研", "论文检索", "查论文", "查文献", "引用导出", "获取 BibTeX", "ADS 文献", "arXiv 论文", "天文文献", "天文论文", and "天体物理论文".
---

# NASA ADS API Skill Reference

Focused reference for practical NASA Astrophysics Data System literature research workflows. Use it to find papers, inspect metadata, build reading lists, export citations, check metrics, and retrieve related-paper or full-text/data links.

This is not a complete ADS API manual. If the user asks for an ADS capability not covered here, first solve it with the documented search/export/library/metrics/resolver workflows when possible, then consult the official ADS API documentation.

## Operating Workflow

1. Check `ADS_API_TOKEN`, then `ADS_DEV_KEY`; if neither exists, tell the user how to create and set an ADS API token before asking them to retry or provide a token for the current session.
2. Translate the user request into the narrowest ADS query or endpoint call.
3. URL-encode search parameters with `urlencode()` or `curl -G --data-urlencode`.
4. Present research results with title, authors, year, venue, citation count, ADS URL, DOI, and arXiv URL when available.
5. For literature research, summarize the result set by themes, recency, venue, and highly cited papers. Avoid raw JSON dumps.
6. Confirm before destructive library operations such as delete, empty, or bulk remove.

## Prerequisites

- ADS API token from https://ui.adsabs.harvard.edu/#user/settings/token
- Header: `Authorization: Bearer <token>`
- Base URL: `https://api.adsabs.harvard.edu/v1`

**Check environment variables `ADS_API_TOKEN` or `ADS_DEV_KEY` first.** If not found, use the setup steps below before asking the user to retry or provide a token for the current session. Never hardcode or log it.

When a token is missing, give the user these setup steps:

1. Open https://ui.adsabs.harvard.edu/#user/settings/token.
2. Register or sign in to ADS.
3. If the direct link does not open the token page, go to account settings and choose **API Token**.
4. Click **Generate a new key**.
5. Copy the token and keep it private.
6. Save it as `ADS_API_TOKEN` or `ADS_DEV_KEY`, then restart the terminal or assistant session.

---

## 1. Search API

### Endpoint

```
GET /search/query?q=<query>&fl=<fields>&rows=<N>&sort=<field>+<dir>
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `q` | Search query (required). Supports: `author:`, `title:`, `abs:`, `bibcode:`, `doi:`, `arxiv:`, `year:`, `object:`, `full:` (full text) |
| `fl` | Comma-separated return fields (default: `id` only) |
| `rows` | Number of results (default: 10, max: 2000) |
| `start` | Offset for pagination |
| `sort` | Sort field + direction, e.g. `citation_count desc`, `date desc`, `read_count desc` (`+` = space in URL) |
| `fq` | Filter query, e.g. `database:astronomy`, `property:refereed`, `doctype:article` |

### Available Fields (`fl=`)

| Field | Type | Description |
|-------|------|-------------|
| `bibcode` | string | Canonical ADS bibcode |
| `title` | array | Paper title |
| `author` | array | Author names |
| `abstract` | string | Abstract text |
| `year` | string | Publication year |
| `pub` | string | Journal/publication name |
| `doi` | array | Digital object identifier |
| `identifier` | array | All IDs (bibcodes, DOIs, arxiv IDs) |
| `citation_count` | int | Number of citations |
| `read_count` | int | Number of reads |
| `keyword` | array | Keywords |
| `aff` | array | Author affiliations |
| `first_author` | string | First author name |
| `property` | array | Properties: REFEREED, OPENACCESS, etc. |
| `doctype` | string | Document type: article, eprint, inproceedings, etc. |
| `alternate_bibcode` | array | Alternate bibcodes (e.g. arXiv version) |
| `data` | array | Data sources linked to this paper |
| `citation` | array | Bibcodes of papers that cite this one |
| `reference` | array | Bibcodes of papers referenced by this one |

### Typical Field Set

```
fl=bibcode,title,author,abstract,year,pub,doi,identifier,citation_count
```

### Query Syntax

```
q=author:"Einstein, A"                        # exact author
q=author:"^Einstein, A"                       # first author only
q=title:"gravitational waves"                 # title search
q=abs:"dark matter"                           # abstract search
q=full:"machine learning"                     # full text search
q=bibcode:2016PhRvL.116f1102A                 # exact bibcode
q=arxiv:1602.03837                            # by arxiv ID
q=doi:10.1103/PhysRevLett.116.061102          # by DOI
q=year:2020                                   # specific year
q=year:2020-2024                              # year range
q=object:M31                                  # astronomical object
q=black+holes&fq=database:astronomy           # with database filter
q=author:"Spergel, D"&fq=property:refereed    # refereed only
q=bibstem:"ApJ"                               # by journal abbreviation
q=orcid:0000-0000-0000-0000                   # by ORCID
q=citations(bibcode:2016PhRvL.116f1102A)      # papers citing a paper
q=references(bibcode:2016PhRvL.116f1102A)     # references of a paper
q=trending(exoplanets)                        # trending papers
q=useful(bibcode:2016PhRvL.116f1102A)         # useful/related papers
q=similar(bibcode:2016PhRvL.116f1102A)        # similar papers
```

These are raw ADS query values. When calling `/search/query`, URL-encode them with `urlencode()` or `curl -G --data-urlencode`; bibcodes such as `2012A&A...542A..16R` contain `&` and will fail if interpolated directly into a URL.

Operators: `+` (AND), `OR`, `-` (NOT), `""` (exact phrase), `*` (wildcard).

### Big Query (Batch Lookup)

Look up up to 2000 bibcodes at once:

```
POST /search/bigquery?q=*:*&fl=bibcode,title&rows=2000&fq={!bitset}
Content-Type: big-query/csv
Body:
bibcode
1907AN....174...59.
1908PA.....16..445.
```

---

## 2. Export API

### Endpoints

**Single bibcode:** `GET /export/<format>/<bibcode>`

**Multiple bibcodes:** `POST /export/<format>`

Single-bibcode GET exports return raw text in the requested format. Multi-bibcode POST exports return JSON with an `export` field.

```json
{"bibcode": ["<bibcode1>", "<bibcode2>"], "sort": "first_author asc"}
```

### Supported Formats

| Format | Endpoint | Use Case |
|--------|----------|----------|
| `bibtex` | `/export/bibtex` | Standard BibTeX |
| `bibtexabs` | `/export/bibtexabs` | BibTeX + abstract |
| `ads` | `/export/ads` | ADS generic tagged format |
| `aastex` | `/export/aastex` | AASTeX (LaTeX) |
| `mnras` | `/export/mnras` | MNRAS style |
| `icarus` | `/export/icarus` | Icarus style |
| `soph` | `/export/soph` | Solar Physics |
| `endnote` | `/export/endnote` | EndNote |
| `ris` | `/export/ris` | RIS/Refman |
| `refworks` | `/export/refworks` | RefWorks |
| `medlars` | `/export/medlars` | MEDLARS |
| `procite` | `/export/procite` | ProCite |
| `ieee` | `/export/ieee` | IEEE format |
| `votable` | `/export/votable` | VOTable XML |
| `dcxml` | `/export/dcxml` | Dublin Core XML |
| `refxml` | `/export/refxml` | REF-XML |
| `refabsxml` | `/export/refabsxml` | REFABS-XML |
| `rss` | `/export/rss` | RSS feed XML |

---

## 3. Libraries API

Manage personal and shared paper collections.

### List All Libraries

```
GET /biblib/libraries?start=0&rows=100&sort=date_last_modified&order=desc
```

Returns: `libraries[]` with `name`, `id`, `description`, `num_documents`, `public`, `permission`, `date_created`, `date_last_modified`.

### Get Library Contents

```
GET /biblib/libraries/<library_id>
```

Returns: `documents[]` (bibcode list), `metadata`, `solr` (search results).

Add `?raw=true` to get exact bibcodes even if not in ADS.

### Create Library

```
POST /biblib/libraries
{"name": "My Library", "description": "...", "public": false, "bibcode": ["bibcode1", "bibcode2"]}
```

### Add/Remove Papers

```
POST /biblib/documents/<library_id>
{"bibcode": ["bibcode1", "bibcode2"], "action": "add"}    # or "remove"
```

### Add Papers by Query

```
POST /biblib/query/<library_id>
{"params": {"q": "black holes", "fq": "database:astronomy"}, "action": "add"}
```

Or via GET: `GET /biblib/query/<library_id>?q=black+holes`

### Update Library Metadata

```
PUT /biblib/documents/<library_id>
{"name": "New Name", "description": "New desc", "public": true}
```

### Delete Library

```
DELETE /biblib/documents/<library_id>
```

### Library Set Operations

```
POST /biblib/libraries/operations/<primary_library_id>
{"action": "union", "libraries": ["<secondary_id>"], "name": "Result Library"}
```

Supported actions: `union`, `intersection`, `difference`, `copy`, `empty`.

### Permissions

```
GET /biblib/permissions/<library_id>
POST /biblib/permissions/<library_id>
{"email": "user@example.com", "permission": {"read": true, "write": true}}
```

Roles: `owner` > `admin` > `write` > `read`. Public libraries are readable by all.

---

## 4. Metrics API

Get citation statistics, h-index, and other bibliometric indicators.

```
POST /metrics
{"bibcodes": ["bibcode1", "bibcode2"], "types": ["basic", "citations", "indicators"]}
```

### Available Metric Types

| Type | Returns |
|------|---------|
| `basic` | Publication count, usage stats, normalized counts |
| `citations` | Citation stats (total, self, refereed, normalized) |
| `indicators` | h-index, g-index, i10-index, m-index, tori, riq, read10 |
| `histograms` | Citation/read/publication histograms over time |
| `timeseries` | Time series for h-index, g-index, etc. |

---

## 5. Citation Helper

Suggest missing citations using "friends of friends" analysis.

```
POST /citation_helper
{"bibcodes": ["bibcode1", "bibcode2"]}
```

Returns up to 10 suggested papers with `bibcode`, `title`, `author`, `score`.

---

## 6. Resolver (Links to External Resources)

Get links to full text, data, and other external resources.

```
GET /resolver/<bibcode>              # all available links
GET /resolver/<bibcode>/esource      # full text sources
GET /resolver/<bibcode>/data         # data links
GET /resolver/<bibcode>/citations    # citation links
GET /resolver/<bibcode>/references   # reference links
GET /resolver/<bibcode>/associated   # associated articles
```

Full text link types: `pub_pdf`, `eprint_pdf`, `pub_html`, `eprint_html`, `ads_scan`.

Data link types include: `simbad`, `ned`, `vizier`, `chandra`, `mast`, `heasarc`, `jwst`, `zenodo`, `github`, and many more.

---

## 7. Extracting arXiv Link

The `identifier` field contains arxiv IDs:
1. Find entry matching `arXiv:XXXX.XXXXX` in the `identifier` array
2. Construct: `https://arxiv.org/abs/<id>`

ADS abstract page: `https://ui.adsabs.harvard.edu/abs/<bibcode>`

---

## Implementation Pattern (Python)

```python
import os, requests, json
from urllib.parse import urlencode

token = os.environ.get("ADS_API_TOKEN") or os.environ.get("ADS_DEV_KEY") or "<user_token>"
headers = {"Authorization": f"Bearer {token}"}
BASE = "https://api.adsabs.harvard.edu/v1"

# Search
params = urlencode({
    "q": 'author:"Einstein" title:"relativity"',
    "fl": "bibcode,title,author,abstract,year,doi,identifier,citation_count",
    "rows": 10,
    "sort": "citation_count desc"
})
r = requests.get(f"{BASE}/search/query?{params}", headers=headers)
docs = r.json()["response"]["docs"]

# Extract info
for doc in docs:
    title = doc.get("title", [""])[0]
    authors = ", ".join(doc.get("author", []))
    abstract = doc.get("abstract", "")
    bibcode = doc.get("bibcode", "")
    doi = doc.get("doi", [""])[0] if doc.get("doi") else ""
    arxiv_id = next((i for i in doc.get("identifier", []) if "arXiv:" in i), "")
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id.replace('arXiv:', '')}" if arxiv_id else ""
    ads_url = f"https://ui.adsabs.harvard.edu/abs/{bibcode}"

# Get BibTeX
bibcodes = [d["bibcode"] for d in docs]
r = requests.post(f"{BASE}/export/bibtex", headers=headers,
                   data=json.dumps({"bibcode": bibcodes}))
bibtex = r.json()["export"]

# List user libraries
r = requests.get(f"{BASE}/biblib/libraries", headers=headers)
libraries = r.json()["libraries"]

# Get library contents
lib_id = libraries[0]["id"]
r = requests.get(f"{BASE}/biblib/libraries/{lib_id}", headers=headers)
lib_bibcodes = r.json()["documents"]

# Get metrics
r = requests.post(f"{BASE}/metrics", headers=headers,
                   data=json.dumps({"bibcodes": bibcodes, "types": ["indicators"]}))
indicators = r.json()["indicators"]

# Citation helper
r = requests.post(f"{BASE}/citation_helper", headers=headers,
                   data=json.dumps({"bibcodes": bibcodes}))
suggestions = r.json()
```

## Implementation Pattern (curl)

```bash
TOKEN="${ADS_API_TOKEN:-$ADS_DEV_KEY}"

# Search
curl -sG "https://api.adsabs.harvard.edu/v1/search/query" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'q=author:"Einstein"' \
  --data-urlencode 'fl=bibcode,title,author' \
  --data-urlencode 'rows=5'

# Export BibTeX (single, GET)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/export/bibtex/2016PhRvL.116f1102A"

# Export BibTeX (multiple, POST)
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/export/bibtex" \
  -d '{"bibcode":["2016PhRvL.116f1102A","2017ApJ...848L..12A"]}'

# List libraries
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries"

# Get library contents
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.adsabs.harvard.edu/v1/biblib/libraries/<library_id>"

# Metrics
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.adsabs.harvard.edu/v1/metrics" \
  -d '{"bibcodes":["2016PhRvL.116f1102A"],"types":["indicators"]}'
```

---

## Rate Limits

- Each endpoint rate-limited independently (~5000/day for search)
- Check `X-RateLimit-Remaining` response header
- Resets at midnight UTC
- Big query: ~100 requests/day

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Getting only `id` back | Must specify `fl=bibcode,title,...` explicitly |
| `title` is a string | `title` is an array, use `title[0]` |
| Missing arxiv link | Check `identifier` array for `arXiv:` prefix entries |
| URL encoding issues | Use `urlencode()` for query params, especially `&` in journal names |
| Too few results | Default `rows=10`; set explicitly for more |
| 401 Unauthorized | Token expired or missing `Bearer ` prefix |
| Library 404 | Use library `id` (hash string), not `name` |
| Metrics returns empty | Use `bibcodes` (plural) as the key, not `bibcode` |
| Citation/reference fields empty | These fields must be explicitly requested in `fl=` |
