# NASA ADS Skill

Skill for interacting with the NASA Astrophysics Data System (ADS) API.

## Commands

- `/ads-search <query>` - Search for papers (natural language, author, title, bibcode, arxiv ID)
- `/ads-bibtex <bibcodes>` - Export BibTeX or other citation formats
- `/ads-library [subcommand]` - List, view, create, and manage ADS libraries
- `/ads-metrics <bibcodes>` - Get citation metrics (h-index, citation count, etc.)
- `/ads-cite [subcommand]` - Suggest missing citations, find similar papers, get full text links

## API Token

Check environment variables `ADS_API_TOKEN` or `ADS_DEV_KEY` first. If neither is set, prompt the user.

Token page: https://ui.adsabs.harvard.edu/#user/settings/token

## API Reference

The full ADS API reference is in `skills/nasa-ads/SKILL.md`, covering:

- **Search**: query syntax, fields, filters, sorting, pagination, big query
- **Export**: BibTeX, AASTeX, MNRAS, RIS, EndNote, custom formats
- **Libraries**: list, view, create, add/remove papers, set operations, permissions
- **Metrics**: h-index, g-index, i10-index, citation/read stats
- **Citation Helper**: suggest missing citations
- **Resolver**: links to full text, data archives
