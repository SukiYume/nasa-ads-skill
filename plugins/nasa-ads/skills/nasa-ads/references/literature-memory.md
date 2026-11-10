# Personal Literature Library

Contents: [Storage and evidence levels](#storage-and-evidence-levels) · [Screening before capture](#screening-before-capture) · [Automatic capture and summary completion](#automatic-capture-and-summary-completion) · [Local lookup and reading](#local-lookup-and-reading) · [Read stored passages](#read-stored-passages) · [Query stored evidence](#query-stored-evidence) · [Classification and manuscript roles](#classification-and-manuscript-roles) · [Citation export](#citation-export) · [Web library](#web-library)

Load this reference for search capture, source summaries, local lookup, stored-evidence queries, classification, citations, and the Web library. Apply [Core Invariants](../SKILL.md#core-invariants). Digest authoring lives in [digest-schema.md](digest-schema.md); backup, restore, and repair live in [library-maintenance.md](library-maintenance.md).

All commands below run `python3 "<skill-dir>/scripts/literature_db.py" [--library-dir <dir>] <subcommand>`; the examples show only the subcommand.

## Storage and Evidence Levels

The default root is `%LOCALAPPDATA%/nasa-ads/literature` on Windows and `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature` on macOS/Linux. `NASA_ADS_LITERATURE_DIR` or `--library-dir <path>` selects another root. The root holds `literature.sqlite3` and a verified `objects/` tree; manage both only through the CLI.

| Layer | Contents | Supports |
|---|---|---|
| Metadata record | Bibliographic identity without an abstract | Identification and relevance triage |
| Abstract record | Source abstract plus an agent-authored source summary | Abstract-level statements and later selection |
| Complete article version | Verified article and text, full or whole-document visual reading, one complete digest | Claims about data, methods, parameters, figures, tables, and limitations, with locators |
| Organization | Hierarchical collections, tags, writing roles, personal notes | Reuse across projects and manuscript sections |

Abstract summaries and article digests have separate source identities. A changed abstract keeps earlier snapshots and summaries; changed article content receives a new exact-version digest. A pending record never claims completed reading.

## Screening Before Capture

Preview exploratory searches with `ads_api.py --no-store search` and the research field set in [SciX CLI](ads-cli.md#search). Compare each result with the requested objects, physical question, and source scope before writing to the library:

- Bare object numbers and wildcards can match reference lists, grant numbers, or unrelated identifiers; prefer `title:` and `abs:` for object names and confirm the actual subject.
- Keep relevant counterevidence and alternative models. Record uncertain relevance as an explicit candidate state.
- Label datasets, meeting abstracts, news, and proposals with their actual document type.

Save the accepted original records in `response.docs` of a SciX response file. Source fields keep the retrieved metadata and abstract; agent interpretation belongs in `summary`, notes, or a digest. For a direct publisher or arXiv record, keep its source text and URL. Preserve the original `numFound` and describe the query, page boundaries, screening criteria, and returned/retained counts in `--query`:

```bash
capture --results "<screened-response.json>" --query "<query; page; criteria; returned/retained counts>"
```

An empty retained set needs no capture. Exact metadata retrieval for already selected identifiers can use the default automatic capture.

## Automatic Capture and Summary Completion

`ads_api.py search`, `ads_api.py bigquery`, and `fulltext.py fetch` capture their returned records by default. The output adds a `literature` object with `run_id`, `captured`, `pending_summaries`, `reused_summaries`, `unread_articles`, source hashes, and `owed`, the steps this run still needs: source summaries, topics, and the full reading of a fetched article. An empty `owed` means the run is complete. Capture never writes summaries; the agent authors them from the stored source:

```bash
pending --run-id <id>
```

For each entry, paraphrase the question, approach, result, and relevance supported by the returned `source`, and keep its uncertainty. A record with only bibliographic metadata gets a short identity summary that names that limitation. Fill a batch with the exact identifiers and hashes from `pending`:

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

`identifier`, `source_hash`, and `summary` are required. Supply `collections` here or keep existing memberships; every paper needs a topic before the task is complete. Keywords also become tags, and notes are appended. Repeating the same summary is idempotent; a different summary for the same source is rejected to protect earlier work.

A summary rests on the title and abstract. A new snapshot of the same paper with the same title and abstract, such as the full-text fetch of a captured search record, a publication update that changes only volume and pages, or the same abstract with other character entities, inline tags, or dash styles, reuses the earlier summary; capture counts it under `reused_summaries` and names the source in `summary_reused_from`. `summarize` fills pending snapshots of the same title and abstract the same way and reports them as `reused`. Records without an abstract also need the same authors, venue, year, and document type.

```bash
summarize --summaries "<summaries.json>"
check --run-id <id>
check --recent 12
runs
```

`pending` pages with `--limit` and `--offset`; without `--run-id` it lists every unfinished snapshot, including historical ones. `check` exits 1 while its scope has pending summaries, papers without a topic (`needs_classification`), or articles that a fetch or import prepared and no complete digest covers (`needs_reading`, with each `manifest_path`). `--run-id` covers one run; `--recent <hours>` covers every search and fetch captured within that window, so one command closes a task; plain `check` covers the whole library. `runs` lists query parameters, retrieval counts, and remaining summaries. Capture commits each batch atomically; `capture --results <response-or-manifest.json>` recovers from a saved SciX response or full-text manifest.

## Local Lookup and Reading

Use `lookup` to decide whether a paper needs reading:

```bash
lookup "<identifier>" --topic "<scientific dimension>"
```

`lookup` returns the paper's overview (tldr, summary, questions, study types) and its facet labels with finding counts. Retrieve the citable results with `findings --paper "<identifier>"` and their passages with [`passage`](#read-stored-passages); `--include-digest` adds the complete stored digest, and `show` lists every stored version. A `--topic` is covered when it occurs in a facet's text, findings, quotes, or value names, models, and conditions, or among the paper's entities, keywords, datasets, and methods.

| Lookup state | Action |
|---|---|
| `not_found` | Retrieve metadata and the article version, or [import](fulltext.md#import-a-local-copy) a copy the user supplies, then complete its source summary and digest. |
| `needs_reading` | Inspect any reported integrity failure, reuse valid local material, and complete the paper-wide reading and digest. |
| `reusable` | Reuse the complete version through `findings`, `parameters`, and `passage`. |
| `targeted_reading` | Find the relevant sections with `passage --outline` or `--grep`, read them with `passage --section`, and merge the missing facets. |
| `version_changed` | Retrieve and read the exact requested version. |

An explicit arXiv suffix such as `v2` requires matching stored version provenance. `--sha256` selects a known artifact, text, or canonical-content hash, including historical artifacts. Lookup verifies stored article and text integrity, and its `version.manifest_path` points to durable stored objects suitable for later merging, so clearing the download cache keeps local reuse intact.

Check full-reading completion for the investigation set, directly or from a UTF-8 file with one identifier per line:

```bash
reading-check "<identifier-1>" "<identifier-2>"
reading-check --identifiers-file "<reading-list.txt>"
```

`reading-check` verifies declared full or visual coverage, exact-version lookup, object integrity, and topic membership. It is read-only, exits 1 while any entry is incomplete, and lists the remaining queue in `needs_reading` and `needs_classification`.

### Read Stored Passages

`passage` reads a bounded part of a stored article version, after verifying its text hash:

```bash
passage "<identifier>" --outline
passage "<identifier>" --finding "<finding_id>"
passage "<identifier>" --section "3.2" --section "Discussion"
passage "<identifier>" --grep "<term>" --grep "<second term>"
```

| Request | Returns |
|---|---|
| `--outline` (also the default) | Stored section headings with starting line, word count, and the digest's gist |
| `--finding` | The paragraph its quote anchors; without a quote, the paragraph naming its table, figure, or equation, or the start of its locator section; the finding's statement and locator come with it |
| `--section` | One section, matched by number, heading, or heading words, such as `2.3`, `Sec. 4`, or `Discussion`; headings in the digest's `reading.sections` locate sections that the stored outline missed |
| `--grep` | Paragraphs containing every term, with their section headings; `term_matches` counts all matches |

Each passage reports its `section`, `match` type, `lines` in the stored text, and `truncated` when it reached `--max-chars` (default 3000; `0` returns complete passages). A truncated section adds `section_lines` for reading the rest by line range from `version.text_path`. `--context <n>` adds neighboring paragraphs, `--limit` caps grep paragraphs (default 5), and `--sha256` selects a known version. Requests that resolve nowhere are listed in `unresolved`; a scan without extracted text returns the finding locators and the artifact path.

## Query Stored Evidence

Search concepts, findings, and text:

```bash
search "<concept or method>" --scope summary
search "<exact article phrase>" --scope fulltext --mode phrase
list --collection "<topic path>" --role discussion
```

Scopes are `metadata`, `summary`, `fulltext`, and `all`. `terms` mode requires every term, `phrase` matches the phrase, and `fts` uses SQLite FTS5 syntax over complete digests. Continuous CJK text uses literal case-insensitive matching. `--topic` filters digest facets; `--year-from`, `--year-to`, `--collection` (including descendants), `--role`, `--tag`, and `--limit` narrow results. Results label the evidence layer and article version, and include matching findings with their values and locators.

Retrieve citable findings and values as rows for comparison tables, claim checks, and citations. `findings` returns one row per finding, including inferences, predictions, and constraints without numbers; `parameters` returns one row per stored value:

```bash
findings "<concept, object, or mechanism>" --kind interpretation
findings --paper "<identifier>"
parameters "<quantity, symbol, or model>"
parameters "<quantity>" --entity "<object name>" --status fitted --status measured
parameters "<quantity>" --collection "<topic path>" --format csv --output "<table.csv>"
```

Both commands accept `--paper`, `--entity`, `--kind`, `--status`, `--collection` (including descendants), `--role`, `--tag`, `--year-from`, `--year-to`, `--limit` (default 200), `--format json|csv`, and `--output`. Every row carries the paper's `citekey`, `bibcode`, year, version, reading status, facet, `finding_id`, finding statement, kind, confidence, `locator`, and `cited_from`. Finding rows add `quote`, `compared_with`, `values`, and `keywords`; `passage --finding <finding_id>` returns the stating paragraph. Value rows add `name`, `symbol`, `value`, `range`, `uncertainty`, `unit`, `qualifier`, `status`, `model`, `dataset`, `method`, and `condition`, and inherit the finding's `cited_from` when the value has none. For `findings`, `--status` keeps findings that report a value with that status.

Latin query terms match at word starts; other scripts match as substrings. Rows whose own text matches every term (`"match": "finding"` or `"value"`) precede rows matched only through the enclosing finding or facet (`"context"`). `--entity` keeps papers whose digest names that object, alias, or dataset identifier; include the object in the query to select its specific findings. `missing` and `without_complete_digest` list requested papers that still need capture or reading, and `truncated` reports a result set beyond `--limit`. CSV output is UTF-8 with a byte-order mark for spreadsheet tools, and `--output` must lie outside the library directory.

`cited_from` names the work a restated result comes from. [Citing specific results](research-writing.md#cite-specific-results) covers how these rows enter manuscript writing.

## Classification and Manuscript Roles

```bash
collections
collections --create "FRB/Polarization" --description "<source-backed thematic overview>"
annotate "<identifier>" --collection "FRB/Polarization/Circular" --collection "My manuscript/Discussion" --tag "FAST" --role discussion --note "<comparison and its limitations>"
organize --annotations "<annotations.json>"
```

Collection paths support up to twelve levels and create their parents. A paper can belong to several branches; parent counts deduplicate papers. Writing roles are `review`, `intro`, `methods`, `discussion`, and `comparison`. Additions preserve existing memberships, tags, and notes. Collection descriptions hold concise thematic syntheses with identifiable paper references; detailed evidence stays in each paper's digest.

Before creating a branch, compare its concept with existing paths, including synonyms and translations, and reuse a matching branch in the library's established language. For bulk classification, read each paper's stored overview, keywords, and facets, then write an `annotations` array whose items have `identifier`, a nonempty `collections` list, and optional `tags`, `roles`, and `note`. `organize` validates the whole batch in one transaction and preserves earlier annotations. Full digest ingest saves digest keywords as tags.

## Citation Export

Citation-only tasks use this section without opening article content.

```bash
citations "<identifier>"
citations "<identifier>" --fetch
citations --collection "My manuscript" --output "<references.bib>"
citations --all --output "<personal-library.bib>"
```

Cached official SciX entries keep their exact keys and source. A paper without one receives BibTeX generated from stored metadata with a provenance comment; it includes only known fields, lists the first ten authors followed by `others` as SciX exports do, and braces collaboration names. `--fetch` caches official entries for the selected papers using SciX credentials and reuses existing ones. Changes to citation-bearing metadata, including DOI and arXiv identifiers, invalidate a cached entry. Direct arXiv records awaiting SciX indexing keep metadata-generated entries. Output files must lie outside the library directory.

For papers missing from the library, retrieve metadata with `ads_api.py bigquery`, complete that run's summaries and topics, then export. A manuscript's reference list reaches bibcodes through [`ads_api.py reference`](ads-cli.md#references-objects-and-journals). Other citation formats use [`ads_api.py export`](ads-cli.md#citation-export).

## Web Library

Run the registered `adslib` command, or the bundled script when the command is unregistered:

```bash
adslib
python3 "<skill-dir>/scripts/adslib.py"
```

`open` (the default) starts or reuses a background service and opens the browser; `start`, `status`, `stop`, `restart`, and `serve` (foreground) manage it. Pass the same `--library-dir <path>` to later commands; `status`, `stop`, `restart`, and `open` find that library's service on whatever port it uses. `--port <number>` sets the preferred port for a new service and chooses among several services of one library; an occupied port is replaced by a free one and recorded for discovery. `--no-open` suppresses the browser. `status` exits 3 when no managed instance runs, and repeated `stop` succeeds. Verify `status`, `/api/stats`, and the page before reporting the URL. The service binds to localhost, uses bundled assets, needs no SciX token, and shows an empty library when no database exists. Classification and notes are edited through the CLI.

Register the command once during installation or on request, then verify it in a fresh shell:

```bash
python3 "<skill-dir>/scripts/adslib.py" install
adslib --version
```

Registration writes a user-level wrapper pointing at this installed script and the working Python: `~/.local/bin/adslib.cmd` plus a Git Bash script on Windows, and `~/.local/bin/adslib` with a managed PATH block for bash, zsh, or sh on macOS, Linux, and WSL. Existing PATH entries and foreign launchers are preserved. `install --bin-dir <path> --no-path` uses a user-managed directory. Re-register after moving the skill or changing Python. Standalone installs usually live at `~/.agents/skills/nasa-ads` (Codex) or `~/.claude/skills/nasa-ads` (Claude); marketplace plugins use the loaded skill's path.
