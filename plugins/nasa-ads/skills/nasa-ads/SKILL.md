---
name: nasa-ads
description: Search and investigate NASA ADS astronomy and astrophysics literature. Use when a user asks to find papers, check whether a claim or topic appears in published literature, retrieve titles/authors/abstracts/DOIs/arXiv IDs, export BibTeX or other citations, manage ADS libraries, inspect citation metrics, find related papers, or resolve full-text and data links. Trigger on terms such as paper, literature, citation, bibliography, BibTeX, arXiv, ADS, published, related work, references, library, h-index, astronomy, and astrophysics, plus Chinese requests including 文献, 论文, 查文献, 查论文, 文献调研, 论文调研, 论文检索, 有没有人发表, 有没有文献提到, 是否有相关论文, 已有研究, 引用导出, 获取 BibTeX, ADS 文献, arXiv 论文, 天文文献, 天文论文, and 天体物理论文.
---

# NASA ADS Agent Workflow

Use the NASA Astrophysics Data System Developer API for literature research, citation export, libraries, bibliometrics, related-paper discovery, and resource-link resolution. Follow this file as runtime instructions for an agent; use the repository README only for human installation and onboarding.

## Core Rules

1. Check `ADS_API_TOKEN`, then `ADS_DEV_KEY`, before every API workflow.
2. Never print, log, commit, or place the token in a URL or source file.
3. Keep research calls read-only by default.
4. Confirm immediately before deleting or emptying a library, bulk removal, or permission changes.
5. Describe an empty search as “no matching records found for these queries.” A search cannot establish that no relevant literature exists.
6. Separate observational labels from intrinsic physical classes; a nondetection is not proof of absence.
7. Use the official [ADS API documentation](https://ui.adsabs.harvard.edu/help/api/) for workflows not covered here.

## Transport Selection

1. Resolve `scripts/ads_api.py` relative to this `SKILL.md`.
2. Try `python3`, then `python`, then `py -3` until one can run the bundled CLI.
3. Use the CLI for every supported `search`, `bigquery`, `export`, `metrics`, `suggest`, or `resolve` call.
4. Do not recreate a supported CLI call with curl, PowerShell, temporary code, or another HTTP client.
5. Use direct HTTP only when Python 3 is unavailable, the requested endpoint is outside the CLI, or the task uses ADS Libraries.
6. Treat ADS HTTP failures returned by the CLI as API failures. Correct or report them without switching transports.
7. When direct HTTP is required, read [references/http-fallback.md](references/http-fallback.md) and state the reason in the method note.

## Research Workflow

1. Define the question, operational categories, date range, and what evidence would support or weaken the claim.
2. Build independent query families from exact terms, synonyms, competing interpretations, known objects or authors, and seed-paper citation chains.
3. Run the required calls through the selected transport.
4. Request only the fields and row count needed.
5. Inspect response shape, `numFound`, returned rows, pagination, and rate limits when relevant.
6. Deduplicate by bibcode, reconcile alternate records, and read abstracts before judging relevance.
7. Track `doctype` and `property`; label preprints, abstracts, circulars, and other non-refereed records separately from refereed papers.
8. Compare recent results with influential or foundational results.
9. Distinguish direct evidence, counterevidence, selection effects, adjacent work, and algorithmic recommendations.
10. Return a reader-facing synthesis with links, evidence calibration, and a concise search-method note.

## Coverage Standard

- For an identifier lookup or citation export, one precise query may be sufficient.
- For a focused literature review, use at least two independent query families and inspect the abstracts of material records.
- For a broad, comprehensive, or claim-level review, cover terminology and synonyms, counterclaims or selection effects, seed-paper citations or references, recent and citation-ranked results, and all manageable result pages. If the result set is too large, state the sampling rule and uncovered scope.
- Use `bigquery` to re-fetch complete metadata for the deduplicated evidence set.
- Refine or discard query families dominated by false positives; do not treat `numFound` as a relevant-paper count.
- Judge sufficiency by conceptual and evidentiary coverage, not by raw result count.

## Credentials

Resolve `ADS_API_TOKEN`, then `ADS_DEV_KEY`. If both are absent, stop; direct the user to [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token), ask them to set either variable in the terminal that launches the host, and retry. If the user supplies a token for the current session, keep it in process memory and avoid commands that echo headers or command lines.

## Bundled CLI

Use `<skill-dir>/scripts/ads_api.py`, where `<skill-dir>` contains this `SKILL.md`. It uses only the Python standard library, reads the token variables itself, URL-encodes parameters, builds request bodies, checks HTTP failures, and never accepts a token on the command line.

```bash
python3 "<skill-dir>/scripts/ads_api.py" --help
```

Use the first working Python 3 command selected above. Do not copy or rewrite the script into a temporary file.

| Subcommand | Workflow |
|---|---|
| `search` | Literature and related-paper searches |
| `bigquery` | Batch bibcode lookup |
| `export` | Citation export |
| `metrics` | Aggregate bibliometrics |
| `suggest` | Citation-helper suggestions |
| `resolve` | Full-text, data, citation, and reference links |

Place global options before the subcommand. `--show-rate-limit` prints rate-limit headers to stderr; `--timeout <seconds>` sets a bounded timeout. JSON endpoints print UTF-8 JSON, and `export` prints citation text.

Claude Code commands can locate the CLI at:

```text
${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py
```

## Literature Search

Use this practical field set when the task needs full research metadata:

```text
bibcode,title,author,abstract,year,pub,doi,identifier,citation_count,read_count,property,doctype
```

```bash
python3 "<skill-dir>/scripts/ads_api.py" search \
  --query 'title:"gravitational waves"' \
  --fields 'bibcode,title,author,year,pub,doi,identifier,citation_count' \
  --rows 10 \
  --sort 'citation_count desc'
```

Repeat `--fq` for filters. Keep native ADS syntax in `--query`.

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
bibstem:ApJ                                  journal abbreviation
orcid:0000-0002-1825-0097                    ORCID
citations(bibcode:2016PhRvL.116f1102A)       citing papers
references(bibcode:2016PhRvL.116f1102A)      cited references
trending(exoplanets)                         trending papers
useful(bibcode:2016PhRvL.116f1102A)          useful papers
similar(bibcode:2016PhRvL.116f1102A)         similar papers
```

For a topic review or claim check, apply the Research Workflow and Coverage Standard above. Record the exact query families and material limits for sparse or negative results.

Use `bigquery` to retrieve metadata for a deduplicated bibcode set:

```bash
python3 "<skill-dir>/scripts/ads_api.py" bigquery \
  1907AN....174...59. \
  1908PA.....16..445. \
  --fields 'bibcode,title,author,abstract,year,pub,doi,identifier,citation_count'
```

Use `--bibcodes-file <path>` for a long list and `--start` when a batch exceeds 2000 returned records.

## Citation Export

```bash
python3 "<skill-dir>/scripts/ads_api.py" export \
  2016PhRvL.116f1102A \
  2017ApJ...848L..12A \
  --format bibtex \
  --sort 'first_author asc'
```

The CLI normalizes single-record and multi-record responses to citation text. Supported formats:

- BibTeX/tagged: `bibtex`, `bibtexabs`, `ads`, `endnote`, `procite`, `ris`, `refworks`, `medlars`
- LaTeX: `aastex`, `icarus`, `mnras`, `soph`
- XML/feed: `dcxml`, `refxml`, `refabsxml`, `votable`, `rss`
- Other: `ieee`

Return exports in a fenced code block or save them with an appropriate extension when requested.

## Metrics

```bash
python3 "<skill-dir>/scripts/ads_api.py" metrics \
  2016PhRvL.116f1102A \
  --type basic \
  --type citations \
  --type indicators
```

Available types are `basic`, `citations`, `indicators`, `histograms`, and `timeseries`. Add `--type histograms` before repeating `--histogram` for requested categories.

Read the returned keys before formatting; several contain spaces, such as `basic stats`, `citation stats`, and `indicators`, with corresponding `refereed` keys. Report the paper set and denominator. Do not present a metric from an arbitrary subset as an author-level metric.

## Suggestions and Resource Links

```bash
python3 "<skill-dir>/scripts/ads_api.py" suggest \
  2016PhRvL.116f1102A
```

Present citation-helper results as algorithmic suggestions. Inspect topical relevance before recommending them.

Find related records through `search` with `similar(...)` or `useful(...)`.

```bash
python3 "<skill-dir>/scripts/ads_api.py" resolve \
  2016PhRvL.116f1102A \
  --link-type esource
```

Common resolver types include `esource`, `data`, `citations`, `references`, and `associated`. Prefer lawful open-access or author-posted links. A resolver result does not guarantee free access.

## Libraries and Other Endpoints

The CLI does not expose ADS Libraries. Read [references/libraries.md](references/libraries.md) before any library call and preserve every confirmation boundary defined there.

For another unsupported endpoint, read [references/http-fallback.md](references/http-fallback.md), then consult the official ADS API documentation for the current method and schema.

## Result Presentation

For literature research, include:

1. A concise answer to the user’s question.
2. Representative records with title, first authors, year, venue, citation count, and bibcode.
3. ADS links in the form `https://ui.adsabs.harvard.edu/abs/<bibcode>`.
4. DOI and arXiv links when present.
5. A thematic synthesis for multi-paper work.
6. Query families, filters, sorting, pagination, and search date when completeness matters.
7. A calibrated limitation statement for sparse or negative results.

Build an arXiv link from an `identifier` value beginning with `arXiv:`.

## Failures

- Missing token: give the token-page link and supported environment-variable names above, then stop.
- `401`: verify that the token is current.
- `403`: check account or library permissions.
- `404`: recheck the bibcode, library ID, or endpoint.
- `429`: report the rate-limit headers and wait until reset.
- Only `id` returned: request the needed fields with `--fields`.
- `undefined field object`: search the target name with `title:`, `abs:`, or `full:`; do not switch transports.
- Empty result: relax unnecessary filters, try variants, and report the searched forms.
- CLI launch failure after all three Python commands: use the direct HTTP fallback and state why.
