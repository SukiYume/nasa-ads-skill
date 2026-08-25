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
- Conditional references: `plugins/nasa-ads/skills/nasa-ads/references/`
- Commands are namespaced by plugin id: `/nasa-ads:ads-search`, `/nasa-ads:ads-bibtex`, `/nasa-ads:ads-library`, `/nasa-ads:ads-metrics`, `/nasa-ads:ads-cite`, `/nasa-ads:ads-fulltext`, `/nasa-ads:ads-memory`

## API Token

The ADS API requires a personal token. Check `ADS_API_TOKEN` first, then `ADS_DEV_KEY`. If neither is set, point the user to the token page, tell them to set one of those environment variables, and ask them to retry or provide a token for the current session. Never hardcode or log the token.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token

Use the bundled Python CLIs for stable read-only API calls, deterministic lawful full-text retrieval, and version-aware local literature memory. Keep article reading, visual interpretation, rich digest authorship, research judgment, and destructive library safety confirmations in Markdown.

## Documentation and Release Checks

- Keep the English and Chinese READMEs aligned and usable from a fresh computer.
- Keep the marketplace metadata, Claude/Codex manifests, shared skill, OpenAI skill metadata, and affected commands in sync.
- Keep the release version identical in `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, and `.codex-plugin/plugin.json`.
- Preserve direct prose and avoid contrastive turn-away phrasing.
- Run `claude plugin validate . --strict`, the Codex skill validator, CLI unit tests and compilation, JSON parsing, README link checks, disposable install tests, read-only ADS smoke tests, and `git diff --check` before committing.
