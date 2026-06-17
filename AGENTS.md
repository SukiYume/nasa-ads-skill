# NASA ADS Skill Repository

Repository for a packaged NASA ADS skill/plugin that targets Claude Code, Codex, and Gemini-compatible Markdown skill loading.

## Packaging Layout

- Claude marketplace: `.claude-plugin/marketplace.json`
- Codex repo marketplace: `.agents/plugins/marketplace.json`
- Installable plugin root: `plugins/nasa-ads/`
- Codex manifest: `plugins/nasa-ads/.codex-plugin/plugin.json`
- Claude manifest: `plugins/nasa-ads/.claude-plugin/plugin.json`
- Skill reference: `plugins/nasa-ads/skills/nasa-ads/SKILL.md`
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
