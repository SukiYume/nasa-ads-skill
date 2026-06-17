# NASA ADS Skill

[中文说明](./README.zh-CN.md)

A packaged NASA ADS skill/plugin bundle for Claude Code, Codex, Gemini, and other Markdown-skill hosts.

This documentation-first repository packages skill and command assets that instruct the host assistant to call the [NASA Astrophysics Data System (ADS)](https://ui.adsabs.harvard.edu/) REST API from the local shell using your token.

Conceptually, this repo is a skill/plugin wrapper around the public [adsabs-dev-api](https://github.com/adsabs/adsabs-dev-api): it repackages the ADS API surface from that project into assistant-friendly skills, slash commands, and plugin manifests for Claude Code, Codex, Gemini, and similar tools.

## What It Covers

| Feature | Description |
|---------|-------------|
| Paper Search | Search by author, title, abstract, bibcode, DOI, arXiv ID, object, ORCID, or full text |
| Metadata | Return title, authors, abstract, year, journal, DOI, citation count, and identifiers |
| Citation Export | Export BibTeX, AASTeX, MNRAS, RIS, EndNote, IEEE, and more |
| Libraries | List, view, create, update, share, combine, and delete ADS libraries |
| Metrics | h-index, g-index, i10-index, citation stats, read stats, and indicators |
| Citation Helper | Suggest related or missing citations |
| Resolver | Return ADS, publisher, arXiv, and data-archive links |

## Scope

This package is intentionally scoped to practical literature research and citation workflows. It covers standard citation export through `/export/<format>` for formats such as BibTeX, AASTeX, MNRAS, RIS, EndNote, and IEEE. It does not try to wrap every ADS API endpoint; if you need less common endpoints such as metrics detail, library notes/transfer, journal metadata, object lookup, visualizations, or reference parsing, use the official ADS API documentation directly.

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

## Post-Install: Create and Set Your ADS API Token

After installing the skill or plugin, create a personal ADS API token before your first ADS request. The token is required for search, export, library, metrics, citation-helper, and resolver calls.

1. Open [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token).
2. Register for an ADS account or sign in with your existing account.
3. If ADS does not open the token page directly, go to your account settings and choose **API Token**.
4. Click **Generate a new key**.
5. Copy the token once and keep it private. Do not commit it to this repository or paste it into shared logs.
6. Save it as an environment variable named `ADS_API_TOKEN`:

```bash
export ADS_API_TOKEN="paste-your-token-here"
```

```powershell
[System.Environment]::SetEnvironmentVariable("ADS_API_TOKEN", "paste-your-token-here", "User")
```

7. Restart your terminal or host assistant session so it can read the new environment variable.

## Agent Prompts

If your host assistant can edit files and run shell commands, use one of these prompts for a faster install path.

### Codex Agent Prompt

```text
Install the NASA ADS skill from https://github.com/SukiYume/nasa-ads-skill into this repository by copying `plugins/nasa-ads` into `./plugins/nasa-ads`, then merge the `nasa-ads` entry from `.agents/plugins/marketplace.json` into `./.agents/plugins/marketplace.json` without overwriting existing plugins.
```

For skill-only install:

```text
Install only the NASA ADS skill from https://github.com/SukiYume/nasa-ads-skill by copying `plugins/nasa-ads/skills/nasa-ads/SKILL.md` to `$CODEX_HOME/skills/nasa-ads/SKILL.md` (default `~/.codex/skills/nasa-ads/SKILL.md`).
```

### Claude Code Agent Prompt

```text
Add `SukiYume/nasa-ads-skill` as a Claude plugin marketplace and install `nasa-ads@nasa-ads-community`, then confirm the NASA ADS slash commands are available.
```

### Gemini CLI Agent Prompt

```text
Install the NASA ADS skill from https://github.com/SukiYume/nasa-ads-skill by placing `plugins/nasa-ads/skills/nasa-ads/SKILL.md` in this project and adding `@./plugins/nasa-ads/skills/nasa-ads/SKILL.md` to `GEMINI.md`.
```

### Generic Assistant Agent Prompt

```text
Download `https://raw.githubusercontent.com/SukiYume/nasa-ads-skill/master/plugins/nasa-ads/skills/nasa-ads/SKILL.md` and load it as a reusable Markdown skill for NASA ADS search, metadata, BibTeX, libraries, metrics, and resolver workflows.
```

After installation, remind the user to complete [Post-Install: Create and Set Your ADS API Token](#post-install-create-and-set-your-ads-api-token). Do not store tokens in this repository or shared logs.

## Manual Installation

### Claude Code Manual Install

Add this repository as a plugin marketplace, then install the plugin. This applies to Claude Code CLI, Desktop, VS Code, and JetBrains.

```bash
# Step 1: Add the marketplace
claude plugin marketplace add SukiYume/nasa-ads-skill

# Step 2: Install the plugin
claude plugin install nasa-ads@nasa-ads-community
```

Or from inside a Claude Code session:

```text
/plugin marketplace add SukiYume/nasa-ads-skill
/plugin install nasa-ads@nasa-ads-community
```

After installation, you get five slash commands:

```text
/nasa-ads:ads-search author:Einstein gravitational waves
/nasa-ads:ads-bibtex 2016PhRvL.116f1102A
/nasa-ads:ads-library list
/nasa-ads:ads-metrics 2016PhRvL.116f1102A
/nasa-ads:ads-cite similar 2016PhRvL.116f1102A
```

`/nasa-ads:ads-library` supports list/view/create/add/remove plus metadata updates, query-based edits, sharing, set operations, and library deletion.

The skill also activates automatically from plain-language requests about literature searches, published-claim checks, papers, citations, ADS, BibTeX, arXiv, libraries, or metrics.

Before running the first command, complete [Post-Install: Create and Set Your ADS API Token](#post-install-create-and-set-your-ads-api-token). The commands will fail with `401 Unauthorized` or ask for a token if `ADS_API_TOKEN` or `ADS_DEV_KEY` is missing.

### Codex Manual Install

**Option A: Repo-local plugin install**

1. Copy the `plugins/nasa-ads` directory into your project
2. Merge the `nasa-ads` plugin entry into `.agents/plugins/marketplace.json`

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git /tmp/nasa-ads-skill
cp -r /tmp/nasa-ads-skill/plugins/nasa-ads ./plugins/nasa-ads
```

Use the entry in the cloned repository's `.agents/plugins/marketplace.json` as the source of truth when merging. Do not overwrite existing plugins.

**Option B: Personal install (available in all repos)**

```bash
cp -r plugins/nasa-ads ~/plugins/nasa-ads
mkdir -p ~/.agents/plugins
# Merge the nasa-ads entry into ~/.agents/plugins/marketplace.json; do not overwrite existing plugins.
```

**Option C: Skill-only (no plugin metadata)**

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills/nasa-ads"
cp plugins/nasa-ads/skills/nasa-ads/SKILL.md "${CODEX_HOME:-$HOME/.codex}/skills/nasa-ads/SKILL.md"
```

For the best Codex UI metadata in a skill-only install, also copy `plugins/nasa-ads/skills/nasa-ads/agents/openai.yaml` to the same relative `agents/openai.yaml` path.

### Gemini CLI Manual Install

Add this line to your project's `GEMINI.md`:

```text
@./plugins/nasa-ads/skills/nasa-ads/SKILL.md
```

Or copy the skill file into your Gemini skill directory.

### Generic Assistant Manual Install

The core file is `plugins/nasa-ads/skills/nasa-ads/SKILL.md` — a self-contained ADS API reference in Markdown. Copy it into any assistant's skill/prompt directory.

## Usage

Plain-language prompts:

- "Search ADS for recent papers on exoplanet atmospheres"
- "Check whether this claim has been mentioned in the astronomy literature"
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
│               ├── agents/
│               │   └── openai.yaml
│               └── SKILL.md
├── AGENTS.md
├── CLAUDE.md
├── GEMINI.md
├── README.zh-CN.md
└── README.md
```

The detailed ADS API reference lives in `plugins/nasa-ads/skills/nasa-ads/SKILL.md`, and the Claude command files are task-specific wrappers that should stay aligned with it.

## Primary API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/search/query` | GET | Search for papers |
| `/search/bigquery` | POST | Batch bibcode lookup |
| `/export/<format>` | GET/POST | Standard citation exports |
| `/biblib/libraries` | GET/POST | List or create libraries |
| `/biblib/libraries/<id>` | GET | View library contents |
| `/biblib/documents/<id>` | POST/PUT/DELETE | POST adds/removes documents, PUT updates library metadata, DELETE removes the library |
| `/biblib/query/<id>` | GET/POST | Add or remove papers by query |
| `/biblib/libraries/operations/<id>` | POST | Library set operations |
| `/biblib/permissions/<id>` | GET/POST | Library permissions |
| `/metrics` | POST | Citation metrics and indicators |
| `/citation_helper` | POST | Suggested citations |
| `/resolver/<bibcode>` | GET | Full-text and data links |

ADS OpenAPI also exposes endpoints outside this skill's normal workflow, including `/metrics/<bibcode>`, `/metrics/detail`, `/biblib/notes/<id>/<bibcode>`, `/biblib/transfer/<id>`, journals, objects, reference parsing, and visualizations. Use the official ADS API documentation for those less common workflows.

## Notes

- The packaged commands assume the assistant can run shell commands.
- The bundled examples now fall back from `ADS_API_TOKEN` to `ADS_DEV_KEY`.
- No token is stored in this repository.
- If you add or change ADS workflows, update `SKILL.md` first and then any Claude command files that expose the same workflow.

## License

MIT
