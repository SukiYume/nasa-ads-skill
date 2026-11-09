# Bundled SciX API CLI

Contents: [Search](#search) · [Highlights, facets, and statistics](#highlights-facets-and-statistics) · [Subject and holdings filters](#subject-and-holdings-filters) · [Batch metadata](#batch-metadata) · [Citation export](#citation-export) · [Metrics](#metrics) · [Suggestions and resource links](#suggestions-and-resource-links) · [References, objects, and journals](#references-objects-and-journals) · [Discovery aids](#discovery-aids) · [Unsupported operations](#unsupported-operations)

Load this reference before using `scripts/ads_api.py`, the standard-library client for `https://api.scixplorer.org/v1`. Launch rules and the token boundary are in [Setup](../SKILL.md#setup); the CLI reads `ADS_API_TOKEN` and never accepts a token argument. Global options go before the subcommand:

```text
--timeout <1-300 seconds>   default 30; 120 per reference batch and for network and wordcloud
--show-rate-limit
--library-dir <directory>
--no-store
```

JSON endpoints print UTF-8 JSON and `export` prints citation text. `search` and `bigquery` capture returned records by default and add a `literature` object; use `--no-store` for exploratory previews, then follow [screening before capture](literature-memory.md#screening-before-capture) and [summary completion](literature-memory.md#automatic-capture-and-summary-completion). A storage failure keeps the SciX response and exits nonzero; apply [failure routing](../SKILL.md#failure-routing).

## Search

Use this field set for literature research when every field is needed:

```text
bibcode,title,author,abstract,year,pub,doi,identifier,citation_count,read_count,property,doctype,esources,volume,issue,page,eid,pubdate,uat,has
```

`uat` returns curated Unified Astronomy Thesaurus subjects and `has` lists the content SciX indexes for the record, such as `body`, `data`, or `reference`. Stored searches save both on the paper; the Web reader shows UAT subjects and indexed body or data holdings.

Choose fields, page size, and sorting for the task. This example previews a small citation-sorted page for relevance screening:

```bash
python3 "<skill-dir>/scripts/ads_api.py" --no-store search \
  --query 'title:"gravitational waves"' \
  --fields 'bibcode,title,author,abstract,year,pub,doi,identifier,doctype,volume,issue,page,eid,pubdate,citation_count' \
  --rows 10 \
  --sort 'citation_count desc'
```

Repeat `--fq` for filters. Use `--start` for pagination and keep native SciX syntax inside `--query`.

### Highlights, Facets, and Statistics

`--highlight <field>` returns snippets around the matching terms from `title`, `abstract`, or `body`, so a `full:` search shows where a paper's text states something before any article is retrieved. The quoted phrases of `--query` are highlighted unless `--highlight-query` names other terms. The output adds `highlights` with each record's `bibcode` and snippets; snippets locate text and support no claim on their own.

```bash
python3 "<skill-dir>/scripts/ads_api.py" --no-store search \
  --query 'full:"Schwinger mechanism" year:2015-2020' \
  --fields bibcode,title --rows 10 --highlight body
```

`--facet <field>` counts matches by a facet field such as `year`, `bibstem_facet`, `doctype`, `property`, or `keyword_facet`, and `--facet-limit` caps the values per field. `--stats <field>` summarizes a numeric field such as `citation_count` or `read_count`. Each further facet or statistics field adds one count-only request. `--rows 0` returns counts without records and writes nothing to the library:

```bash
python3 "<skill-dir>/scripts/ads_api.py" search \
  --query 'abs:"fast radio burst"' --rows 0 \
  --facet year --facet bibstem_facet --stats citation_count
```

`--param <key>=<value>` passes another search parameter, such as `hl.fragsize=300` or `facet.prefix=Ap`; `q`, `fl`, `rows`, `start`, `sort`, and `fq` come from their own options.

Repeat `--collection 'FRB/Propagation'` and `--role methods` to organize captured results. Roles accept `review`, `intro`, `methods`, `discussion`, and `comparison`. Stored searches add the complete metadata fields to custom `--fields`; `--no-store` preserves the requested field set. Search runs retain query parameters, total matches, returned records, and summary progress.

Useful query forms:

```text
author:"Einstein, A"                         exact author
author:"^Einstein, A"                        first author
title:"gravitational waves"                  title phrase
abs:"dark matter"                            abstract
full:"machine learning"                      indexed full text
bibcode:2016PhRvL.116f1102A                  bibcode
arxiv:1602.03837                             arXiv ID
doi:10.1103/PhysRevLett.116.061102           DOI
year:2020-2024                               year range
bibstem:ApJ                                  journal abbreviation
orcid:0000-0002-1825-0097                    ORCID
object:"M31"                                 object name through SIMBAD and NED
citations(bibcode:2016PhRvL.116f1102A)       citing papers
references(bibcode:2016PhRvL.116f1102A)      cited references
trending(exoplanets)                         trending papers
useful(bibcode:2016PhRvL.116f1102A)          useful papers
similar(bibcode:2016PhRvL.116f1102A)         similar papers
```

### Subject and Holdings Filters

SciX spans astrophysics, Earth science, planetary science, heliophysics, and biological and physical sciences. Combine these fielded forms with the query or `--fq`:

```text
uat:"black hole physics"                     curated UAT subject
collection:astronomy                         astrophysics collection
collection:planetary                         also earthscience, heliophysics
planetary_feature:"Jezero"                   named planetary surface feature
has:body                                     SciX indexes the full text
has:data                                     linked data products exist
```

`has:body` marks indexed text for `full:` searches; lawful article access still follows [full-text retrieval](fulltext.md). Example parameters illustrate syntax; choose subjects and collections from the research scope.

An `undefined field object` response usually means an unfielded object-name query was parsed as a field. Retry with `title:`, `abs:`, or `full:`. If only `id` is returned, request the needed values through `--fields`.

## Batch Metadata

Use `bigquery` to retrieve the complete metadata set for deduplicated bibcodes:

```bash
python3 "<skill-dir>/scripts/ads_api.py" bigquery \
  1907AN....174...59. \
  1908PA.....16..445. \
  --fields 'bibcode,title,author,abstract,year,pub,doi,identifier,citation_count'
```

Use `--bibcodes-file <path>` for a long list. Use `--start` when a batch exceeds 2,000 returned records.

## Citation Export

Reusable BibTeX comes from the [local citation workflow](literature-memory.md#citation-export). Use `export` for other formats, a fresh remote export, or the no-write opt-out.

```bash
python3 "<skill-dir>/scripts/ads_api.py" export \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --format bibtex \
  --sort 'first_author asc'
```

Supported formats:

- BibTeX and tagged: `bibtex`, `bibtexabs`, `ads`, `endnote`, `procite`, `ris`, `refworks`, `medlars`
- LaTeX: `aastex`, `icarus`, `mnras`, `soph`
- XML and feeds: `dcxml`, `refxml`, `refabsxml`, `votable`, `rss`
- Other: `ieee`
- Journal styles: `csl` with `--style` (`aastex`, `icarus`, `mnras`, `soph`, `aspc`, `apsj`, `aasj`, or `ieee`) and `--csl-format unicode|html|latex`; the `aastex`, `aspc`, and `aasj` styles also take `--journal-format macros|abbreviations|full`
- Custom: `custom` with `--custom-format`, such as `'%1H:%Y:%q'` for citation keys

```bash
python3 "<skill-dir>/scripts/ads_api.py" export \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --format csl --style mnras --csl-format latex
```

The CLI normalizes single-record and multi-record responses to citation text. Return it in a fenced block or save it with the matching extension when requested.

## Metrics

```bash
python3 "<skill-dir>/scripts/ads_api.py" metrics \
  2016PhRvL.116f1102A \
  --type basic \
  --type citations \
  --type indicators
```

Available types are `basic`, `citations`, `indicators`, `histograms`, and `timeseries`. Add `--type histograms` before repeating `--histogram` for `publications`, `reads`, `downloads`, or `citations`.

Read the returned keys before formatting. Several contain spaces, including `basic stats`, `citation stats`, and `indicators`, with corresponding `refereed` keys. State the exact paper set and denominator; do not describe a metric from an arbitrary subset as an author-level metric.

## Suggestions and Resource Links

Citation helper models an existing bibliography and requires at least two distinct bibcodes:

```bash
python3 "<skill-dir>/scripts/ads_api.py" suggest \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A
```

Present its output as algorithmic suggestions and inspect topical relevance. For one seed paper, search with `similar(...)` or `useful(...)`.

Resolve article, data, citation, reference, or associated links with:

```bash
python3 "<skill-dir>/scripts/ads_api.py" resolve \
  2016PhRvL.116f1102A \
  --link-type esource
```

Common resolver types include `esource`, `data`, `citations`, `references`, and `associated`. Resolver labels identify candidates and say nothing about open access; retrieve article content through [fulltext.md](fulltext.md).

## References, Objects, and Journals

Resolve free-text reference strings, such as a manuscript's reference list, to bibcodes:

```bash
python3 "<skill-dir>/scripts/ads_api.py" reference \
  'Abbott, B. P., et al. 2016, PhRvL, 116, 061102' \
  'Lorimer D. R. et al., 2007, Science, 318, 777'
```

Use `--references-file <path>` for one reference per line. The CLI sends batches of 16, the service's request limit, and returns `count`, `resolved_count`, and `resolved` entries with `refstring`, `score`, and `bibcode`; an unresolved entry has a null `bibcode` and a `comment`. A score below `1.0` marks an approximate match, so compare its record with the reference before citing it. Each batch counts against a separate, much smaller reference-service quota that `--show-rate-limit` reports. Retrieve metadata for the resolved bibcodes with `bigquery`, which captures them for summaries and citation export.

Resolve object names to SIMBAD and NED identifiers, or translate an `object:` query into the search query SciX runs for it:

```bash
python3 "<skill-dir>/scripts/ads_api.py" objects M31 'Crab Nebula'
python3 "<skill-dir>/scripts/ads_api.py" objects --query 'object:M31'
```

Object resolution depends on SIMBAD and NED; an upstream timeout is an API result. When `object:` searches fail, search the name with `title:` or `abs:` and the designations the object goes by.

Find journals and their bibstems for `bibstem:` filters, or read a journal summary with its names, identifiers, and publication history:

```bash
python3 "<skill-dir>/scripts/ads_api.py" journals 'Monthly Notices'
python3 "<skill-dir>/scripts/ads_api.py" journals MNRAS --summary
```

A journal summary leaves out its per-volume completeness table, listed in `omitted`, unless `--completeness` is given. These subcommands print the service JSON and write nothing to the library.

## Discovery Aids

These subcommands print the service JSON and write nothing to the library. Retrieve metadata for the papers they surface with `bigquery`, which captures them for summaries.

Group papers by the references they share, or their authors by coauthorship. A few dozen bibcodes form groups; a paper network returns them in `data.summaryGraph` with paper counts, top terms, and shared references, and `--full` adds the per-paper graph. Sets too small to group return the per-paper graph alone:

```bash
python3 "<skill-dir>/scripts/ads_api.py" network paper --bibcodes-file "<bibcodes.txt>"
python3 "<skill-dir>/scripts/ads_api.py" network author --bibcodes-file "<bibcodes.txt>"
```

List the terms that characterize up to 500 records a query returns, with their record counts and inverse document frequency:

```bash
python3 "<skill-dir>/scripts/ads_api.py" wordcloud --query 'abs:"fast radio burst" year:2024' --rows 200
```

## Unsupported Operations

SciX Libraries use [libraries.md](libraries.md). Bibliographic endpoints or documented options outside the CLI use [http-fallback.md](http-fallback.md); other account services stay outside the skill, as [Setup](../SKILL.md#setup) states. A CLI error from a supported operation is an API result; direct HTTP does not change it.

The ADS document matcher (`/oracle/matchdoc`) is not served by the SciX API. Match a preprint to its publication, or a record known by its title and authors, with `search` on its identifiers, title, first author, and year, or resolve its reference string with `reference`.
