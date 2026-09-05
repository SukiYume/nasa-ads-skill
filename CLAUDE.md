# NASA ADS Skill Repository

This repository packages the NASA ADS skill for Claude Code, Codex, and Gemini-compatible Markdown skill loading. The installable Claude plugin lives in `plugins/nasa-ads/`.

## Claude Plugin

- Plugin root: `plugins/nasa-ads/`
- Manifest: `plugins/nasa-ads/.claude-plugin/plugin.json`
- Marketplace: `.claude-plugin/marketplace.json`
- Shared skill reference: `plugins/nasa-ads/skills/nasa-ads/SKILL.md`
- Bundled API CLI: `plugins/nasa-ads/skills/nasa-ads/scripts/ads_api.py`
- Bundled full-text CLI: `plugins/nasa-ads/skills/nasa-ads/scripts/fulltext.py`
- Bundled literature-memory CLI: `plugins/nasa-ads/skills/nasa-ads/scripts/literature_db.py`
- Web command launcher and user setup: `plugins/nasa-ads/skills/nasa-ads/scripts/adslib.py`
- Catalog and Web modules: `plugins/nasa-ads/skills/nasa-ads/scripts/library_catalog.py` and `library_web.py`
- Local Web assets: `plugins/nasa-ads/skills/nasa-ads/assets/library/`
- Conditional references: `plugins/nasa-ads/skills/nasa-ads/references/`
- Commands are namespaced by plugin id: `/nasa-ads:ads-search`, `/nasa-ads:ads-bibtex`, `/nasa-ads:ads-library`, `/nasa-ads:ads-metrics`, `/nasa-ads:ads-cite`, `/nasa-ads:ads-fulltext`, `/nasa-ads:ads-memory`

## API Token

Online ADS operations require a personal token. Check `ADS_API_TOKEN` first, then `ADS_DEV_KEY`. If neither is set, point the user to the token page and tell them to set one of those environment variables for the next request. Local library browsing, stored reading, organization, and cached citation export work without an ADS token. Never hardcode or log the token.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token

Use the bundled Python CLIs for stable read-only API calls, deterministic lawful full-text retrieval, and version-aware local literature memory. Keep article reading, visual interpretation, rich digest authorship, research judgment, and destructive library safety confirmations in Markdown.

## Documentation and Release Checks

- Maintain the shared reading scope and silent-persistence contract in [SKILL.md](plugins/nasa-ads/skills/nasa-ads/SKILL.md#core-invariants), and route command entry points through it. Keep task-specific procedures in their references and label example parameters as examples.
- Installation includes registering `adslib` from the installed skill, preserving existing commands and PATH entries.
- Keep the English and Chinese READMEs aligned and usable from a fresh computer.
- Use the README for reader entry points, `docs/installation.md` for detailed setup, and `docs/library.md` for Web and library operations; maintain the matching `.zh-CN.md` guides.
- Route agent tasks at the start of `SKILL.md`, load references as needed, and apply task-specific completion checks.
- Keep the marketplace metadata, Claude/Codex manifests, shared skill, OpenAI skill metadata, and affected commands in sync.
- Keep the release version identical in `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, and `.codex-plugin/plugin.json`.
- Preserve direct prose and avoid contrastive turn-away phrasing.
- Run `claude plugin validate . --strict`, the Codex skill validator, CLI unit tests and compilation, JSON parsing, README link checks, disposable install tests, read-only ADS smoke tests, and `git diff --check` before committing.
