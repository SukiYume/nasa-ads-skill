<h1 align="center">NASA ADS Skill</h1>

<div align="center">

**Literature search, citation export, libraries, and bibliometrics for AI coding agents**

Use the NASA Astrophysics Data System from Claude Code, Codex, Gemini CLI, or another Markdown-skill host.

[![NASA ADS](https://img.shields.io/badge/NASA%20ADS-Developer%20API-0B3D91)](https://ui.adsabs.harvard.edu/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-D97757)](https://code.claude.com/docs/en/discover-plugins)
[![Codex](https://img.shields.io/badge/Codex-plugin%20%2B%20skill-10A37F)](https://developers.openai.com/plugins/)
[![Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-GEMINI.md-4285F4)](https://geminicli.com/docs/cli/gemini-md/)
[![Version](https://img.shields.io/badge/version-1.5.1-6f42c1)](plugins/nasa-ads/.codex-plugin/plugin.json)
[![License](https://img.shields.io/badge/license-MIT-2ea44f)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/SukiYume/nasa-ads-skill.svg?label=Stars&logo=github)](https://github.com/SukiYume/nasa-ads-skill)

[Overview](#overview) ·
[Install](#install) ·
[Configure the token](#configure-the-ads-token) ·
[Verify](#verify-the-api) ·
[Use it](#use-it) ·
[Troubleshooting](#troubleshooting) ·
[简体中文](README.zh-CN.md)

</div>

---

## Overview

NASA ADS Skill packages the public [NASA Astrophysics Data System Developer API](https://ui.adsabs.harvard.edu/help/api/) as a reusable agent workflow. The installed host can search astronomy and astrophysics literature, inspect publication metadata, export citations, work with ADS libraries, calculate bibliometric summaries, and discover related papers or full-text/data links.

The host sends requests directly from your computer to `https://api.adsabs.harvard.edu`. This repository stores no ADS token and runs no proxy service.

The shared Markdown skill handles query design, evidence assessment, safety confirmations, and result synthesis. A bundled, standard-library Python CLI handles stable read-only API transport for search, batch lookup, citation export, metrics, citation suggestions, and resource resolution.

| Host | Integration | What becomes available |
|---|---|---|
| Claude Code | Marketplace plugin | Five namespaced slash commands plus natural-language skill activation |
| Codex CLI / desktop app | Marketplace plugin | Installable NASA ADS skill with UI metadata |
| Codex CLI / IDE extension | Standalone skill | `$nasa-ads` and automatic activation from matching requests |
| Gemini CLI | `GEMINI.md` import | Project or user-level NASA ADS instructions |
| Other assistants | Markdown skill folder | The shared `SKILL.md` workflow when the host supports reusable instructions and shell access |

## Capabilities

| Capability | Examples |
|---|---|
| Literature search | Author, title, abstract, full text, bibcode, DOI, arXiv ID, ORCID, year, journal, or astronomical object |
| Claim checking | Search several formulations, inspect abstracts, and report the searched scope |
| Metadata | Title, authors, abstract, year, venue, DOI, identifiers, citation count, and read count |
| Citation export | BibTeX, BibTeX with abstracts, AASTeX, MNRAS, RIS, EndNote, IEEE, XML formats, and more |
| ADS libraries | List, view, create, update, share, combine, empty, and delete libraries |
| Bibliometrics | Basic statistics, citations, h-index, g-index, i10-index, histograms, and time series |
| Discovery | Suggested citations, similar/useful papers, publisher pages, arXiv, and data-archive links |

## How It Works

```mermaid
flowchart LR
    A["Your request"] --> B["Claude Code / Codex / Gemini CLI"]
    S["NASA ADS Skill"] --> B
    B --> M["Markdown research judgment"]
    M --> P["Bundled Python CLI<br/>stable read-only calls"]
    T["ADS_API_TOKEN<br/>or ADS_DEV_KEY"] --> P
    P --> C["ADS Developer API"]
    C --> D["JSON or citation text"]
    M --> E["Linked, reader-facing result"]
    D --> E
```

## Before You Install

Prepare these items on the new computer:

1. **Git**, available from [git-scm.com/downloads](https://git-scm.com/downloads).
2. **One supported host**:
   - [Claude Code setup](https://code.claude.com/docs/en/setup)
   - [Codex CLI setup](https://developers.openai.com/codex/cli/)
   - [Gemini CLI installation](https://geminicli.com/docs/get-started/installation/)
3. **An ADS account and API token**, created later in [Configure the ADS token](#configure-the-ads-token).
4. **One API transport**: Python 3.10 or newer is the recommended default and is available from [python.org/downloads](https://www.python.org/downloads/). The bundled CLI uses only the Python standard library. If Python is unavailable, use `curl` on macOS/Linux/WSL or PowerShell on Windows for the conditional direct HTTP fallback.
5. **Outbound HTTPS access** to `api.adsabs.harvard.edu`.

Check the installed commands:

```bash
git --version
python3 --version   # macOS, Linux, or WSL
python --version    # Windows; "py -3 --version" is also supported
claude --version   # when using Claude Code
codex --version    # when using Codex
gemini --version   # when using Gemini CLI
```

If a selected host command is missing, install or update that host from its official setup page before continuing.

## Install

Choose one host below. Plugin installation is the simplest path for Claude Code and Codex. Standalone installation is available for Codex IDE users and other local-skill workflows.

### Claude Code Plugin

These commands work in macOS, Linux, Windows PowerShell, and Windows Command Prompt after Claude Code is installed.

1. Add this GitHub repository as a Claude Code marketplace:

```bash
claude plugin marketplace add SukiYume/nasa-ads-skill
```

2. Install the `nasa-ads` plugin from that marketplace:

```bash
claude plugin install nasa-ads@nasa-ads-community
```

3. Confirm the installation:

```bash
claude plugin list
```

Look for `nasa-ads@nasa-ads-community`.

4. Start Claude Code:

```bash
claude
```

Run `/reload-plugins` if the installation happened during an existing session. The plugin provides:

```text
/nasa-ads:ads-search <query>
/nasa-ads:ads-bibtex <bibcodes>
/nasa-ads:ads-library [subcommand]
/nasa-ads:ads-metrics <bibcodes>
/nasa-ads:ads-cite [subcommand]
```

Continue with [Configure the ADS token](#configure-the-ads-token), then run the first search in [Use it](#use-it).

### Codex Plugin

Codex plugins are available in Codex CLI and Codex in the desktop app. Use the standalone-skill path below for the IDE extension.

1. Add this repository as a Codex marketplace:

```bash
codex plugin marketplace add SukiYume/nasa-ads-skill
```

2. Install the plugin:

```bash
codex plugin add nasa-ads@nasa-ads-community
```

3. Confirm that Codex sees it:

```bash
codex plugin list
```

4. Start a new Codex session so the bundled skill enters the session’s skill catalog:

```bash
codex
```

Invoke it explicitly with `$nasa-ads`, open `/skills`, or describe an astronomy-literature task in plain language.

Continue with [Configure the ADS token](#configure-the-ads-token).

### Codex Standalone Skill

Codex currently discovers user-level standalone skills under `~/.agents/skills`. This path applies to Codex CLI and the IDE extension.

#### macOS, Linux, or WSL

Keep a source clone at a stable user-level path, then copy the skill contents into Codex’s discovery directory:

```bash
mkdir -p "$HOME/.local/share"
git clone --depth 1 \
  https://github.com/SukiYume/nasa-ads-skill.git \
  "$HOME/.local/share/nasa-ads-skill"
mkdir -p "$HOME/.agents/skills/nasa-ads"
cp -R \
  "$HOME/.local/share/nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/." \
  "$HOME/.agents/skills/nasa-ads/"
```

Verify the required file:

```bash
test -f "$HOME/.agents/skills/nasa-ads/SKILL.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/ads_api.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/http-fallback.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/libraries.md" \
  && echo "NASA ADS skill installed"
```

#### Windows PowerShell

Keep a source clone at a stable user-level path, then copy the skill contents into Codex’s discovery directory:

```powershell
$nasaAdsSource = Join-Path $HOME 'nasa-ads-skill-source'
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
git clone --depth 1 `
  https://github.com/SukiYume/nasa-ads-skill.git `
  $nasaAdsSource
New-Item -ItemType Directory -Force $nasaAdsSkill | Out-Null
Copy-Item -Recurse -Force `
  (Join-Path $nasaAdsSource 'plugins\nasa-ads\skills\nasa-ads\*') `
  $nasaAdsSkill
```

Verify the required file:

```powershell
$nasaAdsSkillReady = `
  (Test-Path "$HOME\.agents\skills\nasa-ads\SKILL.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\ads_api.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\http-fallback.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\libraries.md")
$nasaAdsSkillReady
```

A successful check returns `True`.

Start a new Codex session. Use `/skills` to inspect the catalog or type `$nasa-ads` in the prompt.

For a repository-only installation, copy the same `nasa-ads` skill folder to `<repository>/.agents/skills/nasa-ads`.

### Gemini CLI

Gemini CLI loads instruction files through `GEMINI.md`. The following user-level setup makes NASA ADS available in every Gemini CLI project.

#### macOS, Linux, or WSL

```bash
mkdir -p "$HOME/.gemini"
git clone --depth 1 \
  https://github.com/SukiYume/nasa-ads-skill.git \
  "$HOME/.gemini/nasa-ads-skill"
printf '\n@./nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/SKILL.md\n' \
  >> "$HOME/.gemini/GEMINI.md"
```

#### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force "$HOME\.gemini" | Out-Null
git clone --depth 1 `
  https://github.com/SukiYume/nasa-ads-skill.git `
  "$HOME\.gemini\nasa-ads-skill"
Add-Content -Path "$HOME\.gemini\GEMINI.md" -Value `
  "`n@./nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/SKILL.md"
```

Start Gemini CLI:

```bash
gemini
```

Then run:

```text
/memory reload
/memory show
```

Confirm that the loaded memory contains the `NASA ADS` heading. The repository’s own [`GEMINI.md`](GEMINI.md) demonstrates the same relative-import format for a project-level setup.

### Generic Markdown-Skill Host

1. Clone the repository:

```bash
git clone --depth 1 https://github.com/SukiYume/nasa-ads-skill.git
```

2. Copy the complete `plugins/nasa-ads/skills/nasa-ads/` folder into the host’s documented skill or prompt directory.
3. Configure the host to load `SKILL.md`.
4. Confirm that the host can run the bundled CLI with Python 3, or can use `curl`/PowerShell for direct HTTP fallback.
5. Set the ADS token as described below.
6. Run the public-paper smoke test in [Verify the API](#verify-the-api).

The exact discovery directory and invocation syntax depend on the host. Consult that host’s current documentation when it does not use the Claude Code, Codex, or Gemini conventions above.

## Configure the ADS Token

Every ADS Developer API request requires a personal token.

1. Open [ADS token settings](https://ui.adsabs.harvard.edu/#user/settings/token).
2. Register for ADS or sign in.
3. Open account settings and select **API Token** if the direct link lands elsewhere.
4. Select **Generate a new key**.
5. Copy the token and keep it private.

Use `ADS_API_TOKEN` as the primary environment variable. `ADS_DEV_KEY` remains available as a compatibility fallback.

### macOS, Linux, or WSL

Set the token for the current terminal:

```bash
export ADS_API_TOKEN='paste-your-token-here'
```

This value lasts until that terminal closes. For persistent use, add the same `export` line to the startup file for your shell, commonly `~/.zshrc`, `~/.bashrc`, or `~/.bash_profile`, and open a new terminal.

Verify presence without printing the token:

```bash
if [ -n "${ADS_API_TOKEN:-${ADS_DEV_KEY:-}}" ]; then
  echo "ADS token is set"
else
  echo "ADS token is missing"
fi
```

### Windows PowerShell

Set the token for the current PowerShell session:

```powershell
$env:ADS_API_TOKEN = 'paste-your-token-here'
```

Set a persistent user environment variable:

```powershell
[Environment]::SetEnvironmentVariable(
  'ADS_API_TOKEN',
  'paste-your-token-here',
  'User'
)
```

Open a new terminal and restart the host after the persistent command. Verify presence without printing the token:

```powershell
if ($env:ADS_API_TOKEN -or $env:ADS_DEV_KEY) {
  'ADS token is set'
} else {
  'ADS token is missing'
}
```

Keep the token out of repositories, screenshots, shared logs, shell transcripts, and support messages. Revoke and regenerate it from ADS settings if exposure occurs.

## Verify the API

Use a known public paper to verify network access, authentication, and the ADS response shape.

### Bundled Python CLI

From the repository root on macOS, Linux, or WSL:

```bash
python3 plugins/nasa-ads/skills/nasa-ads/scripts/ads_api.py search \
  --query 'bibcode:2016PhRvL.116f1102A' \
  --fields bibcode,title,year \
  --rows 1
```

From the repository root on Windows PowerShell:

```powershell
python plugins\nasa-ads\skills\nasa-ads\scripts\ads_api.py search `
  --query 'bibcode:2016PhRvL.116f1102A' `
  --fields 'bibcode,title,year' `
  --rows 1
```

Use `py -3` in place of `python` when that is how Python is registered. The JSON response should contain the bibcode `2016PhRvL.116f1102A`.

### Direct HTTP fallback

Use this only when Python 3 cannot run the bundled CLI or an endpoint is not exposed by it. Follow the credential preflight and platform-specific example in [`references/http-fallback.md`](plugins/nasa-ads/skills/nasa-ads/references/http-fallback.md).

## Use It

Natural-language requests work in every supported host:

- “Search ADS for recent refereed papers on exoplanet atmospheres.”
- “Check whether this claim has been mentioned in astronomy literature, and show your search terms.”
- “Get the BibTeX for `2016PhRvL.116f1102A`.”
- “List my ADS libraries.”
- “Show citation metrics for these bibcodes.”
- “Find papers similar to `2016PhRvL.116f1102A`.”
- “检索 2022 年以来关于快速射电暴重复暴的论文，并按主题总结。”
- “查一下这个说法有没有天文文献提到，说明检索范围。”

Claude Code command examples:

```text
/nasa-ads:ads-search dark matter year:2020-2024
/nasa-ads:ads-bibtex 2016PhRvL.116f1102A 2017ApJ...848L..12A --format aastex
/nasa-ads:ads-library create "My Reading List"
/nasa-ads:ads-metrics 2016PhRvL.116f1102A
/nasa-ads:ads-cite links 2016PhRvL.116f1102A
```

The skill instructs the agent to return linked, readable results; refine weak literature searches; and label empty searches by their actual query scope.

## API Coverage

The bundled CLI covers `/search/query`, `/search/bigquery`, `/export/<format>`, `/metrics`, `/citation_helper`, and `/resolver/<bibcode>`. Library operations remain in the Markdown workflow so the agent can confirm destructive or shared-state changes immediately before execution.

| Endpoint | Method | Purpose |
|---|---|---|
| `/search/query` | GET | Search papers and retrieve metadata |
| `/search/bigquery` | POST | Batch bibcode lookup with paginated results |
| `/export/<format>` | GET / POST | Single-record or multi-record citation export |
| `/biblib/libraries` | GET / POST | List or create libraries |
| `/biblib/libraries/<id>` | GET | View a library |
| `/biblib/documents/<id>` | POST / PUT / DELETE | Change documents, update metadata, or delete a library |
| `/biblib/query/<id>` | GET / POST | Add or remove papers by ADS query |
| `/biblib/libraries/operations/<id>` | POST | Union, intersection, difference, copy, or empty |
| `/biblib/permissions/<id>` | GET / POST | View or change sharing permissions |
| `/metrics` | POST | Bibliometric summaries and indicators |
| `/citation_helper` | POST | Suggested citations |
| `/resolver/<bibcode>` | GET | Publisher, arXiv, full-text, and data links |

The current public API also exposes specialized endpoints for metrics detail, library notes and transfer, journals, objects, reference parsing, visualizations, and other services. Use the [official ADS API documentation](https://ui.adsabs.harvard.edu/help/api/api-docs.html) for those workflows.

## Repository Layout

```text
nasa-ads-skill/
├── .agents/plugins/marketplace.json       # Codex marketplace
├── .claude-plugin/marketplace.json        # Claude Code marketplace
├── plugins/nasa-ads/
│   ├── .claude-plugin/plugin.json         # Claude Code manifest
│   ├── .codex-plugin/plugin.json          # Codex manifest
│   ├── commands/                          # Claude Code slash commands
│   │   ├── ads-search.md
│   │   ├── ads-bibtex.md
│   │   ├── ads-library.md
│   │   ├── ads-metrics.md
│   │   └── ads-cite.md
│   └── skills/nasa-ads/
│       ├── agents/openai.yaml              # Codex skill UI metadata
│       ├── references/                       # HTTP fallback and library details
│       ├── scripts/ads_api.py                # Standard-library API CLI
│       └── SKILL.md                          # Shared research workflow
├── tests/test_ads_api.py                    # Offline CLI unit tests
├── AGENTS.md
├── CLAUDE.md
├── GEMINI.md
├── README.zh-CN.md
└── README.md
```

## Troubleshooting

| Symptom | Check |
|---|---|
| `git`, `claude`, `codex`, or `gemini` is unknown | Install or update the selected program from the official link in [Before You Install](#before-you-install) |
| Claude marketplace or plugin is missing | Run `claude plugin marketplace update nasa-ads-community`, reinstall if needed, then run `/reload-plugins` |
| Codex marketplace or plugin is missing | Run `codex plugin marketplace upgrade nasa-ads-community`, run `codex plugin add nasa-ads@nasa-ads-community`, and start a new session |
| Codex standalone skill is absent from `/skills` | Confirm `~/.agents/skills/nasa-ads/SKILL.md` exists and start a new session |
| Gemini does not load the instructions | Check the relative path in `~/.gemini/GEMINI.md`, then run `/memory reload` and `/memory show` |
| Python CLI cannot start | Install Python 3.10 or newer, try `python3`, `python`, or `py -3`, and confirm the complete skill folder includes `scripts/ads_api.py` |
| `401 Unauthorized` | Set a current token, open a new terminal, and verify the `Bearer` header path through the smoke test |
| `403 Forbidden` | Check ADS account access and library permissions |
| `429 Too Many Requests` | Read the `X-RateLimit-Remaining` and `X-RateLimit-Reset` response headers |
| Search returns no papers | Remove unnecessary filters, try synonyms and spelling variants, and record the query scope |
| Query breaks around `&` or spaces | Use the bundled CLI, which URL-encodes parameters; direct HTTP fallbacks must encode `q`, `fq`, and `sort` |

## Updating an Existing Install

Version 1.4.0 renamed the marketplace from `nasa-ads-local` to `nasa-ads-community`. If you installed an earlier release, migrate once with the commands for your host:

```bash
claude plugin uninstall nasa-ads@nasa-ads-local
claude plugin marketplace remove nasa-ads-local
claude plugin marketplace add SukiYume/nasa-ads-skill
claude plugin install nasa-ads@nasa-ads-community
```

```bash
codex plugin remove nasa-ads@nasa-ads-local
codex plugin marketplace remove nasa-ads-local
codex plugin marketplace add SukiYume/nasa-ads-skill
codex plugin add nasa-ads@nasa-ads-community
```

For an existing 1.4.0 or newer marketplace, refresh the marketplace and installed plugin:

```bash
claude plugin marketplace update nasa-ads-community
claude plugin update nasa-ads@nasa-ads-community
```

```bash
codex plugin marketplace upgrade nasa-ads-community
codex plugin add nasa-ads@nasa-ads-community
```

For a standalone Codex skill on macOS, Linux, or WSL:

```bash
git -C "$HOME/.local/share/nasa-ads-skill" pull --ff-only
cp -R \
  "$HOME/.local/share/nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads/." \
  "$HOME/.agents/skills/nasa-ads/"
```

For a standalone Codex skill on Windows PowerShell:

```powershell
$nasaAdsSource = Join-Path $HOME 'nasa-ads-skill-source'
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
git -C $nasaAdsSource pull --ff-only
Copy-Item -Recurse -Force `
  (Join-Path $nasaAdsSource 'plugins\nasa-ads\skills\nasa-ads\*') `
  $nasaAdsSkill
```

For Gemini CLI on macOS, Linux, or WSL:

```bash
git -C "$HOME/.gemini/nasa-ads-skill" pull --ff-only
```

For Gemini CLI on Windows PowerShell:

```powershell
git -C "$HOME\.gemini\nasa-ads-skill" pull --ff-only
```

Run `/memory reload` in Gemini CLI after updating. Start a new Codex or Claude Code session after updating those hosts.

## Security

- Review this public repository before installation.
- Keep `ADS_API_TOKEN` and `ADS_DEV_KEY` outside tracked files.
- Confirm destructive ADS library actions and permission changes.
- Treat publisher and data-archive links as external destinations.
- ADS rate limits are endpoint-specific; response headers are the live authority.

## References

- [ADS API overview](https://ui.adsabs.harvard.edu/help/api/)
- [ADS OpenAPI documentation](https://ui.adsabs.harvard.edu/help/api/api-docs.html)
- [ADS Developer API examples](https://github.com/adsabs/adsabs-dev-api)
- [Claude Code plugin installation](https://code.claude.com/docs/en/discover-plugins)
- [OpenAI plugin documentation](https://developers.openai.com/plugins/)
- [Gemini CLI `GEMINI.md` documentation](https://geminicli.com/docs/cli/gemini-md/)

## License

[MIT](LICENSE)

---

<div align="center">

NASA ADS Skill · From a fresh machine to a verified literature search

</div>
