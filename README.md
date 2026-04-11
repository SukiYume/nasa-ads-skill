# NASA ADS Skill

A packaged NASA ADS skill/plugin bundle for Claude Code and Codex.

This repository is intentionally documentation-first: it does not ship a standalone API client or background service. Instead, it packages prompt/skill assets that instruct the host assistant to call the [NASA Astrophysics Data System (ADS)](https://ui.adsabs.harvard.edu/) REST API from the local shell using your token.

## What It Covers

| Feature | Description |
|---------|-------------|
| Paper Search | Search by author, title, abstract, bibcode, DOI, arXiv ID, object, ORCID, or full text |
| Metadata | Return title, authors, abstract, year, journal, DOI, citation count, and identifiers |
| Citation Export | Export BibTeX, AASTeX, MNRAS, RIS, EndNote, IEEE, custom formats, and more |
| Libraries | List, view, create, and update ADS libraries |
| Metrics | h-index, g-index, i10-index, citation stats, read stats, and indicators |
| Citation Helper | Suggest related or missing citations |
| Resolver | Return ADS, publisher, arXiv, and data-archive links |

## Requirements

You need all of the following:

1. An ADS API token from [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token)
2. Outbound HTTPS access to `https://api.adsabs.harvard.edu`
3. A host environment that allows the assistant to run shell commands (`curl` or equivalent)

Supported environment variables:

- `ADS_API_TOKEN`
- `ADS_DEV_KEY`

Examples:

```bash
export ADS_API_TOKEN="your-token-here"
```

```powershell
[System.Environment]::SetEnvironmentVariable("ADS_API_TOKEN", "your-token-here", "User")
```

## Installation

### Claude Code

This repo is now structured as a Claude plugin marketplace. Add the marketplace first, then install the plugin from that marketplace.

CLI:

```bash
claude plugin marketplace add SukiYume/nasa-ads-skill
claude plugin install nasa-ads@nasa-ads-community
```

Inside Claude Code:

```text
/plugin marketplace add SukiYume/nasa-ads-skill
/plugin install nasa-ads@nasa-ads-community
```

Local validation flow:

```text
/plugin marketplace add .
/plugin install nasa-ads@nasa-ads-community
```

Claude Code IDE extensions use the same marketplace and install flow.

### Claude Commands

Claude plugin commands are namespaced by plugin id. Use:

```text
/nasa-ads:ads-search author:Einstein gravitational waves
/nasa-ads:ads-bibtex 2016PhRvL.116f1102A
/nasa-ads:ads-library list
/nasa-ads:ads-metrics 2016PhRvL.116f1102A
/nasa-ads:ads-cite similar 2016PhRvL.116f1102A
```

The `nasa-ads` skill can also activate from plain-language requests about papers, citations, ADS, BibTeX, arXiv, libraries, or citation metrics.

### Codex Plugin Install

Codex plugin discovery is local: install the plugin through a repo or personal marketplace.

Repo-local install in another project:

1. Copy `plugins/nasa-ads` into `<repo>/plugins/nasa-ads`
2. Add this entry to `<repo>/.agents/plugins/marketplace.json`

```json
{
  "name": "local-repo",
  "plugins": [
    {
      "name": "nasa-ads",
      "source": {
        "source": "local",
        "path": "./plugins/nasa-ads"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Research"
    }
  ]
}
```

Personal install across repos:

1. Copy `plugins/nasa-ads` to `~/plugins/nasa-ads`
2. Add the same plugin entry to `~/.agents/plugins/marketplace.json`
3. Restart Codex

This repo already includes a working repo marketplace at `.agents/plugins/marketplace.json` for local testing.

### Codex Skill-Only Install

If you only want the instruction bundle and do not need Codex plugin metadata, copy the skill directory, not a flat markdown file:

```bash
mkdir -p .agents/skills/nasa-ads
cp plugins/nasa-ads/skills/nasa-ads/SKILL.md .agents/skills/nasa-ads/SKILL.md
```

### Gemini

Reference the packaged skill path:

```text
@./plugins/nasa-ads/skills/nasa-ads/SKILL.md
```

Or copy that directory into your Gemini skill location.

## Usage

Plain-language prompts:

- "Search ADS for recent papers on exoplanet atmospheres"
- "Get the BibTeX for this paper: 2016PhRvL.116f1102A"
- "Show me my ADS libraries"
- "What are the citation metrics for these bibcodes?"
- "Find papers similar to 2016PhRvL.116f1102A"

Claude command examples:

```text
/nasa-ads:ads-search dark matter year:2020-2024
/nasa-ads:ads-bibtex 2016PhRvL.116f1102A 2017ApJ...848L..12A --format aastex
/nasa-ads:ads-library create "My Reading List"
/nasa-ads:ads-cite links 2016PhRvL.116f1102A
```

## Repository Layout

```text
nasa-ads-skill/
├── .claude-plugin/
│   └── marketplace.json
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── plugins/
│   └── nasa-ads/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── .codex-plugin/
│       │   └── plugin.json
│       ├── commands/
│       │   ├── ads-search.md
│       │   ├── ads-bibtex.md
│       │   ├── ads-library.md
│       │   ├── ads-metrics.md
│       │   └── ads-cite.md
│       └── skills/
│           └── nasa-ads/
│               └── SKILL.md
├── AGENTS.md
├── CLAUDE.md
├── GEMINI.md
└── README.md
```

The single source of truth for the ADS reference is `plugins/nasa-ads/skills/nasa-ads/SKILL.md`.

## API Endpoints Covered

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/search/query` | GET | Search for papers |
| `/search/bigquery` | POST | Batch bibcode lookup |
| `/export/<format>` | GET/POST | Export citations |
| `/biblib/libraries` | GET/POST | List or create libraries |
| `/biblib/libraries/<id>` | GET | View library contents |
| `/biblib/documents/<id>` | POST/PUT/DELETE | Add, remove, update, or delete library contents |
| `/biblib/query/<id>` | GET/POST | Add or remove papers by query |
| `/biblib/libraries/operations/<id>` | POST | Library set operations |
| `/biblib/permissions/<id>` | GET/POST | Library permissions |
| `/metrics` | POST | Citation metrics and indicators |
| `/citation_helper` | POST | Suggested citations |
| `/resolver/<bibcode>` | GET | Full-text and data links |

## Notes

- The packaged commands assume the assistant can run shell commands.
- The bundled examples now fall back from `ADS_API_TOKEN` to `ADS_DEV_KEY`.
- No token is stored in this repository.
- If you add or change ADS workflows, update both the skill file and Claude command files inside `plugins/nasa-ads`.

## License

MIT
