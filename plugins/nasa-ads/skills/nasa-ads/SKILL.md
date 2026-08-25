---
name: nasa-ads
description: Search and investigate NASA ADS astronomy and astrophysics literature, retrieve and read lawful article full text, preserve rich multi-topic paper knowledge in a searchable local database, reuse prior full-text reading, check claims, export citations, manage ADS libraries, inspect metrics, and find related work. Use for literature reviews, papers, citations, BibTeX, arXiv/DOI/bibcode lookup, full-text reading, literature memory, libraries, astronomy, and astrophysics, plus Chinese requests including 文献, 论文, 文献调研, 查论文, 全文, 阅读论文, 文献数据库, 引用导出, ADS, arXiv, 天文文献, and 天体物理论文.
---

# NASA ADS Agent Workflow

Use NASA ADS, lawful article sources, and the local evidence-aware literature database for astronomy research. This file is the agent runtime contract. The repository README is the human guide for project capabilities, installation, configuration, verification, and troubleshooting.

## Core Rules

1. Check `ADS_API_TOKEN`, then `ADS_DEV_KEY`, before an ADS API workflow.
2. Never print, log, commit, or place the token in a URL or source file.
3. Never follow an authenticated API redirect or forward the token to an article host.
4. Keep research calls read-only by default.
5. Confirm immediately before deleting or emptying a library, bulk removal, permission changes, replacing or deleting a note, or transferring ownership.
6. Describe an empty search as “no matching records found for these queries.” Search results cannot establish that no relevant literature exists.
7. Separate observational labels from intrinsic physical classes; a nondetection is not proof of absence.
8. Search ADS for current literature on every new research task even when local paper knowledge is reusable.
9. Use abstracts only to triage relevance. Claims about article content require full text, recorded visual reading, or an exact reusable database version with matching facet coverage.
10. Ingest only material papers read beyond the abstract and summarized with evidence locators.

## Task Routing

