# Persistent Literature Memory

Load this reference for every literature review, claim check, or multi-paper synthesis. The local literature database preserves verified article versions, extracted full text, layered digests, topic facets, and atomic findings so later research can reuse prior reading.

## Core Principle

The database is an evidence cache, not a replacement citation. Cite the original paper in reader-facing work. Use the database to decide what has already been read, which version was read, which scientific dimensions were covered, and what still needs targeted reading.

Add only papers that were actually read and summarized. ADS search candidates, title matches, and abstract triage do not enter the database automatically.

## Bundled CLI

Resolve `scripts/literature_db.py` relative to `SKILL.md`. Use the same working Python 3 command selected for the other bundled CLIs.

The default durable library root is:

- Windows: `%LOCALAPPDATA%\nasa-ads\literature`
- macOS/Linux: `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature`

Set `NASA_ADS_LITERATURE_DIR` or pass global `--library-dir <path>` to override it. Place the global option before the subcommand.

The library contains `literature.sqlite3` and a content-addressed `objects/` tree. Each object is keyed by the verified raw artifact SHA256 and can contain the selected PDF/HTML, extracted text, and full-text manifest. Do not edit the SQLite file or object tree directly.

Useful commands:

```bash
python3 "<skill-dir>/scripts/literature_db.py" lookup \
  "<bibcode-or-doi-or-arxiv-id>" \
  --topic "<scientific-dimension>"

python3 "<skill-dir>/scripts/literature_db.py" search \
  "<concept, method, object, or result>" \
  --scope summary

python3 "<skill-dir>/scripts/literature_db.py" search \
  "<exact article phrase>" \
  --scope fulltext

python3 "<skill-dir>/scripts/literature_db.py" show \
  "<bibcode-or-doi-or-arxiv-id>"

python3 "<skill-dir>/scripts/literature_db.py" stats
```

## Research Preflight

After ADS search results are deduplicated, run `lookup` on every prospective material paper before fetching or reading full text.

`lookup` resolves bibcodes, DOIs, and arXiv IDs through one canonical paper record. It returns the preferred stored version, layered digest coverage, available object paths, and one of these reuse states:

| State | Meaning and action |
|---|---|
| `not_found` | Fetch, read, summarize, and ingest the paper. |
| `needs_reading` | A stored version has no reusable digest. Read it and ingest a digest. |
| `reusable` | The stored version was read fully or visually and covers the requested topics. Reuse it. |
| `reusable_for_topics` | A targeted reading covers every requested topic. Reuse only those covered facets. |
| `targeted_reading` | The paper exists, while one or more requested topics are absent. Search the local text, read the complete relevant sections, and merge new facets. |
| `version_changed` | A supplied artifact, text, or canonical-content SHA256 does not match any stored version. Inspect and ingest the new version. |

When no topics are supplied, `full` and `visual` reading records are generally reusable. A `targeted` record requires topic-specific lookup.

Exact numerical values, equations, figure interpretations, table cells, and quotations still require a targeted check against the stored HTML/PDF or extracted text. This is verification, not a complete reread.

## Version Rules

The database separates one paper identity from its article versions.

- Bibcode, DOI, and base arXiv ID are aliases of the same paper when ADS metadata connects them.
- An arXiv version suffix does not create a second paper identity.
- Published, accepted, preprint, and ADS-scan authority classes remain separate even when their text is identical.
- Prefer a stored published digest for publication-specific claims.
- The raw artifact hash verifies exact downloaded bytes and keys the object store. The extracted-text hash verifies the local text file. The canonical content hash normalizes Unicode and layout whitespace and identifies the scientific text within one authority class.
- After a refresh, compare `selected.content_sha256` through `lookup --sha256 <hash>`. A changed publisher HTML shell or PDF container with unchanged canonical content reuses the existing version and digest while retaining the distinct raw artifact in its provenance history. A changed canonical content hash creates a new version; recheck claims whose wording, values, tables, or conclusions may have changed.
- A scan without usable extracted text falls back to raw-artifact identity; visually compare it when the container hash changes.
- Preserve older digest revisions. `ingest --merge` creates a new current revision without deleting history.

