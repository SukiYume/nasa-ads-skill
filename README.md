<h1 align="center">NASA ADS Skill</h1>

<div align="center">

**Full-text research judgment with reusable local literature memory**

Use the NASA Astrophysics Data System from Claude Code, Codex, Gemini CLI, or another Markdown-skill host.

[![NASA ADS](https://img.shields.io/badge/NASA%20ADS-Developer%20API-0B3D91)](https://ui.adsabs.harvard.edu/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-D97757)](https://code.claude.com/docs/en/discover-plugins)
[![Codex](https://img.shields.io/badge/Codex-plugin%20%2B%20skill-10A37F)](https://developers.openai.com/plugins/)
[![Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-GEMINI.md-4285F4)](https://geminicli.com/docs/cli/gemini-md/)
[![Version](https://img.shields.io/badge/version-1.12.0-6f42c1)](plugins/nasa-ads/.codex-plugin/plugin.json)
[![License](https://img.shields.io/badge/license-MIT-2ea44f)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/SukiYume/nasa-ads-skill.svg?label=Stars&logo=github)](https://github.com/SukiYume/nasa-ads-skill)

[Overview](#overview) ·
[Agent install](#install-with-one-agent-prompt) ·
[Hosts](#supported-hosts) ·
[Install](#install) ·
[Configure the token](#configure-the-ads-token) ·
[Verify](#verify-the-api) ·
[Use it](#use-it) ·
[Troubleshooting](#troubleshooting) ·
[简体中文](README.zh-CN.md)

</div>

---

## Overview

NASA ADS Skill packages the public [NASA Astrophysics Data System Developer API](https://ui.adsabs.harvard.edu/help/api/) as a reusable workflow for Claude Code, Codex, Gemini CLI, and compatible Markdown-skill hosts. It can search astronomy and astrophysics literature, retrieve and read lawful article full text, preserve rich multi-topic paper knowledge in a searchable local database, reuse prior reading by exact article version and topic coverage, inspect publication metadata, export citations, work with ADS libraries, calculate bibliometric summaries, and discover related papers or data links.

The host sends requests directly from your computer to `https://api.adsabs.harvard.edu`. This repository stores no ADS token and runs no proxy service.

This README is the reader guide: install the project on a new computer, configure the token, verify the connection, and troubleshoot the host. [`SKILL.md`](plugins/nasa-ads/skills/nasa-ads/SKILL.md) is the agent runtime contract and intentionally does not repeat installation guidance.

The skill keeps research judgment in agent instructions and repeatable mechanics in three bundled Python CLIs. They handle stable ADS API transport; deterministic full-text discovery, download, validation, caching, extraction, scan detection, and page rendering; and a version-aware SQLite literature library with a content-addressed object store and full-text search. Their core path uses the Python standard library; optional PDF helpers improve extraction and rendering. The ADS CLI rejects authenticated redirects and treats ADS error payloads as failed operations.

## Install with One Agent Prompt

If an agent with terminal and internet access is already running on the computer, copy the single sentence below into it. This is a natural-language prompt, not a shell command.

```text
Install the current NASA ADS Skill from https://github.com/SukiYume/nasa-ads-skill on this computer: read the repository README and SKILL.md completely, identify the agent host you are running in, install any missing documented prerequisites and the complete skill through that host's README instructions, replace only an existing nasa-ads installation if necessary, check ADS_API_TOKEN and then ADS_DEV_KEY without displaying either value and direct me to the documented token setup if both are absent, verify that SKILL.md, agents/openai.yaml, scripts/ads_api.py, scripts/fulltext.py, scripts/literature_db.py, references/ads-cli.md, references/fulltext.md, references/literature-memory.md, references/digest-schema.md, references/libraries.md, and references/http-fallback.md are installed, run all three CLIs with --version, run the documented public-paper API smoke test when credentials are available, run the arXiv full-text and literature-memory smoke tests, and report the installation path, version, and validation result.
```

## Supported Hosts

| Host | Integration | What becomes available |
|---|---|---|
| Claude Code | Marketplace plugin | Seven namespaced slash commands plus natural-language skill activation |
| Codex CLI / desktop app | Marketplace plugin | Installable NASA ADS skill with UI metadata |
| Codex CLI / IDE extension | Standalone skill | `$nasa-ads` and automatic activation from matching requests |
| Gemini CLI | `GEMINI.md` import | Project or user-level NASA ADS instructions |
| Other assistants | Markdown skill folder | The shared `SKILL.md` workflow when the host supports reusable instructions and shell access |

## Capabilities

| Capability | Examples |
|---|---|
| Literature search | Author, title, abstract, full text, bibcode, DOI, arXiv ID, ORCID, year, journal, or target name |
| Claim checking | Search several formulations, triage abstracts, read material papers in full, and report evidence coverage |
| Full-text reading | Published open versions, author manuscripts, direct arXiv HTML/PDF, ADS scans, caching, extraction, and visual fallback |
| Literature memory | Version-aware SQLite records, verified article objects, one complete schema-version-2 digest per exact article version, section-to-facet coverage, atomic findings, health audits, recoverable backups, and metadata/summary/full-text search |
| Metadata | Title, authors, abstract, year, venue, DOI, identifiers, citation count, and read count |
| Citation export | BibTeX, BibTeX with abstracts, AASTeX, MNRAS, RIS, EndNote, IEEE, XML formats, and more |
| ADS libraries | List, view, create, update, share, combine, empty, and delete libraries |
| Bibliometrics | Basic statistics, citations, h-index, g-index, i10-index, histograms, and time series |
| Discovery | Suggested citations, similar/useful papers, publisher pages, arXiv, and data-archive links |

Facets are created dynamically from each article's independent research questions and evidence chains. The database does not prescribe FRB, exoplanet, cosmology, theory, simulation, catalog, or instrument-specific fields.

Ordinary research applies a per-article open gate. When the agent inspects any article body, page, figure, caption, table, equation, appendix, or quotation context, it first checks the exact version in local memory. A missing or incomplete exact version receives complete full-text or whole-document visual reading, a layered digest of every material scientific dimension, validation, and ingest before the requested detail is used. Persistent ingest is the default skill behavior. ADS metadata and abstract triage stay outside this gate, and unrelated database gaps stay outside the current task.

## How It Works

```mermaid
flowchart LR
    A["Your request"] --> B["Claude Code / Codex / Gemini CLI"]
    S["NASA ADS Skill"] --> B
    B --> M["Markdown research judgment"]
    M --> P["ADS API CLI<br/>stable read-only calls"]
    M --> F["Full-text CLI<br/>fetch, cache, extract"]
    M --> L["Literature-memory CLI<br/>lookup, index, reuse"]
    T["ADS_API_TOKEN<br/>or ADS_DEV_KEY"] --> P
    P --> C["ADS Developer API"]
    F --> X["Publisher / author / arXiv / ADS scan"]
    C --> D["JSON or citation text"]
    X --> R["Text / PDF / rendered pages"]
    R --> M
    M --> K["Layered digest<br/>facets + evidence locators"]
    R --> L
    K --> L
    L --> M
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
4. **Python 3.10 or newer**, available from [python.org/downloads](https://www.python.org/downloads/), is required for the complete full-text and literature-memory workflow. The three bundled CLIs need no third-party Python package on their core path. `curl` on macOS/Linux/WSL or PowerShell on Windows provides a limited ADS metadata/API fallback when Python is unavailable; it does not provide full-text preparation or persistent literature memory.
5. **Optional PDF helpers**: `pdftotext` and `pdfinfo` improve PDF text handling; `pdftoppm` renders scanned pages. A capable host can visually read a downloaded PDF or rendered pages when these helpers are absent.
6. **Outbound HTTPS access** to `api.adsabs.harvard.edu`, `arxiv.org`, and any selected lawful publisher or repository source.

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

Choose one host below. Claude Code and Codex can add the public GitHub repository directly as a marketplace. Standalone and Gemini installations keep a local source clone so they can be updated later.

### Claude Code Plugin

These commands work in macOS, Linux, Windows PowerShell, and Windows Command Prompt after Claude Code is installed.

1. Add the GitHub repository as a Claude Code marketplace:

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
/nasa-ads:ads-fulltext <bibcodes, DOIs, or arXiv IDs>
/nasa-ads:ads-memory <lookup, search, show, stats, or paper topics>
```

Continue with [Configure the ADS token](#configure-the-ads-token), then run the public-paper test in [Verify the API](#verify-the-api).

### Codex Plugin

Codex plugins are available in Codex CLI and Codex in the desktop app. Use the standalone-skill path below for the IDE extension.

1. Add the GitHub repository as a Codex marketplace:

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

Continue with [Configure the ADS token](#configure-the-ads-token), then run the public-paper test in [Verify the API](#verify-the-api).

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
  && test -f "$HOME/.agents/skills/nasa-ads/agents/openai.yaml" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/ads_api.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/fulltext.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/literature_db.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/ads-cli.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/fulltext.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/literature-memory.md" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/digest-schema.md" \
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
  (Test-Path "$HOME\.agents\skills\nasa-ads\agents\openai.yaml") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\ads_api.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\fulltext.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\literature_db.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\ads-cli.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\fulltext.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\literature-memory.md") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\digest-schema.md") -and `
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
git clone https://github.com/SukiYume/nasa-ads-skill.git
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

### Installed host

Restart the host after setting a persistent token. In Claude Code, run:

```text
/nasa-ads:ads-search bibcode:2016PhRvL.116f1102A
```

In Codex, Gemini CLI, or another host, send:

```text
Search NASA ADS for bibcode 2016PhRvL.116f1102A and return its title, year, and bibcode.
```

The result should identify *Observation of Gravitational Waves from a Binary Black Hole Merger* and include `2016PhRvL.116f1102A`. A missing-token message means the environment variable was not inherited by the host; an HTTP error should be handled with [Troubleshooting](#troubleshooting).

### Bundled Python CLI

Standalone Codex and Gemini installations created a source checkout at a path shown below. Move into the matching directory before running the CLI.

On macOS, Linux, or WSL:

```bash
cd "$HOME/.local/share/nasa-ads-skill"  # standalone Codex
# For Gemini CLI instead:
# cd "$HOME/.gemini/nasa-ads-skill"
```

Then run:

```bash
python3 plugins/nasa-ads/skills/nasa-ads/scripts/ads_api.py search \
  --query 'bibcode:2016PhRvL.116f1102A' \
  --fields bibcode,title,year \
  --rows 1
```

On Windows PowerShell:

```powershell
Set-Location "$HOME\nasa-ads-skill-source"  # standalone Codex
# For Gemini CLI instead:
# Set-Location "$HOME\.gemini\nasa-ads-skill"
```

Then run:

```powershell
python plugins\nasa-ads\skills\nasa-ads\scripts\ads_api.py search `
  --query 'bibcode:2016PhRvL.116f1102A' `
  --fields 'bibcode,title,year' `
  --rows 1
```

Use `py -3` in place of `python` when that is how Python is registered. If you cloned the repository to another location, enter that checkout instead. The JSON response should contain the bibcode `2016PhRvL.116f1102A`.

### Full-text smoke test

This public arXiv paper has an official HTML version, so the smoke test needs no PDF helper. It also works without an ADS token when no token is present.

macOS, Linux, or WSL:

```bash
python3 plugins/nasa-ads/skills/nasa-ads/scripts/fulltext.py fetch \
  arXiv:1901.04502 \
  --source arxiv
```

Windows PowerShell:

```powershell
python plugins\nasa-ads\skills\nasa-ads\scripts\fulltext.py fetch `
  'arXiv:1901.04502' `
  --source arxiv
```

The result should report `status: fulltext`, select `https://arxiv.org/html/1901.04502`, and provide existing `artifact_path`, `text_path`, and `manifest_path` files under the user cache. The script uses `https://arxiv.org/pdf/<id>` automatically when official HTML is unavailable. Pass the returned `text_path` to `fulltext.py outline <text_path>` to inspect the inferred article structure before summarizing it.

Use `--format pdf` when you explicitly need the PDF for equation, figure, table, pagination, or visual-reading checks; `--format html` requests only structured HTML. The default `--format auto` keeps the HTML-first fallback workflow.

### Literature-memory smoke test

The database CLI can verify its schema and digest contract without an ADS token. `template` prints JSON and does not create a library.

macOS, Linux, or WSL:

```bash
python3 plugins/nasa-ads/skills/nasa-ads/scripts/literature_db.py --version
python3 plugins/nasa-ads/skills/nasa-ads/scripts/literature_db.py template
```

Windows PowerShell:

```powershell
python plugins\nasa-ads\skills\nasa-ads\scripts\literature_db.py --version
python plugins\nasa-ads\skills\nasa-ads\scripts\literature_db.py template
```

The CLI version command on either platform should report `1.12.0`. The schema-version-2 template should contain `overview`, `facets`, `findings`, `global_limitations`, and `reading.coverage`. `init`, ingest, enrichment, backup, and reindex operations create or update the live library under `%LOCALAPPDATA%\nasa-ads\literature` on Windows or `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature` on macOS/Linux. Read commands return an empty result for a missing library and create no files. Set `NASA_ADS_LITERATURE_DIR` to choose another location.

### Direct HTTP fallback

Use this only when Python 3 cannot run the bundled CLI or an endpoint is not exposed by it. Follow the credential preflight, redirect rule, response checks, and platform-specific example in [`references/http-fallback.md`](plugins/nasa-ads/skills/nasa-ads/references/http-fallback.md).

## Use It

Natural-language requests work in every supported host:

- “Search ADS for recent refereed papers on exoplanet atmospheres.”
- “Check whether this claim has been mentioned in astronomy literature, and show your search terms.”
- “Get the BibTeX for `2016PhRvL.116f1102A`.”
- “List my ADS libraries.”
- “Show citation metrics for these bibcodes.”
- “Find papers similar to `2016PhRvL.116f1102A`.”
- “Retrieve and read the full text of `2019MNRAS.489..176M`, then summarize its methods, results, and limitations.”
- “Search my literature memory for papers with circular-polarization sign reversals, and show the matching findings and evidence locations.”
- “Look up `2023ApJ...955..142Z` in the database and tell me whether activity, waiting time, energy distribution, and synthetic spectrum are already covered.”
- “Audit my literature database, create a backup before any repair, and explain every warning.”
- “检索 2022 年以来关于快速射电暴重复暴的论文，并按主题总结。”
- “查一下这个说法有没有天文文献提到，说明检索范围。”

Claude Code command examples:

```text
/nasa-ads:ads-search dark matter year:2020-2024
/nasa-ads:ads-bibtex 2016PhRvL.116f1102A 2017ApJ...848L..12A --format aastex
/nasa-ads:ads-library create "My Reading List"
/nasa-ads:ads-metrics 2016PhRvL.116f1102A
/nasa-ads:ads-cite links 2016PhRvL.116f1102A
/nasa-ads:ads-fulltext 2019MNRAS.489..176M arXiv:1602.03837
/nasa-ads:ads-memory lookup 2023ApJ...955..142Z waiting-time circular-polarization
/nasa-ads:ads-memory audit
```

A literature-research result should be linked and readable, identify the searched scope, distinguish published, preprint, visual-reading, and abstract-only evidence, and report which papers were reused, verified, augmented, newly stored, or refreshed. A paper absent from the database receives complete reading and a structurally validated `full` digest on first ingest; scans receive whole-document `visual` coverage. Facets follow the article's independently reusable scientific dimensions, and every major read section maps to its scientific facets or documented section role. Later requests merge targeted evidence into the single exact-version digest. An approved repair creates a backup and replaces a proven-invalid digest with one complete record. The maintenance CLI provides read-only audits, consistent backups, metadata enrichment, and deterministic reindexing.

## Troubleshooting

| Symptom | Check |
|---|---|
| `git`, `claude`, `codex`, or `gemini` is unknown | Install or update the selected program from the official link in [Before You Install](#before-you-install) |
| Claude marketplace or plugin is missing | Run `claude plugin marketplace update nasa-ads-community`, reinstall if needed, then run `/reload-plugins` |
| Codex marketplace or plugin is missing | Run `codex plugin marketplace upgrade nasa-ads-community`, run `codex plugin add nasa-ads@nasa-ads-community`, and start a new session |
| Codex standalone skill is absent from `/skills` | Confirm `~/.agents/skills/nasa-ads/SKILL.md` exists and start a new session |
| Gemini does not load the instructions | Check the relative path in `~/.gemini/GEMINI.md`, then run `/memory reload` and `/memory show` |
| Python CLI cannot start | Install Python 3.10 or newer, try `python3`, `python`, or `py -3`, and confirm the complete skill folder includes `scripts/ads_api.py`, `scripts/fulltext.py`, and `scripts/literature_db.py` |
| `401 Unauthorized` | Set a current token, open a new terminal, and verify the `Bearer` header path through the smoke test |
| `403 Forbidden` | Check ADS account access and library permissions |
| `429 Too Many Requests` | Read the `X-RateLimit-Remaining` and `X-RateLimit-Reset` response headers |
| Unexpected API redirect | Stop and update the installed skill or endpoint; never follow an authenticated redirect |
| ADS application error with HTTP `200` | Treat the operation as failed and report the returned error detail |
| Search returns no papers | Remove unnecessary filters, try synonyms and spelling variants, and record the query scope |
| Query breaks around `&` or spaces | Use the bundled CLI, which URL-encodes parameters; direct HTTP fallbacks must encode `q`, `fq`, and `sort` |
| arXiv HTML returns `404` | Let `fulltext.py` continue to the official `/pdf/<id>` candidate; install `pdftotext` or use host PDF vision when needed |
| Full-text status is `needs_visual_reading` | Open the selected PDF with the host's PDF vision tool or use `fulltext.py render --pages <range>` in batches of at most twenty pages |
| Full-text status is `abstract_only` | Inspect candidate errors, report the access limitation, and keep scientific conclusions within abstract-level evidence |
| First ingest rejects a `targeted` digest | Finish the complete article reading and submit a `full` digest, or inspect every scan page and submit whole-document `visual` coverage |
| A stored paper returns `targeted_reading` | The requested facet is missing; search the stored full text, read the complete relevant sections, then ingest the added facet with `--merge` |
| A stored paper returns `version_changed` | Compare the refreshed manifest's canonical content hash; changed scientific text becomes a separate version, while an HTML/PDF shell-only change reuses the existing digest |
| A read command reports a database-schema mismatch | Create a complete backup with the compatible pre-update CLI, install the current files, run `literature_db.py init` explicitly, then run `audit` |
| Summary search misses an exact article phrase | Retry with `literature_db.py search '<phrase>' --scope fulltext --mode phrase`; verify quotations against the stored article |
| SQLite lacks FTS5 | The database CLI automatically uses deterministic case-insensitive term matching; advanced `--mode fts` queries are unavailable |
| `audit` lists a fresh arXiv record under `arxiv_records_awaiting_ads_bibcode` | The paper remains searchable with arXiv metadata; rerun discovery and `enrich` after ADS assigns a bibcode |
| A Chinese query misses a known facet | Update to the current release; CJK term queries automatically use substring matching and report `search_engine: substring` |

## Updating an Existing Install

Version 1.11.0 introduced database schema 2. Create a complete library backup with the installed pre-update CLI, update the skill or plugin files, and run `literature_db.py init`. This one-time migration keeps the active highest revision for each article version, removes the digest revision fields, and enforces one digest per article version. Version 1.12.0 keeps all read commands read-only, so they report a schema mismatch before migration. Run `literature_db.py audit` after migration.

For a Claude Code or Codex plugin, refresh the marketplace and installed plugin:

```bash
claude plugin marketplace update nasa-ads-community
claude plugin update nasa-ads@nasa-ads-community
```

```bash
codex plugin marketplace upgrade nasa-ads-community
codex plugin add nasa-ads@nasa-ads-community
```

For a standalone skill or Gemini CLI import, update the source path chosen during installation. The commands below use the paths shown in this README.

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
- Never follow redirects for authenticated ADS API requests.
- Full-text requests send no ADS authorization header to arXiv, publishers, author repositories, or Unpaywall.
- Full-text artifacts are cached under the user cache directory; keep restricted manuscripts and shared-machine caches within the user's access policy.
- Literature objects and digests remain local under the user data directory. The database is not uploaded to ADS, arXiv, publishers, or an embedding service.
- The database CLI exposes no delete command. Back up the complete library and ask for explicit confirmation before any manual deletion, clearing, relocation, or complete-digest replacement.
- Confirm destructive ADS library actions, note replacement or deletion, permission changes, and ownership transfer.
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
