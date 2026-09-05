# Personal library upgrade and Web refinement

Completed on 2026-09-05 UTC. Implementation version: 1.13.1. Database schema: 3. Complete article digest schema: 2. This phase follows the [project review](review.md). The subsequent [Chrome Web audit](web-audit.md) records version 1.13.2, browser testing and fixes, and the latest installation checks. The counts and runtime version below describe this migration phase.

## Actual library and data preservation

The active personal library at `%LOCALAPPDATA%/nasa-ads/literature` contains 136 papers and 139 exact article versions. The three-paper library under `.validation/library` is an isolated validation fixture. The running Web service reads the active personal library.

Migration created a consistent database and object backup at `%LOCALAPPDATA%/nasa-ads/backups/literature-20260905T073112` before changing schema 2 to schema 3. Classification and enrichment were validated on a complete copy, then applied to the active library through the bundled storage operations.

| Measure | Before curation | After curation |
|---|---:|---:|
| Papers | 136 | 136 |
| Exact article versions | 139 | 139 |
| Complete reading digests | 139 | 139 |
| Scientific facets | 839 | 839 |
| Traceable findings | 2203 | 2203 |
| Hierarchical collection nodes | 0 | 44 |
| Papers with topic classification | 0 | 136 |
| Official cached ADS citations | 0 | 136 |

The hierarchy has seven roots, three intermediate nodes, and 34 leaves. Its 316 paper-to-topic memberships support cross-topic reuse. The catalog also contains 918 keyword/tag memberships and 277 manuscript-role memberships. Counts for different branches and roles can overlap.

Root subjects are fast radio bursts, methods and software, the Milky Way, pulsars and magnetars, other astronomy subjects, observing facilities, and research practice. Topic descriptions explain scope and important interpretation limits. Classification uses the existing paper overviews, keywords, methods, and scientific facets.

All 136 papers received metadata verified against ADS; 13 previously unresolved records received their ADS bibcodes. Available author lists and publication fields were reconciled. All 136 official BibTeX entries were cached with their current identities and exported successfully with both ADS token variables removed from the export process.

Three historical digest fields were repaired: one scan's reading coverage now uses its verified seven PDF page numbers, and two supplemental-note overviews now describe their complete papers using their existing scientific facets. The scan's journal pagination remains in its reading notes. Original article hashes, version counts, facet counts, and finding counts were preserved. The remaining 136 digests retained their previous content. Retraction and source-identity correction labels reflect information already present in the relevant stored digests. Existing article knowledge was reused; this maintenance pass adds no claim of newly rereading all 139 full articles.

The final integrity audit verified object hashes, database integrity, relationships, search coverage, and digest validity. It reported `healthy`, with zero errors and zero warnings. The completion check reported zero pending summaries and zero uncategorized papers.

## Future classification and reuse

The skill requires each returned or newly read paper to have at least one content-based topic. Agents inspect and reuse the existing directory paths and language, author scientific summaries, and record applicable manuscript roles. Summary and full-digest keywords automatically become retrieval tags. Existing classifications and notes are preserved.

The `check --run-id` command now checks summary completion and topic classification together. It returns exit code 1 while either remains incomplete. It reports the papers that need classification. Search and full-text routes both require this check before reporting persistence complete. The agent chooses the scientific topics; the storage commands persist and verify those choices.

Two maintenance operations support existing libraries: `organize` applies a reviewed annotation batch atomically, and `import-citations` caches an unedited ADS BibTeX export after checking every entry against the current paper identity. Invalid batches preserve prior data.

## Web experience

The interface uses independent navigation, literature-list, and article-reading panes. It shows paper summaries and topic context directly in the list, offers collapsible topic hierarchies ordered by root size, and supports combined topic, role, tag, evidence-level and year filters. Sorting operates on the full filtered result set before pagination.

The reader separates the overview, scientific facets, citations, and complete versions. It provides focused reading, concise author display, expandable source abstracts, linked topics and keywords, and visible citation provenance. The toolbar supports selecting a page, clearing selections, exporting selected references, and exporting the entire filtered result set. A library-information dialog shows the actual data directory and counts.

Narrow screens use a navigation drawer and a separate reader with a return control. Hidden navigation and covered list content are excluded from keyboard navigation through their visibility state. Keyboard search, Escape, reduced-motion preferences, and explicit empty states are supported. The page uses bundled assets and reads the local database through its loopback service.

## Installation and validation

- The Codex standalone skill in `~/.agents/skills/nasa-ads` and the Claude standalone skill in `~/.claude/skills/nasa-ads` were backed up and updated. All 17 packaged skill files matched the repository in each installation. All three entrypoints reported 1.13.1 and read the migrated personal library successfully. The backup is under `%LOCALAPPDATA%/nasa-ads/backups/skills-before-1.13.1-20260905T074303`.
- A live ADS search through the installed CLI captured one real paper into an isolated library. The first check reported one pending summary and one missing classification, with exit code 1. An authored abstract summary with topics, keywords and roles completed both requirements. Repeating capture reused the existing summary; a keyword was independently searchable as a tag.
- The complete unit suite passed 165 tests. Ruff checks, Python compilation, JavaScript syntax checks, Claude strict marketplace validation, and the Codex skill validator passed. Package tests verify manifests, release versions, resources, bilingual README structure, links and Markdown fences.
- Browser checks covered the actual 136-paper library, its source-path dialog, topic navigation, combined topic/role filtering, bulk selection, official citation display, focused reading, and a 390-pixel viewport. Fast-radio-burst plus methods filtering returned 18 papers, and page selection enabled export for all 18. The narrow layout had no horizontal page overflow, and all temporary viewport overrides were reset.
- Validation reports, enrichment sources, classifications, backups of installation state, and the 136-entry bibliography remain under `.validation/` or the local backup directory. The active Web service uses the installed 1.13.1 CLI and the platform-default personal library.

Changes remain in the project working tree. This phase updated the local standalone installations. Repository publication remains a separate action.