## Layered Digest Model

A database entry contains the verified article text or visual-reading provenance plus a structured digest. A single sentence or abstract restatement is insufficient.

The digest has these layers:

1. **Overview**: the paper-wide objective, scope, significance, and questions addressed.
2. **Entities**: named sources, objects, surveys, instruments, simulations, catalogs, and their aliases.
3. **Datasets**: observing setup, sample, time span, frequency or wavelength coverage, and identifiers.
4. **Methods**: each major analysis method and its purpose.
5. **Facets**: independent scientific dimensions that can be retrieved separately.
6. **Findings**: atomic measurements, constraints, nondetections, interpretations, comparisons, methods, or limitations with evidence locators.
7. **Limitations**: paper-wide and facet-specific selection effects, assumptions, and unresolved alternatives.
8. **Data products**: tables, catalogs, code, software, and availability statements.
9. **Reading coverage**: full, targeted, or visual reading, including sections and page ranges.

Facet decomposition is dynamic and domain-agnostic. The schema has no fixed facet vocabulary, no FRB-specific columns, and no required facet count beyond at least one. Derive facets from the article's actual evidence structure.

A candidate deserves its own facet when it can answer an independent future research question and has a distinguishable evidence chain: its own measured or predicted quantity, method or model, result family, evidence locator, assumptions, or limitations. Split candidates when they use materially different observables, samples, analyses, parameter regimes, or inferential steps. Merge candidates that merely restate the same result, repeat a section heading, or differ only in presentation.

Apply that rule across paper types:

- observational papers may yield facets around distinct observables, populations, temporal or spectral behavior, correlations, constraints, and physical interpretations;
- theoretical papers may yield facets around assumptions, derivations, regimes, mechanisms, predictions, degeneracies, and observational tests;
- simulation papers may yield facets around setup, parameter dependence, convergence, emergent behavior, comparison with data, and failure modes;
- method, instrument, or catalog papers may yield facets around input data, algorithm or calibration, validation, performance, selection functions, products, and known failure cases;
- review papers may yield facets around evidence clusters, competing explanations, areas of agreement, disputed results, and open questions.

Do not turn every section, figure, or method into a facet automatically. Data, methods, entities, and global limitations already have separate layers. Use a facet when the scientific content is independently retrievable; use atomic findings within that facet for individual measurements, constraints, comparisons, or interpretations.

Do not force the paper into the topic of the current research request. Capture all material dimensions discovered during a full reading. Later requests can retrieve only the relevant facets.

### Atomic Findings

Every facet contains one or more findings. Each finding records:

- a concise paraphrased statement;
- `kind`: `measurement`, `constraint`, `interpretation`, `nondetection`, `method`, `comparison`, or `limitation`;
- `confidence`: `high`, `medium`, or `low`, calibrated to the paper's evidence and language;
- a locator with at least a section, page, figure, table, appendix, or paragraph hint;
- structured values when a number or bound matters;
- keywords that improve retrieval.

Separate measurements from author interpretation. Tentative correlations, model preferences, and physical-origin claims should retain the authors' uncertainty.

Store short paraphrases and evidence locators. Retrieve the local article for exact wording rather than copying long passages into the digest.

## Creating a Digest

Generate the current schema skeleton:

```bash
python3 "<skill-dir>/scripts/literature_db.py" template
```

Write the completed JSON to a task-specific temporary file, then validate it:

```bash
python3 "<skill-dir>/scripts/literature_db.py" validate-digest \
  "<digest.json>"
```

The digest must use schema version `1`. Required top-level fields are:

```text
schema_version
language
overview
keywords
entities
datasets
methods
facets
global_limitations
data_products
reading
```

Validation also rejects unknown fields inside overviews, entities, datasets, methods, facets, findings, values, data products, and reading coverage. This catches misspelled keys before an incomplete record enters the database.

