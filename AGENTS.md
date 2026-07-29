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
- Conditional references: `plugins/nasa-ads/skills/nasa-ads/references/`
- Gemini include file: `GEMINI.md`

## Claude Commands

Claude plugin commands are namespaced by plugin id:

- `/nasa-ads:ads-search <query>`
- `/nasa-ads:ads-bibtex <bibcodes>`
- `/nasa-ads:ads-library [subcommand]`
- `/nasa-ads:ads-metrics <bibcodes>`
- `/nasa-ads:ads-cite [subcommand]`

## API Token

Check environment variables `ADS_API_TOKEN` or `ADS_DEV_KEY` first. If neither is set, point the user to the token page, tell them to set one of those environment variables, and ask them to retry or provide a token for the current session. Never hardcode or log the token.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token

Use the bundled standard-library Python CLI for search, big query, citation export, metrics, citation-helper, and resolver calls. Keep query design, evidence assessment, result synthesis, and all library mutation confirmations in Markdown.

## Documentation Contract

- Write README installation paths for a reader starting on a new computer with no repository-specific knowledge.
- Keep `README.md` and `README.zh-CN.md` structurally aligned.
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
4. Run `python -m unittest discover -s tests -v` and compile the bundled CLI.
5. Check README relative links and Markdown anchors.
6. Test the documented Codex and Claude marketplace installs with disposable entries; record the pre-test state and remove only the exact test entries afterward.
7. Run read-only ADS smoke tests for search, big query, export, metrics, citation helper, and resolver when a token is available.
8. Run `git diff --check` and inspect the complete diff.
