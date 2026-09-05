---
description: "Search, inspect, maintain, and update the personal literature library"
argument-hint: '<lookup, search, collections, annotate, organize, pending, summarize, check, serve, citations, backup, restore, or paper topics>'
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Literature Memory

Use the persistent literature database for: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/SKILL.md` for shared task routing and Core Invariants, then the relevant sections of `references/literature-memory.md` for the command below. Load `references/digest-schema.md` for digest work. Local browsing, search, and cached citation export work without an ADS token.
2. Try `python3`, `python`, then `py -3` to run `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/literature_db.py`. Manage the SQLite database and object store exclusively through this CLI.
3. Map the request to the narrow command:
   - known paper plus scientific topics: `lookup <identifier> --topic '<topic>' ...`
   - local concept or finding: `search '<query>' --scope summary`
   - exact article phrase or unmodeled detail: `search '<query>' --scope fulltext`
   - complete stored digest and provenance: `show <identifier>`
   - hierarchy and topic summaries: `collections` or `collections --create <path> --description <summary>`
   - paper classification and personal notes: `annotate <identifier> --collection <path> --role methods --tag <tag> --note <note>`
   - unfinished summaries: `pending`, followed by source-grounded `summarize --summaries <json>`
   - reviewed bulk classifications: `organize --annotations <json>`
   - summary and classification completion: `check --run-id <id>`; plain `check` for whole-library maintenance
   - search history: `runs`
   - reading completion for the investigation set: `reading-check <identifiers>` or `reading-check --identifiers-file <list.txt>`
   - local Web reader: run the registered `adslib` command or bundled `scripts/adslib.py`; use `open`, `start`, `status`, `stop`, `restart`, or `serve` for the requested operation and verify the active service
   - register the Web command during installation or explicit setup: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/adslib.py" install`
   - offline citations: `citations <identifiers>`; add `--fetch` for official ADS entries
   - cache an unedited ADS export: `import-citations --bibtex <ads-export.bib>`
   - restoration into a new library directory: `restore <snapshot> --destination <new-directory>`
   - collection health and counts: `stats`
   - full read-only health review: `audit`
   - recoverable maintenance snapshot: `backup`
   - refreshed metadata for an existing record: `enrich --manifest '<manifest.json>'`
4. Apply the shared reading scope when the request investigates article content. Follow the library reference's lookup states into `references/fulltext.md` and `references/digest-schema.md` as needed.
5. Match the handoff to the task. For Web, return its URL, directory, paper count, and stop instructions. For citations, return the requested entries or file with provenance. For scientific lookup, return matching papers, reading coverage, evidence locators, and useful stored paths. Cite the original paper in scientific answers. Run whole-library completion checks during requested maintenance; focused requests keep their own completion scope.
6. The bundled CLI exposes no delete operation. A repair or relocation starts with a CLI backup. Perform destructive operations within the user's explicit authorization. Existing authorization covers the stated action and scope.
