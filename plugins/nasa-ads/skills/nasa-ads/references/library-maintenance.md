# Library Maintenance

Load this reference for health checks, backup and restore, metadata refresh, duplicate identities, digest conflicts, citation-cache import, index rebuilds, and compaction. Destructive and whole-library work follows the write scope in [Core Invariants](../SKILL.md#core-invariants). Commands run `python3 "<skill-dir>/scripts/literature_db.py" [--library-dir <dir>] <subcommand>`.

## Health Checks

```bash
stats
audit
audit --skip-hashes
check
```

`lookup`, `passage`, `show`, `search`, `findings`, `parameters`, `list`, `stats`, `pending`, `check`, `reading-check`, `runs`, plain `collections`, offline `citations`, Web requests, and `audit` use read-only connections, and reads of a missing library create no files. `audit` and `backup` require an existing database.

`audit` checks SQLite integrity, foreign keys, digest validity, complete reading state, search-index parity, primary and historical objects and their hashes, paper metadata, source-snapshot hashes and evidence levels, historical pending summaries, topic assignments, and missing citation caches. An unhealthy audit exits nonzero; `--skip-hashes` gives a faster structural pass. Some document types and unindexed publications legitimately lack metadata fields, so verify reported gaps against the source. Plain `check` reports unfinished summaries, topics, and prepared article versions that still need their digest across the whole library.

## Backup and Restore

```bash
backup --destination "<new backup directory>"
restore "<backup directory>" --destination "<new library directory>"
```

A backup holds a consistent SQLite snapshot, article objects, and `backup.json`. `restore` requires a new destination, verifies object hashes and database integrity, rewrites managed file references, and leaves the original library in place. Transfer a library to another computer with a backup and restore; copying a live database between synchronized machines can capture an inconsistent state. Concurrent writes on one computer are serialized by SQLite transactions.

## Metadata and Identity

`enrich --manifest <file>` refreshes current source metadata and reconciles identifiers for an existing paper. Fresh capture and enrichment correct nonempty fields of the same current record, and empty incoming fields keep known values. Ingest and cached full-text capture keep the current bibliography while recording historical source evidence.

Confirmed journal metadata upgrades a preprint's record. A record listing the stored bibcode in `alternate_bibcode`, such as a final volume replacing a `.tmp.` bibcode, replaces it, and a publication awaiting its journal bibcode keeps the preprint bibcode as a lookup alias. Later preprint captures keep the confirmed journal bibliography.

When one capture, ingest, or enrich manifest carries identifiers held by several stored papers, such as a preprint and its separately captured publication that SciX later links, those papers merge. The merged paper keeps distinct versions, readings, summaries, topics, tags, roles, notes, and search history, and takes the published metadata. Identity reconciliation, ingest checks, and writes share one transaction, and successful merges rebuild search documents. For unlinked candidates, verify authors, content, and publication provenance before adding identifiers by hand; title similarity only suggests candidates. Related articles, datasets, conference abstracts, and corrections keep separate identities.

### Reconcile Conflicting Digests

Duplicate versions keep their artifact files and exact arXiv labels. Identical digests share one record, and a digest present on only one side moves to the retained version. Different stored digests stop the merge with a conflict, and every operation carrying both records' identifiers reports it until the digests agree:

1. Run `backup`.
2. Run `lookup <identifier> --include-digest` for each record using an identifier only that record holds, such as the preprint's arXiv ID and the publication's DOI. Note each `version.manifest_path` and digest.
3. Author one complete digest that keeps the verified evidence of both readings, and check it with `validate-digest`.
4. Run `ingest --manifest <that record's manifest_path> --digest <reconciled digest> --replace-digest` for each record.
5. Retry the original capture, ingest, or enrich; the records then merge.

## Refresh SciX Metadata

A whole-library refresh picks up publication changes, new abstracts, subject terms, and identifier links:

1. Run `backup`.
2. Write the bibcodes from `list --limit <paper count>` to a file and run `ads_api.py bigquery --bibcodes-file <file>` with default capture. SciX resolves superseded preprint and `.tmp.` bibcodes to current records.
3. For papers without a bibcode, query their DOI and arXiv identifiers with `ads_api.py search --query 'identifier:"<id>"'`. Publisher or arXiv metadata can fill verified details while SciX indexing is pending; keep source links and exact identifiers.
4. Compare suspected source-field substitutions with the original sources. Keep legitimate abstract revisions; correct confirmed substitutions with verified source text and new source-grounded summaries, and record the correction's provenance.
5. Complete pending summaries from all historical runs in scope, reconcile reviewed duplicates and equivalent collection paths, cache official BibTeX with `citations --fetch` where needed, and finish with `check` and `audit`.

Unchanged sources reuse their summaries.

## Citation Cache Import

`import-citations --bibtex <scix-export.bib>` caches an unedited `ads_api.py export` BibTeX file. Every entry must match a current library bibcode; unknown records, duplicates, and incomplete entries abort the whole import. Run `enrich` or a metadata refresh first when SciX indexing or publication status has changed.

## Upgrade from the Previous Release

A library written by the previous release opens with an error naming its earlier schema. Convert it once:

```bash
migrate
migrate --destination "<new backup directory>"
```

`migrate` converts every digest in memory first and stops without changes if any record fails. It then writes a verified backup, rebuilds the digest table and the search index, and compacts the database. Earlier records keep their content: significance joins the summary, the first summary sentence becomes the tldr, separate dataset and method fields join their descriptions, coverage records give way to section headings, and facet-level limitations join `global_limitations`. Value statuses, entity and dataset types, and study types that a record left unclassified are assigned by rule, and the record's `reading.notes` says which, so check them in the article before citing. Converted records carry no quotes or section summaries; `passage` resolves their findings through locators. Run `audit` afterwards. A library already on the current schema reports `current`.

## Rebuild, Compact, and Replace

`reindex` rebuilds the complete-digest search documents and the full-text index from scratch. `compact` rewrites the database file without the pages that removed or replaced records left free and reports the bytes returned to the file system; run it after large maintenance. Replacing a complete digest uses `backup` followed by an approved `ingest --replace-digest`, described in [digest-schema.md](digest-schema.md#validation-and-ingest).
