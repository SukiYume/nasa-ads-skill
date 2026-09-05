# NASA ADS Skill Repository

Repository for a packaged NASA ADS skill/plugin that targets Claude Code, Codex, and Gemini-compatible Markdown skill loading.

## Packaging Layout

- Claude marketplace: `.claude-plugin/marketplace.json`
- Codex repo marketplace: `.agents/plugins/marketplace.json`
- Installable plugin root: `plugins/nasa-ads/`
- Codex manifest: `plugins/nasa-ads/.codex-plugin/plugin.json`
- Claude manifest: `plugins/nasa-ads/.claude-plugin/plugin.json`
- Packaged license: `plugins/nasa-ads/LICENSE`
- Skill reference: `plugins/nasa-ads/skills/nasa-ads/SKILL.md`
- Bundled API CLI: `plugins/nasa-ads/skills/nasa-ads/scripts/ads_api.py`
- Bundled full-text CLI: `plugins/nasa-ads/skills/nasa-ads/scripts/fulltext.py`
- Bundled literature-memory CLI: `plugins/nasa-ads/skills/nasa-ads/scripts/literature_db.py`
- Web command launcher and user setup: `plugins/nasa-ads/skills/nasa-ads/scripts/adslib.py`
- Catalog and Web modules: `plugins/nasa-ads/skills/nasa-ads/scripts/library_catalog.py` and `library_web.py`
- Local Web assets: `plugins/nasa-ads/skills/nasa-ads/assets/library/`
- Conditional references: `plugins/nasa-ads/skills/nasa-ads/references/`
- Gemini include file: `GEMINI.md`

## Claude Commands

Claude plugin commands are namespaced by plugin id:

- `/nasa-ads:ads-search <query>`
- `/nasa-ads:ads-bibtex <bibcodes>`
- `/nasa-ads:ads-library [subcommand]`
- `/nasa-ads:ads-metrics <bibcodes>`
- `/nasa-ads:ads-cite [subcommand]`
- `/nasa-ads:ads-fulltext <bibcodes, DOIs, or arXiv IDs>`
- `/nasa-ads:ads-memory <lookup, search, show, stats, or paper topics>`

## API Token

For online ADS operations, check `ADS_API_TOKEN` first, then `ADS_DEV_KEY`. If neither is set, point the user to the token page and tell them to set one of those environment variables for the next request. Local library browsing, stored reading, organization, and cached citation export work without an ADS token. Never hardcode or log the token.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token

Use the bundled standard-library ADS CLI for search, big query, citation export, metrics, citation-helper, and resolver calls. Use the bundled full-text CLI for deterministic lawful retrieval and preparation. Use the bundled literature-memory CLI for version-aware storage, lookup, structured digests, and local search. Keep article reading, visual interpretation, digest authorship, query design, evidence assessment, result synthesis, and all destructive library confirmations in Markdown.

## Documentation Contract

- Keep the shared reading scope and silent-persistence contract in [SKILL.md](plugins/nasa-ads/skills/nasa-ads/SKILL.md#core-invariants). References and command entry points use that contract and document their own operations. Examples illustrate syntax; task-specific choices follow the user's research scope.
- Include one-time `adslib` command registration in installation instructions and verify it against the installed skill. Preserve existing PATH entries and foreign commands.
- Write README installation paths for a reader starting on a new computer with no repository-specific knowledge.
- Keep `README.md` and `README.zh-CN.md` structurally aligned.
- Keep the README focused on installation choices, first use, Web access, and troubleshooting. Put detailed platform commands in `docs/installation.md` and library operations in `docs/library.md`; maintain their `.zh-CN.md` counterparts with matching structure.
- Keep `SKILL.md` task-oriented: route requests first, load references as needed, and scope completion checks to the selected task.
- Keep the copyable one-sentence agent-install prompt directly after the overview; require CLI-file, token-safety, version, and smoke-test checks.
- Use the current Codex standalone-skill location, `~/.agents/skills/<skill-name>`.
- Give Windows PowerShell and macOS/Linux/WSL commands where filesystem syntax differs.
- Explain that Python 3.10 or newer is recommended for the bundled CLI and document the direct HTTP fallback.
- Include an installation check, token-presence check, public API smoke test, and troubleshooting path.
- Keep prose direct and avoid contrastive turn-away constructions.

## Release Sync

When behavior or installation changes, update these surfaces together:

- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`
- `plugins/nasa-ads/.claude-plugin/plugin.json`
- `plugins/nasa-ads/.codex-plugin/plugin.json`
- `plugins/nasa-ads/LICENSE`
- `plugins/nasa-ads/skills/nasa-ads/SKILL.md`
- `plugins/nasa-ads/skills/nasa-ads/scripts/ads_api.py`
- `plugins/nasa-ads/skills/nasa-ads/scripts/fulltext.py`
- `plugins/nasa-ads/skills/nasa-ads/scripts/literature_db.py`
- affected files under `plugins/nasa-ads/skills/nasa-ads/references/`
- `plugins/nasa-ads/skills/nasa-ads/agents/openai.yaml`
- affected files under `plugins/nasa-ads/commands/`
- both README files

Keep the plugin version identical across the Claude marketplace metadata and both plugin manifests.

## Validation

Before committing:

1. Run `claude plugin validate . --strict`.
2. Parse every JSON manifest.
3. Run the Codex skill validator from `skill-creator` with UTF-8 mode on Windows.
4. Run `python -m unittest discover -s tests -v` and compile all bundled Python modules.
5. Check README and guide relative links, cross-file Markdown anchors, and bilingual heading structure.
6. Test the documented Codex and Claude marketplace installs with disposable entries; record the pre-test state and remove only the exact test entries afterward.
7. Run read-only ADS smoke tests for search, big query, export, metrics, citation helper, and resolver when a token is available.
8. Run `git diff --check` and inspect the complete diff.
