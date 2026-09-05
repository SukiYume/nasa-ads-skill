# Installation and Updates

[Back to README](../README.md#install) · [简体中文](installation.zh-CN.md)

Choose your host, finish its installation steps, configure a token for online ADS access, and verify the result. Each host section contains its own commands. Existing users can go directly to [updates](#updating-an-existing-install).

- [Prerequisites](#before-you-install)
- [Claude Code plugin](#claude-code-plugin)
- [Codex plugin](#codex-plugin)
- [Codex standalone skill](#codex-standalone-skill)
- [Gemini CLI](#gemini-cli)
- [Other hosts](#generic-markdown-skill-host)
- [Register adslib](#register-the-adslib-command)
- [ADS token](#configure-the-ads-token)
- [Installation and API verification](#verify-the-api)
- [Updates](#updating-an-existing-install)

## Before You Install

Prepare these items on the new computer:

1. **Git**, available from [git-scm.com/downloads](https://git-scm.com/downloads).
2. **One supported host**:
   - [Claude Code setup](https://code.claude.com/docs/en/setup)
   - [Codex CLI setup](https://developers.openai.com/codex/cli/)
   - [Gemini CLI installation](https://geminicli.com/docs/get-started/installation/)
3. **An ADS account and API token** for online ADS requests, created in [Configure the ADS token](#configure-the-ads-token). Local library browsing and cached citation export work without a token.
4. **Python 3.10 or newer**, available from [python.org/downloads](https://www.python.org/downloads/), is required for the complete full-text and literature-memory workflow. The four bundled CLIs need no third-party Python package on their core path. `curl` on macOS/Linux/WSL or PowerShell on Windows provides a limited ADS metadata/API fallback when Python is unavailable; it does not provide full-text preparation or persistent literature memory.
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
/nasa-ads:ads-memory <search, collections, serve, citations, pending, or paper topics>
```

Continue with [Register adslib](#register-the-adslib-command) and [Configure the ADS token](#configure-the-ads-token), then run the public-paper test in [Verify the API](#verify-the-api).

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

Continue with [Register adslib](#register-the-adslib-command) and [Configure the ADS token](#configure-the-ads-token), then run the public-paper test in [Verify the API](#verify-the-api).

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
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/library_catalog.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/library_web.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/scripts/adslib.py" \
  && test -f "$HOME/.agents/skills/nasa-ads/assets/library/index.html" \
  && test -f "$HOME/.agents/skills/nasa-ads/assets/library/style.css" \
  && test -f "$HOME/.agents/skills/nasa-ads/assets/library/app.js" \
  && test -f "$HOME/.agents/skills/nasa-ads/references/research-writing.md" \
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
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\library_catalog.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\library_web.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\scripts\adslib.py") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\assets\library\index.html") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\assets\library\style.css") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\assets\library\app.js") -and `
  (Test-Path "$HOME\.agents\skills\nasa-ads\references\research-writing.md") -and `
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

Confirm that the loaded memory contains the `NASA ADS` heading. The repository’s own [`GEMINI.md`](../GEMINI.md) demonstrates the same relative-import format for a project-level setup.

### Generic Markdown-Skill Host

1. Clone the repository:

```bash
git clone https://github.com/SukiYume/nasa-ads-skill.git
```

2. Copy the complete `plugins/nasa-ads/skills/nasa-ads/` folder into the host’s documented skill or prompt directory.
3. Configure the host to load `SKILL.md`.
4. Confirm that the host can run the bundled CLI with Python 3, or can use `curl`/PowerShell for direct HTTP fallback.
5. Set the ADS token for online ADS requests as described below.
6. Run the public-paper smoke test in [Verify the API](#verify-the-api).

The exact discovery directory and invocation syntax depend on the host. Consult that host’s current documentation when it does not use the Claude Code, Codex, or Gemini conventions above.

## Register the adslib Command

Complete this step once after installing the skill on each computer. Then `adslib` opens Web from any directory. Host plugin commands install the resources; this step registers the terminal command. The README's one-sentence installation prompt includes registration.

You can ask the agent to complete it:

> Locate scripts/adslib.py in the currently installed nasa-ads skill, run install to register adslib while preserving existing PATH settings, and verify adslib --version and the library page in a new terminal.

**Windows PowerShell, Codex standalone skill:**

```powershell
python "$HOME\.agents\skills\nasa-ads\scripts\adslib.py" install
```

**macOS, Linux, or WSL, Codex standalone skill:**

```bash
python3 "$HOME/.agents/skills/nasa-ads/scripts/adslib.py" install
```

A Claude standalone skill uses `~/.claude/skills/nasa-ads/scripts/adslib.py`. A marketplace plugin uses `scripts/adslib.py` within the directory containing its loaded `SKILL.md`. Gemini uses the script in its source copy. The agent resolves the actual installed path.

The installer creates `%LOCALAPPDATA%\nasa-ads\bin\adslib.cmd` and adds its directory to the Windows user PATH. macOS/Linux/WSL use `~/.local/bin/adslib`; a marked PATH block is added to the active bash, zsh, or sh configuration when needed. Existing settings and foreign commands are preserved; a conflicting command produces an actionable error. Use `install --bin-dir <directory> --no-path` for a command directory whose PATH you manage yourself.

Verify in a new terminal:

```bash
adslib --version
adslib
```

The version should be `1.14.1`. The browser opens automatically; keep the terminal open while a new service runs, and press `Ctrl+C` to stop it. A matching existing service is reused and the command returns. If the command is missing, restart the terminal app or IDE to load its new PATH, or invoke the installed `adslib.py` directly. Run `install` again after moving the skill, upgrading to a new plugin cache directory, or changing Python.

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

The result should identify *Observation of Gravitational Waves from a Binary Black Hole Merger* and include `2016PhRvL.116f1102A`. A missing-token message means the environment variable was not inherited by the host; an HTTP error should be handled with [Troubleshooting](../README.md#troubleshooting).

### Bundled Python CLI

Verify the scripts in the installed skill directory. The examples below use the Codex standalone location. For Gemini, use `~/.gemini/nasa-ads-skill/plugins/nasa-ads/skills/nasa-ads`; for a marketplace plugin, ask the agent for the directory containing its loaded `SKILL.md`. Other installation paths follow [Locate the Installed Skill](library.md#locate-the-installed-skill). Set the variable to that actual path and use the same terminal for the checks below.

On macOS, Linux, or WSL:

```bash
nasa_ads_skill="$HOME/.agents/skills/nasa-ads"
python3 "$nasa_ads_skill/scripts/ads_api.py" --version
python3 "$nasa_ads_skill/scripts/fulltext.py" --version
python3 "$nasa_ads_skill/scripts/literature_db.py" --version
python3 "$nasa_ads_skill/scripts/adslib.py" --version
python3 "$nasa_ads_skill/scripts/ads_api.py" --no-store search \
  --query 'bibcode:2016PhRvL.116f1102A' \
  --fields bibcode,title,year \
  --rows 1
```

On Windows PowerShell:

```powershell
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
python "$nasaAdsSkill/scripts/ads_api.py" --version
python "$nasaAdsSkill/scripts/fulltext.py" --version
python "$nasaAdsSkill/scripts/literature_db.py" --version
python "$nasaAdsSkill/scripts/adslib.py" --version
python "$nasaAdsSkill/scripts/ads_api.py" --no-store search `
  --query 'bibcode:2016PhRvL.116f1102A' `
  --fields 'bibcode,title,year' `
  --rows 1
```

Use `py -3` in place of `python` when that is how Python is registered. All four version commands should report `1.14.1`. The JSON response should contain the bibcode `2016PhRvL.116f1102A`. The `--no-store` diagnostic preserves the current library contents.

### Full-text smoke test

This public arXiv paper has an official HTML version, so the smoke test needs no PDF helper. It also works without an ADS token when no token is present.

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/fulltext.py" fetch \
  arXiv:1901.04502 \
  --source arxiv --no-store
```

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/fulltext.py" fetch `
  'arXiv:1901.04502' `
  --source arxiv --no-store
```

The result should report `status: fulltext`, select `https://arxiv.org/html/1901.04502`, and provide existing `artifact_path`, `text_path`, and `manifest_path` files under the user cache. The script uses `https://arxiv.org/pdf/<id>` automatically when official HTML is unavailable. Pass the returned `text_path` to `fulltext.py outline <text_path>` to inspect the inferred article structure before summarizing it.

Use `--format pdf` when you explicitly need the PDF for equation, figure, table, pagination, or visual-reading checks; `--format html` requests only structured HTML. The default `--format auto` keeps the HTML-first fallback workflow.

### Literature-memory smoke test

The database CLI can verify its schema and digest contract without an ADS token. `template` prints JSON and does not create a library.

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" --version
python3 "$nasa_ads_skill/scripts/adslib.py" --version
python3 "$nasa_ads_skill/scripts/literature_db.py" template
```

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" --version
python "$nasaAdsSkill/scripts/adslib.py" --version
python "$nasaAdsSkill/scripts/literature_db.py" template
```

The CLI version command on either platform should report `1.14.1`. The schema-version-2 template should contain `overview`, `facets`, `findings`, `global_limitations`, and `reading.coverage`. Normal search, full-text fetch, and explicit library writes create or update the live library under `%LOCALAPPDATA%\nasa-ads\literature` on Windows or `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature` on macOS/Linux. Read commands return an empty result for a missing library and create no files. Set `NASA_ADS_LITERATURE_DIR` to choose another location.

### Direct HTTP fallback

Use this only when Python 3 cannot run the bundled CLI or an endpoint is not exposed by it. Follow the credential preflight, redirect rule, response checks, and platform-specific example in [`references/http-fallback.md`](../plugins/nasa-ads/skills/nasa-ads/references/http-fallback.md).

## Updating an Existing Install

Update the installation using the same method and source directory chosen during setup. If an existing database reports a schema mismatch, follow the [database upgrade procedure](library.md#upgrade-an-older-library).

For a Claude Code or Codex plugin, refresh the marketplace and installed plugin:

```bash
claude plugin marketplace update nasa-ads-community
claude plugin update nasa-ads@nasa-ads-community
```

```bash
codex plugin marketplace upgrade nasa-ads-community
codex plugin add nasa-ads@nasa-ads-community
```

For a standalone skill or Gemini CLI import, update the source path chosen during installation. The commands below use the paths shown in this guide.

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

After updating, run `adslib.py install` from the current installed directory and verify `adslib --version`.

Run `/memory reload` in Gemini CLI after updating. Start a new Codex or Claude Code session after updating those hosts.

After verification, [start a research task](../README.md#use-it) or [open the Web library](../README.md#open-the-web-library).
