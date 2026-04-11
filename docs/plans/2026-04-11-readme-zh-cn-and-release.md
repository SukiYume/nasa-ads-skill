# Chinese README And Release Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Chinese README that mirrors the current installation and capability guidance, then verify, commit, and push the documentation updates.

**Architecture:** Keep `README.md` as the primary English document and add `README.zh-CN.md` as a parallel Chinese guide. Add language links between the two files so users can switch quickly, then verify the plugin metadata still validates before publishing.

**Tech Stack:** Markdown, git, Claude plugin manifests

---

### Task 1: Add the Chinese documentation entry point

**Files:**
- Modify: `README.md`
- Create: `README.zh-CN.md`

**Step 1: Add language links**

Add a short language switcher near the top of `README.md`, and include the reverse link at the top of `README.zh-CN.md`.

**Step 2: Translate the current README**

Create a Chinese README that covers repository purpose, ADS API wrapper positioning, one-line agent prompts, manual installation, usage, repository layout, endpoint coverage, and maintenance notes.

### Task 2: Verify the documentation state

**Files:**
- Review: `README.md`
- Review: `README.zh-CN.md`
- Review: `plugins/nasa-ads/.claude-plugin/plugin.json`

**Step 1: Validate plugin metadata**

Run: `claude plugin validate .`
Expected: validation passes

**Step 2: Inspect the diff**

Run: `git diff -- README.md README.zh-CN.md docs/plans/2026-04-11-readme-zh-cn-and-release.md`
Expected: only the new Chinese README, language links, and expected doc changes appear

### Task 3: Publish the changes

**Files:**
- Commit: repository root

**Step 1: Stage the documentation files**

Run: `git add README.md README.zh-CN.md plugins/nasa-ads/commands/ads-bibtex.md plugins/nasa-ads/commands/ads-library.md plugins/nasa-ads/skills/nasa-ads/SKILL.md docs/plans/2026-04-11-nasa-ads-doc-alignment.md docs/plans/2026-04-11-readme-zh-cn-and-release.md`

**Step 2: Commit**

Run: `git commit -m "docs: add Chinese README and refine install guidance"`

**Step 3: Push**

Run: `git push origin master`
