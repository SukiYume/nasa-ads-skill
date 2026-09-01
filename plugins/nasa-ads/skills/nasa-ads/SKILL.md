---
name: nasa-ads
description: Search and investigate NASA ADS astronomy and astrophysics literature, retrieve and read lawful article full text, preserve complete version-aware paper knowledge in a searchable local database, reuse prior reading, check claims, export citations, manage ADS libraries, inspect metrics, and find related work. Use for astronomy literature reviews, papers, citations, BibTeX, arXiv/DOI/bibcode lookup, full-text reading, literature memory, and Chinese requests including 文献, 论文, 文献调研, 查论文, 全文, 阅读论文, 文献数据库, 引用导出, ADS, arXiv, 天文文献, and 天体物理论文.
---

# NASA ADS Agent Workflow

Use NASA ADS, lawful article sources, and the local evidence-aware literature database to search, read, preserve, and synthesize astronomy research evidence.

## Core Invariants

1. Resolve ADS credentials from `ADS_API_TOKEN`, then `ADS_DEV_KEY`. Keep credentials out of output, logs, URLs, source files, redirects, and external article requests.
2. Search ADS for current literature on every new research task. Local paper knowledge supplies reusable evidence from previously read versions.
3. Use metadata and abstracts for relevance triage. Article-level claims require lawful full text, recorded whole-document visual reading, or an exact reusable database version with relevant facet coverage.
4. Run `literature_db.py lookup` before opening article content. Article content includes a body section, page, figure, caption, table, equation, appendix, supplementary passage, or quotation context.
5. Persistent literature memory is the default workflow. Every opened exact version without a reusable complete record receives complete reading, a validated layered digest, and ingest during the same task. This rule also applies when the user asks about one figure or isolated detail.
6. A changed canonical-content version starts its own complete-ingest gate. `targeted` reading and `--merge` extend an exact version that already has a complete `full` or whole-document `visual` digest.
7. The original article remains the citable source. The database records version identity, reading coverage, scientific facets, evidence locators, and reusable summaries.
8. Research ingestion covers papers opened for the current request. Maintenance of unrelated records requires a database-maintenance request. Destructive library operations and digest replacement require explicit confirmation and a recoverable backup.

## Task Routing

- ADS search, batch metadata, citation export, metrics, citation helper, or resolver: load [references/ads-cli.md](references/ads-cli.md) and use `scripts/ads_api.py`.
- ADS Libraries: load [references/libraries.md](references/libraries.md).
- Local lookup, search, inspection, statistics, audit, backup, enrichment, or indexing: load [references/literature-memory.md](references/literature-memory.md) and use `scripts/literature_db.py`.
- Full-text discovery, extraction, outline, or visual reading: load [references/fulltext.md](references/fulltext.md) and use `scripts/fulltext.py`.
- Digest authorship, validation, ingest, merge, or approved replacement: load [references/digest-schema.md](references/digest-schema.md).
- Literature review, claim check, or multi-paper synthesis: begin with `ads-cli.md`. Load `literature-memory.md` when papers become prospective material evidence. Load `fulltext.md` and `digest-schema.md` for each material paper whose article content needs to be opened.
- Unsupported ADS endpoint or CLI option: load [references/http-fallback.md](references/http-fallback.md) and verify the current [ADS API documentation](https://ui.adsabs.harvard.edu/help/api/).

Load only the references reached by the task route.

## Transport

1. Resolve bundled scripts relative to this `SKILL.md`.
2. Try `python3`, `python`, then `py -3` until one launches the required CLI.
3. Use the bundled CLIs for supported ADS calls, retrieval, extraction, caching, database, hashing, and indexing operations.
4. Direct HTTP supports documented ADS endpoints when Python is unavailable or the bundled API CLI lacks the operation. Full-text preparation and persistent-memory workflows require Python 3.10 or newer.
5. Preserve the selected transport's validation and error result. API failures remain failures.

## Literature Research

1. Define the question, operational categories, date range, and evidence criteria.
2. Build independent query families from exact terms, synonyms, competing interpretations, known objects or authors, and seed-paper citation chains.
3. Inspect result counts, returned rows, pagination, filters, response shape, and rate limits when they affect coverage.
4. Deduplicate by bibcode, reconcile alternate records, label publication state, and triage by metadata and abstract.
5. Run local `lookup` with the requested scientific topics before opening every prospective material paper.
6. Reuse an exact complete record when its facets cover the request. Check decisive values, equations, figure readings, table cells, and quotations against the stored artifact.
7. For every opened version that requires complete ingest, fetch the best lawful source, run `outline`, read all material sections, inspect every content-bearing page for visual records, build the digest, validate it, and ingest it before using article details.
8. Capture every independently reusable scientific dimension found during the complete reading. Record section-to-facet coverage, methods, context, limitations, data products, references, and administrative material according to `digest-schema.md`.
9. Compare recent evidence with influential or foundational results. Track direct evidence, counterevidence, selection effects, adjacent work, and method dependence.
10. Return a reader-facing synthesis with article links, calibrated evidence, version-aware full-text coverage, database-reuse counts, and a concise method note.

## Coverage and Evidence

- A focused review uses independent query families, abstract triage, and complete reading of the manageable material-paper set.
- A broad review covers terminology, synonyms, counterclaims, selection effects, seed-paper citations or references, recent work, and influential work. State the sampling rule and uncovered scope when the result set exceeds the manageable reading set.
- `numFound` measures ADS matches. Relevance follows record inspection.
- Label evidence as published full text, accepted manuscript, preprint full text, whole-document visual reading, or abstract only.
- Abstract-only records support abstract-level statements and relevance triage.
- Scientific sufficiency follows conceptual coverage, evidence quality, and version fit.
- Describe an empty result as “no matching records found for these queries,” followed by the exact query scope.
- Keep observational labels separate from intrinsic physical classes. A nondetection supports a bounded nondetection statement.

## Result Presentation

For literature research, include the answer, representative records, ADS links, DOI or arXiv links, thematic synthesis, search scope, evidence limitations, selected article versions, reading coverage, and counts for reused, verified, augmented, newly ingested, and version-refreshed papers.

Build ADS links as `https://ui.adsabs.harvard.edu/abs/<bibcode>` and arXiv links from identifiers beginning with `arXiv:`.

## Failure Routing

- Missing ADS credentials: provide the [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token) link and the supported environment-variable names, then stop the ADS operation. Direct arXiv identifiers remain available to `fulltext.py`.
- HTTP or ADS API failure: report the authentication, permission, identifier, redirect, payload, or rate-limit context supplied by the CLI.
- `needs_visual_reading`: follow the bounded native-vision or rendering workflow in `fulltext.md`.
- `abstract_only`: report attempted sources and keep conclusions at abstract level.
- Exact version requires complete ingest: finish the full or whole-document visual workflow before using its article details.
- Literature database unavailable or corrupt: preserve fetched artifacts and digest files, pause use of newly opened article details, and report the storage failure.
- SQLite FTS5 unavailable: use the CLI's deterministic substring fallback.
- Stored complete version lacks a requested facet: read the complete relevant sections and merge the added evidence.
- Approved digest repair: create a backup, rebuild a complete digest from the stored article, and use `--replace-digest`.
