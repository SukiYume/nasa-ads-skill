# Bundled SciX API CLI

Load this reference before using `scripts/ads_api.py`, the standard-library client for `https://api.scixplorer.org/v1`. Launch rules and the token boundary are in [Setup](../SKILL.md#setup); the CLI reads `ADS_API_TOKEN` and never accepts a token argument. Global options go before the subcommand:

```text
--timeout <1-300 seconds>
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

## Unsupported Operations

SciX Libraries use [libraries.md](libraries.md). Other endpoints or documented options outside the CLI use [http-fallback.md](http-fallback.md). A CLI error from a supported operation is an API result; direct HTTP does not change it.
