# NASA ADS Skill

This plugin provides skills and commands for interacting with the NASA Astrophysics Data System (ADS) API.

## Available Commands

- `/ads-search <query>` - Search for papers (supports natural language, author, title, bibcode, arxiv ID)
- `/ads-bibtex <bibcodes>` - Export BibTeX or other citation formats
- `/ads-library [subcommand]` - List, view, create, and manage ADS libraries
- `/ads-metrics <bibcodes>` - Get citation metrics (h-index, citation count, etc.)

## API Token

The ADS API requires a personal token. Check environment variables `ADS_API_TOKEN` or `ADS_DEV_KEY` first. If neither is set, prompt the user.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token

## Skill Reference

See skills/nasa-ads/SKILL.md for full ADS API reference including search syntax, export formats, library management, metrics, citation helper, and resolver endpoints.
