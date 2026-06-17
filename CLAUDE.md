# NASA ADS Skill Repository

This repository packages the NASA ADS skill for Claude Code, Codex, and Gemini-compatible Markdown skill loading. The installable Claude plugin lives in `plugins/nasa-ads/`.

## Claude Plugin

- Plugin root: `plugins/nasa-ads/`
- Manifest: `plugins/nasa-ads/.claude-plugin/plugin.json`
- Marketplace: `.claude-plugin/marketplace.json`
- Shared skill reference: `plugins/nasa-ads/skills/nasa-ads/SKILL.md`
- Commands are namespaced by plugin id: `/nasa-ads:ads-search`, `/nasa-ads:ads-bibtex`, `/nasa-ads:ads-library`, `/nasa-ads:ads-metrics`, `/nasa-ads:ads-cite`

## API Token

The ADS API requires a personal token. Check `ADS_API_TOKEN` first, then `ADS_DEV_KEY`. If neither is set, point the user to the token page, tell them to set one of those environment variables, and ask them to retry or provide a token for the current session. Never hardcode or log the token.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token
