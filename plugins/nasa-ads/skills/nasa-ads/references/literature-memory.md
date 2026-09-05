# Personal Literature Library

Load this reference for persistent search capture, source-based summaries, local reuse, organization, Web browsing, citations, and maintenance. Apply the defaults and exceptions in [Core Invariants](../SKILL.md#core-invariants), and load [digest-schema.md](digest-schema.md) for complete article digests.

## Storage and Evidence Levels

The default root is `%LOCALAPPDATA%/nasa-ads/literature` on Windows and `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature` on macOS/Linux. Set `NASA_ADS_LITERATURE_DIR` or place `--library-dir <path>` before the database subcommand to select another root.

The root contains `literature.sqlite3` and a verified `objects/` tree. Keep both together. A backup and explicit restoration provide a portable copy. Use the bundled CLI to manage them. Concurrent writes on one computer use SQLite transactions; copying a live database across synchronized machines requires a consistent backup.

| Layer | Meaning | Future use |
|---|---|---|
| Metadata record | Bibliographic identity with no available abstract | Identification and relevance triage |
| Abstract record | Stored source abstract plus pending or completed agent summary | Abstract-level claims and later selection |
| Complete article version | Verified article and text, full or whole-document visual reading, one complete digest | Scientific evidence with facet coverage and locators |
| Organization | Hierarchical collections, tags, writing roles, personal notes | Reuse across projects and manuscript sections |

An abstract summary and a complete article digest have separate source identities. Changed abstracts retain earlier snapshots and summaries. Changed article content receives a new exact-version digest. A pending record never claims completed reading.

## Automatic Capture and Summary Completion

`ads_api.py search` and `bigquery` capture their returned records automatically. The request includes the metadata fields needed for reuse. The JSON response retains the ADS response and adds `literature.run_id`, `captured`, `pending_summaries`, `reused_summaries`, and source hashes. `fulltext.py fetch` also captures its available metadata and exposes the same completion information. Preparation and capture leave scientific authorship to the agent.

Capture uses the local library; the remote requests are read-only. The no-library-write exception in [Core Invariants](../SKILL.md#core-invariants) specifies opt-out behavior and option placement.

Inspect each task's summary queue:

```bash
python3 "<skill-dir>/scripts/literature_db.py" pending --run-id <id>
```

Read the returned `source` for each entry. Author a concise paraphrase of the question, approach, result, and relevance supported by that source. Preserve uncertainty. If the record has only a title and bibliographic metadata, summarize its identity and stated topic. Include a source-level limitation in that short summary. Fill this batch structure using the exact returned identifiers and hashes:

```json
{
  "summaries": [
    {
      "identifier": "<bibcode, DOI, or arXiv ID>",
      "source_hash": "<hash from pending>",
      "summary": "<agent-authored source-based summary>",
      "keywords": ["<retrieval term>"],
      "collections": ["<scientific topic>/<subtopic>"],
      "roles": ["intro", "discussion"],
      "note": "<optional task-specific relevance>"
    }
  ]
}
```

`identifier`, `source_hash`, and `summary` are required. Every paper needs a topic collection before the research task is complete; supply `collections` here or preserve its existing memberships. The CLI accepts missing list fields for staged work. `check` exposes unfinished classifications. Keywords also become paper tags. Notes are appended separately. Summaries for the same source are idempotent; a different replacement summary is rejected to preserve earlier work.

```bash
python3 "<skill-dir>/scripts/literature_db.py" summarize --summaries "<summaries.json>"
python3 "<skill-dir>/scripts/literature_db.py" pending --run-id <id>
python3 "<skill-dir>/scripts/literature_db.py" check --run-id <id>
python3 "<skill-dir>/scripts/literature_db.py" runs
```

Finish all pages retrieved for the task. `pending` supports `--limit` and `--offset`. Process repeated batches from offset zero as summaries are completed. Without `--run-id`, it lists the latest pending snapshot per paper. `runs` records query parameters, retrieval counts, and remaining summaries.

`check --run-id <id>` verifies the task's summaries and topic memberships. It reports `needs_classification` and exits with code 1 while either requirement remains incomplete. Use plain `check` during requested whole-library maintenance. Inspect the existing `collections` tree before assigning paths; reuse its language and hierarchy. The agent chooses scientific classifications from the paper's content. The scripts persist and verify those choices.

Recover capture from a saved ADS response or a full-text manifest:

```bash
python3 "<skill-dir>/scripts/literature_db.py" capture --results "<response-or-manifest.json>" --query "<recorded scope>"
```

Capture validates the batch and commits it atomically. Storage errors follow the shared [failure routing](../SKILL.md#failure-routing).

## Local Lookup and Reading

Use lookup to select and verify local evidence. Apply the shared [reading scope](../SKILL.md#reading-scope) when investigating article content. The actions below describe that investigation path; catalog-only tasks can return the available records and their evidence levels.

```bash
python3 "<skill-dir>/scripts/literature_db.py" lookup "<identifier>" --topic "<scientific dimension>" --include-digest
python3 "<skill-dir>/scripts/literature_db.py" show "<identifier>"
python3 "<skill-dir>/scripts/literature_db.py" search "<concept or method>" --scope summary
python3 "<skill-dir>/scripts/literature_db.py" search "<exact article phrase>" --scope fulltext --mode phrase
python3 "<skill-dir>/scripts/literature_db.py" list
```

| Lookup state | Action |
|---|---|
| `not_found` | Retrieve metadata and the required article version, then complete its source brief and article digest. |
| `needs_reading` | Inspect any reported integrity failure, reuse valid local material, and complete the missing paper-wide reading and digest. |
| `reusable` | Reuse the selected complete version and stored artifacts. |
| `targeted_reading` | Read relevant complete sections locally and merge the missing facets. |
| `version_changed` | Retrieve and complete the exact requested version. |

Explicit arXiv suffixes such as `v2` require corresponding stored version provenance. `--sha256` selects a known artifact, historical artifact, text, or canonical-content hash. Choose online discovery according to the freshness, coverage, and source-scope criteria in [Core Invariants](../SKILL.md#core-invariants).

Lookup validates stored article and text integrity. Its `version.manifest_path` is suitable for later ingest and merging. New stored manifests point to durable article objects, so clearing the download cache preserves local reuse.

Check every identifier in the task's investigation set. Pass a small set directly; `--identifiers-file` accepts a UTF-8 file with one exact identifier per line for large or resumable queues. Full-reading completion and source-summary completion have separate checks:

```bash
python3 "<skill-dir>/scripts/literature_db.py" reading-check "<identifier-1>" "<identifier-2>"
python3 "<skill-dir>/scripts/literature_db.py" reading-check --identifiers-file "<reading-list.txt>"
```

`reading-check` verifies declared full or visual coverage, exact-version lookup, stored-object integrity, and scientific topic membership. It is read-only and exits with code 1 while any listed entry remains incomplete. Its `needs_reading` and `needs_classification` fields form the remaining queue. `check --run-id <id>` covers captured source summaries and topics. The agent remains responsible for the reading and scientific authorship behind these structural checks.

Search scopes are `metadata`, `summary`, `fulltext`, and `all`. Terms mode requires all terms; phrase mode matches a phrase. SQLite FTS5 serves token queries when available. Continuous CJK text uses literal case-insensitive substring matching. `--mode fts` requires FTS5 and covers complete-digest search documents. Source-level briefs participate in terms and phrase searches.

`--topic` filters complete-digest facets. `--year-from`, `--year-to`, and `--limit` bound results. `--collection`, `--role`, and `--tag` filter personal organization. Collection filters include their descendants. Search results label the matching evidence layer and article version.

## Classification and Manuscript Uses

```bash
python3 "<skill-dir>/scripts/literature_db.py" annotate "<identifier>" --collection "FRB/Polarization/Circular" --collection "My manuscript/Discussion" --tag "FAST" --role discussion --note "<comparison and its limitations>"
python3 "<skill-dir>/scripts/literature_db.py" collections
python3 "<skill-dir>/scripts/literature_db.py" collections --create "FRB/Polarization" --description "<source-backed thematic overview>"
python3 "<skill-dir>/scripts/literature_db.py" list --collection "FRB" --role discussion
```

Collection paths support up to twelve levels. Parent directories are created automatically. Papers can belong to multiple branches; parent counts deduplicate papers. Writing roles are `review`, `intro`, `methods`, `discussion`, and `comparison`. Additions preserve memberships, tags, and notes. Use collection descriptions for concise thematic syntheses with identifiable paper references. Scientific details remain in each article's digest.

For an existing library, read each paper's stored overview, keywords and facets, prepare a reviewed batch, and run `organize --annotations <file.json>`. The file contains an `annotations` array; each item has `identifier`, a nonempty `collections` list, and optional `tags`, `roles`, and `note`. The operation validates all items within one transaction and preserves earlier annotations. Schema migration creates the catalog tables; content-based classification uses this separate reading and organization step. Full digest ingest also saves its keywords as tags.

## Web Browsing and Citation Export

When the user asks to start or open the Web library, resolve `<skill-dir>` from the installed `SKILL.md`. A Codex standalone installation normally uses `~/.agents/skills/nasa-ads`; a Claude standalone installation uses `~/.claude/skills/nasa-ads`. Marketplace plugins use the path of the loaded skill. The complete directory includes `scripts/adslib.py`, `scripts/library_web.py`, `scripts/library_catalog.py`, and `assets/library/`.

During skill installation or a request to register the shortcut, run `python3 "<skill-dir>/scripts/adslib.py" install`, then verify `adslib --version` in a fresh shell. This registers a user-level wrapper pointing to this installed script and the working Python interpreter. Windows uses `~/.local/bin/adslib.cmd` for PowerShell and a sibling `adslib` shell script for Git Bash and preserves existing user PATH entries. macOS/Linux/WSL use `~/.local/bin/adslib`; the installer adds a managed PATH block to the active bash/zsh/sh configuration when needed. `install --bin-dir <path> --no-path` supports a user-managed command directory. Existing foreign launchers are preserved. Re-register after moving the installed skill or changing its interpreter. A host plugin installation copies resources; command registration completes shell setup.

Ordinary Web launch uses `adslib`, or the bundled script directly when the command is unregistered:

```bash
adslib
python3 "<skill-dir>/scripts/adslib.py"
```

The launcher defaults to `open`: it opens the browser and starts or reuses a managed background service. `start` starts in the background without opening a browser; `status` prints the URL, library, version and PID; `stop` shuts down the matching instance; `restart` starts a replacement in the background; `serve` runs in the foreground until Ctrl+C. Use the same `--library-dir <path>` and preferred `--port <number>` for subsequent commands. An occupied port gets an available alternative, which is recorded for discovery. `--no-open` suppresses browser launch. Windows background processes use hidden windows. The CLI handles background process creation and authenticated shutdown. Verify `status`, `/api/stats`, and the page before reporting the URL. Status returns 3 when no managed instance is running; repeated stop succeeds. Startup prints a log path. Runtime state is separate from the literature database; preserve the same user and runtime-directory environment for control.

For foreground service operation, use:

```bash
python3 "<skill-dir>/scripts/adslib.py" serve --port 8765
```

The Web server uses the Python standard library and bundled assets. Local browsing needs no ADS token. An absent database displays an empty library without creating files; `init` is needed when upgrading an existing incompatible schema. Installing the skill provides its code. To reuse a personal library on another computer, transfer a CLI backup and restore it to a new destination, which rewrites managed article paths. Use the default destination or the same `NASA_ADS_LITERATURE_DIR` for subsequent searches and Web browsing. Stop and restart the server when changing its library directory.

On Windows, use `python` or `py -3` with the same arguments. The server supports collapsible topic navigation, combined topic/role/tag/year filters, sorting, summaries directly in the list, focused reading, scientific facets, version downloads, and BibTeX export for selected papers or the entire filtered view (up to 2000 papers). Narrow windows use a navigation drawer and a separate reader with a return button. The library information button shows the actual storage directory. Refresh reads current data from that directory. The page uses bundled assets and loads no external scripts. It binds to localhost and blocks cross-origin access. Classification and notes are edited through the CLI or agent.

Apply a year range with the year control's apply button. Invalid ranges keep the previous results and show persistent validation feedback. Applied years, reading levels, and search scopes appear as removable filters. The URL preserves filters, sorting, pagination, the active paper, and its detail tab across reloads and browser back/forward navigation. Copied article links include that browsing context. Connection failures show an inline message and a refresh recovery action. Keyboard shortcuts support `/` for search, `Escape` for closing the year control or reader, and arrow keys within detail tabs.

## Citation Export

For a citation-only task, use this section directly. Stored BibTeX and metadata-derived exports work offline. For missing papers, retrieve their metadata through ADS `bigquery`, finish that run's source summaries and scientific topic assignments, then export citations. Subsequent content investigation follows the shared [reading scope](../SKILL.md#reading-scope).

Export the local bibliography:

```bash
python3 "<skill-dir>/scripts/literature_db.py" citations "<identifier>"
python3 "<skill-dir>/scripts/literature_db.py" citations --collection "My manuscript" --output "<references.bib>"
python3 "<skill-dir>/scripts/literature_db.py" citations --all --output "<personal-library.bib>"
```

Cached official ADS entries retain their exact keys and source. A record without a cached official entry receives BibTeX generated from its stored metadata, with a provenance comment. Metadata-derived exports include only known fields; publication details may be incomplete.

Fetch and cache official entries for selected known papers:

```bash
python3 "<skill-dir>/scripts/literature_db.py" citations "<identifier>" --fetch
```

This explicit online operation uses ADS credentials. Existing official entries are reused. Direct arXiv records with pending ADS indexing keep their metadata-derived entries. Citation output files are written outside the managed database directory.

A bulk unedited BibTeX export obtained through `ads_api.py export` can be cached with `import-citations --bibtex <ads-export.bib>`. Every entry must identify the paper's current library bibcode; unknown records, duplicates and incomplete entries abort the transaction. Refresh existing metadata through `enrich` first when ADS indexing or publication status has changed.

## Integrity, Backup, and Migration

`lookup`, `show`, `search`, `list`, `stats`, `pending`, `check`, `reading-check`, `runs`, ordinary `collections`, offline `citations`, Web requests, and `audit` open read-only connections. Ordinary reads of a missing library create no files. `audit` and `backup` require an existing database.

```bash
python3 "<skill-dir>/scripts/literature_db.py" stats
python3 "<skill-dir>/scripts/literature_db.py" audit
python3 "<skill-dir>/scripts/literature_db.py" backup --destination "<new backup directory>"
python3 "<skill-dir>/scripts/literature_db.py" restore "<backup directory>" --destination "<new library directory>"
python3 "<skill-dir>/scripts/literature_db.py" init
```

Database schema 3 adds the personal catalog to existing complete article records. `init` automatically creates a backup before migrating schema 1 or 2. Schema 1 migration retains the active highest digest revision and enforces one current digest per exact version. Existing current digests and article objects remain available. Ordinary write commands require the migration to be performed explicitly.

Backups contain a consistent SQLite snapshot, article objects, and `backup.json`. Restore requires a new destination and rewrites managed file references. It checks object hashes and database integrity before publishing the restored directory. The original library remains available at its original path.

The audit checks SQLite integrity, foreign keys, digest validity, complete reading state, search parity, primary and historical objects, and their hashes. An unhealthy audit returns a nonzero exit code. `--skip-hashes` provides a structural pass. Pending abstract summaries represent incomplete reading work and appear in the summary queue.

Use `enrich --manifest <file>` to add metadata and reconcile identifiers for an existing paper. Confirmed journal metadata can upgrade a preprint's bibliographic record. Use `reindex` to rebuild derived complete-digest search documents. A complete-digest replacement uses `backup` followed by approved `ingest --replace-digest`.