- ADS search, batch metadata, citation export, metrics, citation helper, or resolver: load [references/ads-cli.md](references/ads-cli.md) and use `scripts/ads_api.py`.
- Full-text retrieval or article reading: load [references/fulltext.md](references/fulltext.md) and use `scripts/fulltext.py`.
- Local paper lookup, digest inspection, topic or full-text search, ingest, or database statistics: load [references/literature-memory.md](references/literature-memory.md) and use `scripts/literature_db.py`.
- Literature question, claim check, or multi-paper synthesis: load all three references above, then follow Literature Research and Coverage Standard.
- ADS Libraries: load [references/libraries.md](references/libraries.md).
- Another ADS endpoint or an unavailable CLI option: load [references/http-fallback.md](references/http-fallback.md) and verify the current [ADS API documentation](https://ui.adsabs.harvard.edu/help/api/).

## Transport Selection

1. Resolve bundled scripts relative to this `SKILL.md`.
2. Try `python3`, then `python`, then `py -3` until one can run the required CLI.
3. Use the bundled CLI for every supported operation. Do not recreate its request, download, extraction, cache, database, or index logic with temporary code, curl, or PowerShell.
4. Use direct HTTP only when Python 3 is unavailable, the task uses ADS Libraries, the endpoint is outside the CLI, or current official documentation confirms a requested option that the installed CLI does not expose.
5. Correct or report an API error through the selected transport. Do not change transports to bypass it.

## Literature Research

1. Define the question, operational categories, date range, and evidence that would support or weaken the claim.
2. Build independent query families from exact terms, synonyms, competing interpretations, known objects or authors, and seed-paper citation chains.
3. Request the necessary metadata, inspect `numFound`, returned rows, pagination, response shape, and rate limits when relevant.
4. Deduplicate by bibcode, reconcile alternate records, label record type and publication status, and triage material papers by abstract.
5. Run `literature_db.py lookup` for every prospective material paper and include the scientific topics required by the question.
6. Reuse an exact stored version only when its digest covers those facets. Verify decisive numbers, equations, table cells, figure readings, and quotations against the stored article.
7. For a database miss, changed version, missing digest, or uncovered facet, retrieve the best lawful version with `fulltext.py`. Read the complete material paper or every complete relevant section required by a targeted update.
8. Build a layered digest containing every independently useful scientific facet discovered during a full reading. Validate and ingest it. For later targeted reading, inspect the current digest and use `--merge` to preserve earlier facets and revision history.
9. Compare recent evidence with influential or foundational results. Separate direct evidence, counterevidence, selection effects, adjacent work, and algorithmic recommendations.
10. Return a reader-facing synthesis with article links, calibrated evidence, version-aware full-text coverage, database-reuse counts, and a concise method note.

### Coverage Standard

- A focused review uses at least two independent query families, abstract triage, and full reading of the manageable material-paper set.
- A broad, comprehensive, or claim-level review covers terminology and synonyms, counterclaims or selection effects, seed-paper citations or references, recent results, citation-ranked results, and all manageable result pages. State the sampling rule and uncovered scope when the set is too large.
- Use `bigquery` to re-fetch complete metadata for the deduplicated evidence set.
- Refine query families dominated by false positives. `numFound` is not a relevant-paper count.
- Label each material record as published-full-text, accepted-manuscript, preprint-full-text, visual-reading, or abstract-only. Abstract-only records support only abstract-level statements.
- A database digest counts as full-text coverage only for its exact stored version and recorded facets. Report targeted verification and newly added facets separately.
- Judge sufficiency by conceptual and evidentiary coverage rather than raw result count.

### Digest Standard

- Derive facets dynamically from the article’s research questions and evidence chains. The database has no fixed domain vocabulary.
- Split facets when observables, samples, analyses, parameter regimes, result families, or inferential steps differ materially. Merge restatements of the same result.
- Capture all material dimensions encountered during a full reading, including findings outside the current query.
- Give every finding a kind, calibrated confidence, evidence locator, values with units or qualifiers when relevant, and retrieval keywords.
- Keep entities, datasets, methods, data products, and global limitations in their dedicated layers.
- A one-sentence summary, abstract paraphrase, section-title dump, or current-topic-only note does not satisfy the database standard.

## Credentials

ADS API operations resolve `ADS_API_TOKEN`, then `ADS_DEV_KEY`. If both are absent, stop the ADS operation, direct the user to [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token), ask them to set either variable in the terminal that launches the host, and retry. A direct arXiv identifier can still use `fulltext.py` without ADS metadata enrichment. Keep a session token in process memory and avoid commands that echo headers or command lines.

## Result Presentation

For literature research, include:

1. A concise answer to the question.
2. Representative records with title, first authors, year, venue, citation count, bibcode, and ADS link.
3. DOI and arXiv links when present.
4. A thematic synthesis for multi-paper work.
5. Query families, filters, sorting, pagination, and search date when completeness matters.
6. A calibrated limitation statement for sparse or negative results.
7. Full-text coverage by selected version, visual-reading page ranges, and abstract-only reasons.
8. Literature-memory counts: reused, targeted-verified, augmented, newly ingested, and version-refreshed papers.

Build ADS links as `https://ui.adsabs.harvard.edu/abs/<bibcode>` and arXiv links from `identifier` values beginning with `arXiv:`.

## Failure Routing

- Missing token: provide the token-page link and supported environment-variable names, then stop the ADS operation.
- `401`, `403`, `404`, or `429`: report the relevant authentication, permission, identifier, or rate-limit context from the CLI.
- Unexpected redirect or ADS error payload: treat the operation as failed.
- Empty or malformed search: correct unnecessary filters, field the target term, try variants, and report the exact searched forms.
- Full-text HTML `404`: let `fulltext.py` continue to the official arXiv PDF or next ranked candidate.
- `needs_visual_reading`: use the host’s native PDF vision or bounded rendering procedure in `references/fulltext.md`.
- `abstract_only`: report attempted candidates and limit claims to abstract-level evidence.
- Literature database unavailable or corrupt: preserve fetched artifacts and digest files, continue the current synthesis, and state that storage failed.
- SQLite FTS5 unavailable: use the CLI’s deterministic substring fallback.
- Stored version lacks a requested facet: perform targeted reading and merge the added evidence.
- CLI launch failure after all three Python commands: use the documented direct HTTP fallback when it supports the task and state why.