Use concise facet keys made from lowercase ASCII letters, digits, and hyphens. Labels, aliases, summaries, and keywords can be multilingual. Include English technical terms and useful Chinese aliases when they improve retrieval.

`reading.status` accepts:

- `full`: the article's introduction, data/methods, results, discussion, conclusions, limitations, and data/code statements were covered as applicable;
- `targeted`: complete sections relevant to explicit topics were read, with remaining sections recorded;
- `visual`: a scan or sparse-text PDF was read through page images, with every inspected page range recorded.

## Ingesting a Read Paper

Use the cache manifest written by `fulltext.py` and the validated digest:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest \
  --manifest "<manifest.json>" \
  --digest "<digest.json>"
```

For a later targeted reading, inspect the current digest with `show`, add or improve the relevant facets, then preserve the accumulated record:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest \
  --manifest "<manifest.json>" \
  --digest "<new-facets.json>" \
  --merge
```

If the exact article version already has a different digest, plain `ingest` stops instead of replacing it. Use `--merge`; the merge preserves existing facets, combines record lists and limitations, updates matching facet keys, and creates a new current revision while retaining history.

The CLI verifies the selected artifact, text, and canonical-content hashes when present; copies the article and extracted text into the content-addressed object store; validates the digest schema; reconciles identifiers; writes one SQLite transaction; preserves previous revisions; and rebuilds the current search document.

An `abstract_only` manifest cannot be ingested. A `needs_visual_reading` manifest requires a digest with `reading.status: visual` and explicit visual page ranges.

## Search

Search defaults to all indexed fields:

```bash
python3 "<skill-dir>/scripts/literature_db.py" search "<multiple search terms>"
```

Limit the evidence surface with `--scope`:

| Scope | Indexed content |
|---|---|
| `metadata` | title, authors, abstract, identifiers, entities |
| `summary` | topics, overview, facets, findings, methods, limitations |
| `fulltext` | complete extracted article text |
| `all` | every searchable field |

The default `--mode terms` requires every query term. `--mode phrase` searches an exact phrase. `--mode fts` exposes native SQLite FTS5 syntax for advanced local queries.

Use repeated `--topic` filters for declared facet coverage, and `--year-from`, `--year-to`, or `--limit` for result control. Search returns short snippets, matching paper/version provenance, reading status, digest revision, all available facets, and dynamically matched facets and findings with `matched_terms`. A multi-term paper hit may span several facets; inspect the per-facet terms instead of forcing one facet to contain the complete query. Do not present database snippets as quotations without checking the stored article.

SQLite FTS5 is used when available. Because the default Unicode tokenizer does not segment continuous CJK text reliably, Chinese/Japanese/Korean queries automatically use deterministic substring matching. The same fallback is used when the local Python SQLite build lacks FTS5. The result reports `search_engine` and whether FTS5 is available.

Use `list` to enumerate stored papers. It returns the preferred available article version for each canonical paper, ordered by published, accepted, preprint, and scan authority, then by retrieval time. Topic-filtered listing scans the complete local paper set before applying the requested result limit.

## Automatic Write Boundary

The user has requested persistent literature memory. After a material paper is read and a valid digest is produced, ingesting or merging that record is an expected part of the research workflow and does not need per-paper confirmation.

The bundled CLI exposes no delete command. Any future operation that clears the library, removes stored papers, discards digest history, overwrites human-authored notes, or relocates the entire library requires explicit confirmation and a recoverable backup.

The library remains local. It is not uploaded to ADS, arXiv, a publisher, or an embedding service. Avoid placing the live SQLite database in a folder synchronized concurrently by multiple machines. Use an explicit export/import workflow when cross-machine synchronization is added later.

## Final Method Note

For literature research, report:

- papers reused without rereading;
- papers reused after targeted verification;
- papers receiving new targeted facets;
- newly read and ingested papers;
- new article versions refreshed;
- material papers left outside the database and why;
- published, accepted, preprint, visual, and abstract-only evidence coverage.

Database reuse reduces repeated work. It does not reduce the obligation to search ADS for newly published literature or to verify decisive claims against the stored article version.
