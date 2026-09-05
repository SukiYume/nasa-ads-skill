# Web and Personal Library Guide

[Back to README](../README.md#personal-literature-library) · [简体中文](library.zh-CN.md)

- [Locate the installed skill](#locate-the-installed-skill)
- [Start Web](#start-the-web-library)
- [Export citations](#export-citations)
- [Choose the data directory](#choose-the-data-directory)
- [Move to another computer](#move-to-a-new-computer)
- [Upgrade an older database](#upgrade-an-older-library)
- [Check library health](#check-library-health)

## Locate the Installed Skill

You can ask the agent to perform the tasks in this guide. It locates the scripts relative to its loaded `SKILL.md` and uses your selected library. Local browsing, cached citations, backup, and health checks work without an ADS token.

For manual commands, first choose the directory containing the installed `SKILL.md`. The examples below use the Codex standalone location.

Windows PowerShell:

```powershell
$nasaAdsSkill = Join-Path $HOME '.agents\skills\nasa-ads'
```

macOS, Linux, or WSL:

```bash
nasa_ads_skill="$HOME/.agents/skills/nasa-ads"
```

A Claude standalone installation uses `~/.claude/skills/nasa-ads`. A source checkout uses `<checkout>/plugins/nasa-ads/skills/nasa-ads`. Marketplace plugins use the actual directory reported by the agent. Set the variable to that directory and run the corresponding platform commands in the same terminal.

## Start the Web Library

Complete [one-time adslib registration](installation.md#register-the-adslib-command), then run this from any directory:

```bash
adslib
```

The command opens the browser and reuses an existing NASA ADS service for the same data directory, or starts a new service. Keep the terminal open for a new service; `Ctrl+C` stops it. A conflicting port gets an available alternative. Use `adslib --port 8766` for a preferred port or `adslib --library-dir "<directory>"` for another library. `--no-open` serves and prints the URL without launching a browser.

You can also run the installed launcher directly before registering the command:

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/adslib.py"
```

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/adslib.py"
```

The browser and service run on the same computer. The default address is [http://127.0.0.1:8765](http://127.0.0.1:8765); use the actual URL printed by the launcher. Run `adslib` again after restarting the computer. A fresh installation can show an empty library immediately without creating a database. Web uses bundled assets and the Python standard library. The existing `literature_db.py serve --port 8765` command remains available for manual service management.

Claude plugin users can invoke `/nasa-ads:ads-memory serve`. The agent resolves the installed plugin path. The [README](../README.md#open-the-web-library) also has complete Codex standalone commands that work from any directory.

| What you want to do | Page control |
| --- | --- |
| Find a scientific topic | Expand the topic tree; parent topics include their descendants |
| Find papers for a manuscript section | Combine a topic with a writing role such as methods or discussion |
| Search a particular evidence layer | Choose metadata, authored summaries, or stored full text |
| Apply a date range | Open years, enter the range, and click 应用年份; applied filters can be removed individually |
| Read detailed findings | Open a paper and switch between overview, scientific facets, citations, and article versions |
| Revisit the same result | Copy the article link; it preserves filters, page, paper, and detail tab on the same computer |
| Read with the keyboard | `/` focuses search; Escape closes the year control or reader; arrow keys switch focused detail tabs |
| See newly stored papers | Click refresh after the agent updates the same library |

The interface provides read-only browsing. Ask the agent to add summaries, classifications, topic descriptions, or notes. The library information button shows the active data directory. Citation downloads support checked papers and the full filtered result set, up to 2000 papers per whole-view export.

## Export Citations

> Export BibTeX for the papers in my selected topic, use cached official ADS entries where available, and save the bibliography as references.bib.

The Web citation tab shows each entry's source. Official ADS entries retain their exact citation keys. A paper without a cached official entry receives an entry generated from known local metadata, with a provenance label. Fetching official entries requires ADS credentials.

These examples write `references.bib` in the current working directory. Replace the topic with one present in your library.

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" citations --collection "FRB/Propagation" --output references.bib
python "$nasaAdsSkill/scripts/literature_db.py" citations --all --output personal-library.bib
python "$nasaAdsSkill/scripts/literature_db.py" citations "2016PhRvL.116f1102A" --fetch
```

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" citations --collection "FRB/Propagation" --output references.bib
python3 "$nasa_ads_skill/scripts/literature_db.py" citations --all --output personal-library.bib
python3 "$nasa_ads_skill/scripts/literature_db.py" citations "2016PhRvL.116f1102A" --fetch
```

The last command fetches and caches the official citation for a known local paper. Ask the agent to retrieve metadata for an article that is absent from the library. For RIS, AASTeX, MNRAS, or another supported remote format, ask for that format explicitly; the agent uses ADS citation export.

## Choose the Data Directory

| Setting | Location or effect |
| --- | --- |
| Windows default | `%LOCALAPPDATA%\nasa-ads\literature` |
| macOS / Linux / WSL default | `${XDG_DATA_HOME:-~/.local/share}/nasa-ads/literature` |
| `NASA_ADS_LITERATURE_DIR` | Selects the personal library for searches, storage, and Web browsing |
| `NASA_ADS_CACHE_DIR` | Selects the temporary full-text download cache |

The personal library contains `literature.sqlite3` and the managed `objects/` tree. Together they preserve bibliographic records, source summaries, exact articles, classifications, findings, and citations. Stored complete versions remain reusable after the download cache is cleared. Use the CLI's backup and restore operations when relocating the library so managed paths remain valid.

To use a custom library only for one server, put `--library-dir` before `serve`:

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" --library-dir "$HOME/nasa-ads-literature" serve --port 8765
```

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" --library-dir "$HOME/nasa-ads-literature" serve --port 8765
```

For ongoing use, set `NASA_ADS_LITERATURE_DIR` as described in the migration steps below. Use the same value in the agent and server environments. Restart an existing server after changing the directory.

## Move to a New Computer

> Back up my personal literature library and give me the complete backup directory to transfer; on the new computer, restore it into a new directory and make the agent and Web use that directory.

1. **On the original computer, create a backup.** The command reports a new backup directory containing the database snapshot, article objects, and `backup.json`.

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" backup
```

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" backup
```

2. **Transfer the entire reported directory.** Install the skill and Python on the new computer. The examples assume the transferred directory is `$HOME/nasa-ads-library-backup` and the new destination is `$HOME/nasa-ads-literature`. Choose a destination that does not yet exist.

3. **On the new computer, restore and select the library.** Set the installed-skill variable from the [first section](#locate-the-installed-skill) before running these commands.

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" restore "$HOME/nasa-ads-library-backup" --destination "$HOME/nasa-ads-literature"
$env:NASA_ADS_LITERATURE_DIR = "$HOME/nasa-ads-literature"
[Environment]::SetEnvironmentVariable('NASA_ADS_LITERATURE_DIR', $env:NASA_ADS_LITERATURE_DIR, 'User')
```

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" restore "$HOME/nasa-ads-library-backup" --destination "$HOME/nasa-ads-literature"
export NASA_ADS_LITERATURE_DIR="$HOME/nasa-ads-literature"
```

On macOS/Linux/WSL, add the `export` line to your shell startup file, such as `~/.zshrc` or `~/.bashrc`, to preserve the setting for future sessions. Start a new agent session after setting the persistent environment. Restoration validates the backup and updates stored file paths for the destination.

4. **Verify and open the restored library.** Run the [health checks](#check-library-health), then [start Web](#start-the-web-library). An older schema first needs the upgrade below. Compare the reported library directory and counts with the source backup.

## Upgrade an Older Library

The current database schema is 3; complete article digests use schema version 2. When an existing schema-1 or schema-2 library reports a mismatch, update the complete skill installation and run `init` explicitly. It creates a complete backup before migrating and reports that backup's location. A fresh missing library can be browsed directly.

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" init
python "$nasaAdsSkill/scripts/literature_db.py" audit
```

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" init
python3 "$nasa_ads_skill/scripts/literature_db.py" audit
```

Schema migration prepares the storage format. The agent assigns scientific categories by reading each paper's available summary and evidence. Ask it to organize an older unclassified library when that content work is needed.

## Check Library Health

Windows PowerShell:

```powershell
python "$nasaAdsSkill/scripts/literature_db.py" stats
python "$nasaAdsSkill/scripts/literature_db.py" check
python "$nasaAdsSkill/scripts/literature_db.py" audit
```

macOS, Linux, or WSL:

```bash
python3 "$nasa_ads_skill/scripts/literature_db.py" stats
python3 "$nasa_ads_skill/scripts/literature_db.py" check
python3 "$nasa_ads_skill/scripts/literature_db.py" audit
```

`stats` reports counts and the library location. `check` reports unfinished summaries and topic assignments; its exit code is 1 while that content work remains. `audit` checks database relationships and saved article integrity. A library can have healthy integrity and pending reading work at the same time.

If search misses expected text, choose the matching scope: metadata for titles and source abstracts, summary for authored reading and findings, or full text for the stored article. Chinese terms use substring matching. A phrase query searches a contiguous phrase; terms mode requires all terms. Requesting the latest publication or a changed article version can require a fresh source check.

The [agent library reference](../plugins/nasa-ads/skills/nasa-ads/references/literature-memory.md) contains the full command and evidence contract. The [Web audit](web-audit.md) records browser tests and screenshots.
