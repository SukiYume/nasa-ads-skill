# NASA ADS Skill

A skill for AI coding assistants to search the [NASA Astrophysics Data System (ADS)](https://ui.adsabs.harvard.edu/) — the primary digital library for astronomy and astrophysics research.

Search papers, retrieve metadata, export BibTeX citations, manage libraries, get citation metrics, and find related papers — all from your coding environment.

## Features

| Feature | Description |
|---------|-------------|
| Paper Search | By author, title, abstract, keyword, year, object, ORCID, full text |
| Metadata | Title, authors, abstract, year, journal, DOI, citation count, read count |
| arXiv Links | Automatically extracted from ADS identifiers |
| Citation Export | BibTeX, AASTeX, MNRAS, Icarus, EndNote, RIS, IEEE, custom, and more |
| Libraries | List, view, create, add/remove papers, set operations (union/intersection/difference) |
| Metrics | h-index, g-index, i10-index, citation stats, read stats, histograms |
| Citation Helper | Suggest missing citations via "friends of friends" analysis |
| Resolver | Links to full text (PDF/HTML), data archives (MAST, Chandra, JWST, etc.) |
| Advanced Queries | `citations()`, `references()`, `trending()`, `similar()`, `useful()` operators |
| Batch Lookup | Look up up to 2000 bibcodes at once via Big Query |

## Setup

You need an ADS API token:

1. Create an account at [ADS](https://ui.adsabs.harvard.edu/)
2. Go to [API Token Settings](https://ui.adsabs.harvard.edu/#user/settings/token)
3. Click "Generate a new key"
4. Set as environment variable:

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
export ADS_API_TOKEN="your-token-here"
```

On Windows (PowerShell):
```powershell
[System.Environment]::SetEnvironmentVariable("ADS_API_TOKEN", "your-token-here", "User")
```

## Installation

### Claude Code (CLI / Desktop / Web)

Install directly from GitHub:

```bash
# Via the Claude Code CLI
claude plugin install --from https://github.com/SukiYume/nasa-ads-skill
```

Or from within a Claude Code session:

```
/plugin install --from https://github.com/SukiYume/nasa-ads-skill
```

After installation, the skill activates automatically when you mention papers, literature, BibTeX, arXiv, ADS, etc. You can also use the slash commands: `/ads-search`, `/ads-bibtex`, `/ads-library`, `/ads-metrics`.

### Claude Code (VS Code / JetBrains Extension)

The Claude Code IDE extensions share the same plugin system as the CLI. Install via the built-in terminal:

```bash
claude plugin install --from https://github.com/SukiYume/nasa-ads-skill
```

Alternatively, copy the plugin manually:

```bash
# Clone into the plugins cache directory
git clone https://github.com/SukiYume/nasa-ads-skill.git \
  ~/.claude/plugins/cache/nasa-ads/1.1.0
```

Then add to `~/.claude/plugins/installed_plugins.json` or reinstall via the CLI.

### OpenAI Codex CLI

Codex supports `AGENTS.md` for configuration. Clone this repo into your project and Codex will pick up the `AGENTS.md` file (which points to `CLAUDE.md`):

```bash
# Option 1: Clone as a subdirectory in your project
git clone https://github.com/SukiYume/nasa-ads-skill.git .claude-plugins/nasa-ads

# Option 2: Copy the skill file into your project's agents config
mkdir -p .agents/skills
cp nasa-ads-skill/skills/nasa-ads/SKILL.md .agents/skills/nasa-ads.md
```

You can also copy the contents of `CLAUDE.md` into your project's `AGENTS.md` to make the commands available.

### Gemini CLI

This project includes a `GEMINI.md` that auto-loads the skill. Clone into your project:

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git .plugins/nasa-ads
```

Or copy manually:

```bash
# Option 1: Copy the skill file
mkdir -p .gemini/skills
cp nasa-ads-skill/skills/nasa-ads/SKILL.md .gemini/skills/nasa-ads.md

# Option 2: Reference in your GEMINI.md
echo '@./nasa-ads-skill/GEMINI.md' >> GEMINI.md
```

### Generic / Manual Installation

For any AI coding assistant that supports markdown-based skills or system prompts:

1. Clone this repository
2. Copy `skills/nasa-ads/SKILL.md` into your assistant's skill/prompt directory
3. The skill contains the complete ADS API reference — no external dependencies needed

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git
```

The key file is `skills/nasa-ads/SKILL.md` — it is self-contained and works as a standalone reference for any LLM-based coding assistant.

## Usage

### Automatic Skill Activation

The `nasa-ads` skill activates automatically when you mention:
- Searching for papers, literature, or publications
- BibTeX, citations, references
- arXiv, ADS, astrophysics
- Author names + paper topics
- h-index, citation metrics
- ADS libraries

### Slash Commands

```bash
# Search for papers
/ads-search author:Einstein gravitational waves
/ads-search dark matter year:2020-2024
/ads-search arxiv:1602.03837

# Export citations
/ads-bibtex 2016PhRvL.116f1102A
/ads-bibtex 2016PhRvL.116f1102A 2017ApJ...848L..12A --format aastex

# Manage libraries
/ads-library list
/ads-library view <library_id>
/ads-library create "My Reading List"
/ads-library add <library_id> 2016PhRvL.116f1102A

# Get metrics
/ads-metrics 2016PhRvL.116f1102A
```

### Natural Language (via Skill)

Just ask in plain language:

- "Search ADS for recent papers on exoplanet atmospheres"
- "Get the BibTeX for this paper: 2016PhRvL.116f1102A"
- "Show me my ADS libraries"
- "What's the h-index for these papers?"
- "Find papers similar to 2016PhRvL.116f1102A"
- "What papers cite 2017ApJ...848L..12A?"

## Plugin Structure

```
nasa-ads-skill/
├── .claude-plugin/
│   └── plugin.json           # Plugin metadata (name, version, homepage)
├── skills/
│   └── nasa-ads/
│       └── SKILL.md          # Auto-triggered skill (complete API reference)
├── commands/
│   ├── ads-search.md         # /ads-search slash command
│   ├── ads-bibtex.md         # /ads-bibtex slash command
│   ├── ads-library.md        # /ads-library slash command
│   └── ads-metrics.md        # /ads-metrics slash command
├── .gitignore                # Git ignore rules
├── CLAUDE.md                 # Project instructions (Claude Code)
├── AGENTS.md                 # Agent instructions (Codex)
├── GEMINI.md                 # Skill loader (Gemini CLI)
├── LICENSE
└── README.md
```

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/search/query` | GET | Search for papers |
| `/search/bigquery` | POST | Batch bibcode lookup (up to 2000) |
| `/export/<format>` | GET/POST | Export citations (bibtex, aastex, etc.) |
| `/biblib/libraries` | GET/POST | List/create libraries |
| `/biblib/libraries/<id>` | GET | View library contents |
| `/biblib/documents/<id>` | POST/PUT/DELETE | Add/remove papers, update/delete library |
| `/biblib/query/<id>` | GET/POST | Add/remove papers by search query |
| `/biblib/libraries/operations/<id>` | POST | Set operations (union, intersection, etc.) |
| `/biblib/permissions/<id>` | GET/POST | View/edit library permissions |
| `/metrics` | POST | Citation metrics and indicators |
| `/citation_helper` | POST | Suggest missing citations |
| `/resolver/<bibcode>` | GET | Links to full text and data |

Rate limits: ~5000 requests/day per search endpoint, ~100/day for big query. Check `X-RateLimit-Remaining` header.

## Contributing

Issues and PRs welcome. If you add new ADS API features, please update both `skills/nasa-ads/SKILL.md` and the relevant command file.

## License

MIT

## Acknowledgments

- [NASA ADS](https://ui.adsabs.harvard.edu/) for the API
- [ADS Dev API Documentation](https://github.com/adsabs/adsabs-dev-api) for the reference material
- [ads Python client](https://ads.readthedocs.io/) by Andy Casey
