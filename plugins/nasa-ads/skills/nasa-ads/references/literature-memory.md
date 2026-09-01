# Persistent Literature Memory

Load this reference when a task looks up, searches, inspects, stores, or maintains local paper knowledge. Load [digest-schema.md](digest-schema.md) when the task creates, validates, merges, or replaces a digest.

## Purpose and Storage

The local database is a version-aware evidence cache. The original paper remains the reader-facing citation. The database preserves verified artifacts, extracted text, visual-reading provenance, layered digests, scientific facets, and atomic findings.

Persistent storage is the default behavior of this skill. A valid digest is ingested or merged after a material paper is read. Per-paper confirmation is unnecessary. Library deletion, bulk removal, relocation, human-note replacement, and complete-digest replacement require explicit confirmation and a recoverable backup.

Resolve `scripts/literature_db.py` relative to `SKILL.md`. Use the working Python 3 command selected for the bundled CLIs.

The default durable library root is:

- Windows: `%LOCALAPPDATA%\nasa-ads\literature`
- macOS/Linux: `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature`

Set `NASA_ADS_LITERATURE_DIR` or place global `--library-dir <path>` before the subcommand to select another root. The library contains `literature.sqlite3` and a content-addressed `objects/` tree keyed by verified artifact SHA256. Manage both through the CLI.

## Read Commands

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

python3 "<skill-dir>/scripts/literature_db.py" list
python3 "<skill-dir>/scripts/literature_db.py" stats
python3 "<skill-dir>/scripts/literature_db.py" audit
```

`lookup`, `show`, `search`, `list`, `stats`, and `audit` open the database read-only. A missing library returns empty results for ordinary reads and creates no files. `audit` requires an existing library. A database-schema mismatch exits with backup and explicit `init` instructions.

## Lookup and the Article-Open Gate

Run `lookup` with the requested topics before opening article content. It resolves bibcodes, DOIs, and arXiv IDs to a canonical paper, selects the preferred stored version, and reports coverage, object paths, `open_gate_action`, and `complete_ingest_required`.

| State | Required action |
|---|---|
| `not_found` | Fetch the exact version. Complete full or whole-document visual reading, validate its layered digest, and ingest it before using article details. |
| `needs_reading` | Complete the same paper-wide workflow. A targeted-only record does not satisfy the gate. |
| `reusable` | Reuse the exact complete version and verify decisive details against its stored artifact. |
| `targeted_reading` | Read the complete relevant sections and merge missing facets into the existing complete exact-version digest. |
| `version_changed` | Treat the changed canonical-content version as a new complete-ingest gate. |

Opening article content means inspecting a body section, local or remote article page, PDF page, figure, caption, table, equation, appendix, supplementary passage, or quotation context. Metadata and abstract triage remain outside this gate.

Process the opened papers for the current request. Unopened candidates remain outside the database. Unrelated maintenance remains outside the research workflow.

Exact values, equations, figure interpretations, table cells, and quotations require a check against the stored artifact even when the digest covers the requested facet.

## Version Identity

- Bibcode, DOI, and base arXiv ID become aliases of one paper when metadata connects them.
- An arXiv version suffix identifies provenance within that paper.
- Published, accepted, preprint, and ADS-scan authority classes remain distinct.
- Raw artifact SHA256 identifies downloaded bytes. Extracted-text SHA256 identifies the prepared text. Canonical-content SHA256 normalizes Unicode and layout whitespace within one authority class.
- A refreshed container with matching canonical content reuses the stored version and records its artifact provenance. Changed canonical content creates a new version and requires a complete digest for that version.
- Scans without usable text use raw-artifact identity and whole-document visual coverage.
- Each exact article version has one current structured digest. `--merge` updates that digest in place.

Valid current digests use schema version `2`. Invalid digests or multiple digests block reuse until an approved backup-and-repair workflow installs one complete record. Read commands open without migration. For a database-schema-1 library, create a full backup with the compatible pre-update CLI, install the update, and run `init` explicitly to migrate.

## Search

Search defaults to all indexed fields:

```bash
python3 "<skill-dir>/scripts/literature_db.py" search "<multiple search terms>"
```

| Scope | Indexed content |
|---|---|
| `metadata` | title, authors, abstract, identifiers, entities |
| `summary` | topics, overview, facets, findings, methods, limitations |
| `fulltext` | complete extracted article text |
| `all` | every searchable field |

The default `--mode terms` requires every query term. `--mode phrase` matches an exact phrase. `--mode fts` exposes SQLite FTS5 syntax. Repeated `--topic` values filter declared facet coverage. `--year-from`, `--year-to`, and `--limit` control results.

Search scans matching candidates until it fills the requested topic-filtered limit or exhausts them. Results include paper/version provenance, reading status, snippets, available facets, dynamically matched facets, findings, and `matched_terms`. Check the stored article before quoting.

SQLite FTS5 is used when available. Continuous CJK queries and Python builds without FTS5 use deterministic substring matching. The response identifies the selected search engine.

`list` selects the preferred available version for each canonical paper and applies topic filters before the result limit.

## Maintenance

Initialize a new library or perform an explicitly prepared schema migration:

```bash
python3 "<skill-dir>/scripts/literature_db.py" init
```

Run the read-only health audit:

```bash
python3 "<skill-dir>/scripts/literature_db.py" audit
```

The audit checks SQLite integrity, foreign keys, schema-version-2 digest validity, complete reading state, one digest per exact version, search and FTS parity, stored object presence and hashes, orphan objects, and metadata coverage. `--skip-hashes` runs a faster structural pass.

Create a consistent database and object-store backup before approved maintenance:

```bash
python3 "<skill-dir>/scripts/literature_db.py" backup
```

`--destination <path>` selects another backup location. The backup contains `literature.sqlite3`, `objects/`, and `backup.json`, followed by an integrity check.

Refresh discovery with `fulltext.py` and enrich an existing record when ADS assigns a bibcode or supplies additional metadata:

```bash
python3 "<skill-dir>/scripts/literature_db.py" enrich \
  --manifest "<manifest.json>"
```

Enrichment preserves populated bibliographic fields, fills empty fields, reconciles identifiers, updates available dynamic metrics, and rebuilds the derived search document. Fresh arXiv records remain searchable while ADS indexing is pending. The audit reports them under `arxiv_records_awaiting_ads_bibcode`.

Run `reindex` when an audit reports derived search drift. The command rebuilds search documents from current records and stored full text.

The library remains local. Concurrent multi-machine writes to a synchronized live database can corrupt state. A future cross-machine workflow should use explicit export and import steps.

## Research Method Note

Report counts for papers reused, reused after targeted verification, augmented with new facets, newly ingested, and refreshed as new versions. Report opened papers whose ingest failed, unopened abstract-triaged candidates, and evidence coverage across published, accepted, preprint, visual, and abstract-only records.

Database reuse reduces repeated reading. Each research task still searches ADS for current literature and verifies decisive claims against the stored exact version.
