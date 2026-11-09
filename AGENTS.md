# NASA ADS Skill Repository

This repository packages the NASA ADS skill, backed by SciX (the successor to NASA ADS), as a Claude Code plugin, a Codex plugin, a standalone skill, and a Gemini-compatible Markdown include.

## Layout

```text
.claude-plugin/marketplace.json     Claude marketplace (release version lives here)
.agents/plugins/marketplace.json    Codex repository marketplace
GEMINI.md                           Gemini CLI include of SKILL.md
README.md, README.zh-CN.md          The complete user documentation
.github/images/                     README images
tests/                              Unit and packaging tests
plugins/nasa-ads/
  .claude-plugin/plugin.json        Claude manifest
  .codex-plugin/plugin.json         Codex manifest
  LICENSE                           Packaged license (matches the root LICENSE)
  commands/                         Claude slash commands, thin entry points into SKILL.md
  skills/nasa-ads/
    SKILL.md                        Routing, Core Invariants, research workflow, failure routing
    agents/openai.yaml              Codex skill metadata
    references/                     Task references loaded on demand
    scripts/                        ads_api.py, fulltext.py, literature_db.py, library_catalog.py,
                                    library_migrate.py, library_web.py, adslib.py (standard-library Python)
    assets/                         Local Web reader (index.html, style.css, app.js)
```

Reference responsibilities:

| Reference | Scope |
|---|---|
| `research-writing.md` | Reviews and manuscript evidence, citing specific results, claim-to-evidence handoff |
| `ads-cli.md` | SciX API CLI: search with highlights, facets, and statistics, big query, export, metrics, citation helper, resolver, reference strings, objects, journals, networks, word clouds |
| `fulltext.md` | Lawful retrieval, import of user-supplied copies, manifest states, prepared text, reading procedure |
| `digest-schema.md` | What a digest retains, layers and vocabularies, values, validation warnings, ingest, merge |
| `literature-memory.md` | Capture, summaries, lookup, stored passages, search, `findings`, `parameters`, classification, citations, Web library |
| `library-maintenance.md` | Audit, backup, restore, identity merges, metadata refresh |
| `libraries.md` | Remote SciX account libraries |
| `http-fallback.md` | Direct HTTP rules and clients |

The skill uses the public bibliographic SciX services and SciX account libraries; other account services, such as myADS notifications, reading-history recommendations, and ORCID, stay outside it.

Claude commands are namespaced by plugin id: `/nasa-ads:ads-search`, `/nasa-ads:ads-fulltext`, `/nasa-ads:ads-memory`, `/nasa-ads:ads-bibtex`, `/nasa-ads:ads-cite`, `/nasa-ads:ads-metrics`, `/nasa-ads:ads-library`.

## API Token

Online SciX operations read a personal token from `ADS_API_TOKEN`. When it is unset, point the user to https://scixplorer.org/user/settings/token and ask them to set it. Local browsing, stored reading, organization, and cached citation export work without it. Never hardcode, print, or log the token. API base: https://api.scixplorer.org/v1.

Bundled Python CLIs handle stable read-only API calls, deterministic lawful full-text retrieval, and version-aware local storage. Article reading, visual interpretation, digest authorship, research judgment, and destructive-action confirmations stay in Markdown instructions.

## Documentation Rules

- `SKILL.md` owns the shared contract: task routing, Core Invariants, Reading Scope, research workflow, handoff, and failure routing. References and commands link to it and document only their own operations; each fact lives in one place.
- Commands stay thin: parse arguments, name the route, and point to the reference section.
- Label example parameters as examples; task choices follow the user's research scope.
- Audience: `README.md` is written for human readers and `SKILL.md`, references, and commands for agents. The README addresses the reader, describes what they can ask the agent and run themselves, and leaves agent execution rules to the skill; the skill states operational rules and leaves installation and user guidance to the README.
- `README.md` is the only user document. It follows the reader's path: overview, installation, token, verification, first use, what the library keeps, reuse and citation export, Web, library management, updates, and troubleshooting. `README.zh-CN.md` keeps the same heading structure. README images live in `.github/images/`; the repository has no separate user-guide directory.
- Keep the copyable agent-install prompt directly after the README overview, listing every packaged skill file and the version, token-safety, and smoke-test checks.
- Use the Codex standalone location `~/.agents/skills/<skill-name>`. Give Windows PowerShell and macOS/Linux/WSL commands where syntax differs. State that Python 3.10 or newer runs the bundled CLIs and document the direct HTTP fallback.
- Document the current release only. Version history, upgrade paths from old releases, and migration notes stay out of the README and the skill.
- Write direct prose and avoid contrastive turn-away phrasing.

## Release Sync

When behavior or installation changes, update together: both marketplaces, both plugin manifests, `agents/openai.yaml`, `SKILL.md`, affected references and commands, and both READMEs. Keep the release version identical in `.claude-plugin/marketplace.json`, both plugin manifests, the `VERSION` constant of `ads_api.py`, `fulltext.py`, and `literature_db.py`, and the README badges and version checks. Runtime code reads only the current database and digest schemas; a schema change extends `library_migrate.py` so that `literature_db.py migrate` converts a library from the previous release.

## Validation

Before committing:

1. `claude plugin validate . --strict`
2. Codex skill validator from `skill-creator` (`quick_validate.py`), with `PYTHONUTF8=1` on Windows.
3. `python -m unittest discover -s tests` and compile every bundled Python module; `node --check` the Web script.
4. Parse every JSON manifest; check README links, Markdown anchors, and bilingual heading structure (covered by `tests/test_package.py`).
5. Test the documented Codex and Claude marketplace installs with disposable entries; record the prior state and remove only the test entries.
6. Run read-only SciX smoke tests for search (with highlights, facets, and statistics), big query, export (including `csl` and `custom`), metrics, citation helper, resolver, reference, objects, journals, network, and wordcloud when a token is available.
7. `git diff --check`, then review the complete diff.
