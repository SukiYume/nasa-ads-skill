# Bundled ADS API CLI

Load this reference before using `scripts/ads_api.py`. It documents the stable ADS operations exposed by the bundled CLI. Research design, full-text reading, evidence judgment, and synthesis remain in `SKILL.md`.

## Launch

Resolve the script relative to `SKILL.md`, then try `python3`, `python`, and `py -3` until one can run it:

```bash
python3 "<skill-dir>/scripts/ads_api.py" --help
```

The CLI reads `ADS_API_TOKEN` and then `ADS_DEV_KEY`; it never accepts a token argument. Put global options before the subcommand:

```text
--timeout <1-300 seconds>
--show-rate-limit
--library-dir <directory>
--no-store
```

JSON endpoints print UTF-8 JSON. `export` prints citation text. Check the exit status and actual response shape before interpreting either.

Search and big query capture every returned record by default. The response's `literature` object identifies the run and pending summaries. Follow [source-summary completion](literature-memory.md#automatic-capture-and-summary-completion) for summaries and topic assignments, and the shared [reading scope](../SKILL.md#reading-scope) for content investigation. Storage failure preserves the ADS response and returns a failing exit status; apply [failure routing](../SKILL.md#failure-routing). The no-library-write exception in [Core Invariants](../SKILL.md#core-invariants) governs diagnostics and explicit opt-outs.

## Search

Use this field set for literature research when every field is needed:

```text
bibcode,title,author,abstract,year,pub,doi,identifier,citation_count,read_count,property,doctype,esources,volume,issue,page,eid,pubdate
```

Choose fields, page size, and sorting for the task. This example requests a small citation-sorted page:

```bash
python3 "<skill-dir>/scripts/ads_api.py" search \
  --query 'title:"gravitational waves"' \
  --fields 'bibcode,title,author,year,pub,doi,identifier,citation_count' \
  --rows 10 \
  --sort 'citation_count desc'
```

Repeat `--fq` for filters. Use `--start` for pagination and keep native ADS syntax inside `--query`.

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

For reusable BibTeX, use `literature_db.py citations <identifiers>` and add `--fetch` to cache official ADS entries. Offline export uses the cached entry or a clearly labeled entry generated from stored metadata. The ADS export command below supports the additional citation formats.

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

Common resolver types include `esource`, `data`, `citations`, `references`, and `associated`. Resolver labels identify candidates but do not prove that access is open. Use `references/fulltext.md` and `fulltext.py` when article content is needed.

## Unsupported Operations

The CLI does not expose ADS Libraries. Load `references/libraries.md` for those calls. For another unsupported endpoint or a current documented option that the CLI does not expose, load `references/http-fallback.md`. Do not use direct HTTP to bypass a supported CLI error.
