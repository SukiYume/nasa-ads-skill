# NASA ADS Doc Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove unsupported `custom` export guidance and align Claude command docs plus README wording with the ADS API behavior already documented in the skill.

**Architecture:** This repo is documentation-first, so the work is a consistency pass rather than runtime code changes. The plan updates the canonical ADS reference, the Claude command wrappers, and README summaries together so the same capability matrix is reflected across installation docs and slash-command guidance.

**Tech Stack:** Markdown, Claude plugin manifests, Codex plugin metadata

---

### Task 1: Remove unsupported custom export guidance

**Files:**
- Modify: `plugins/nasa-ads/commands/ads-bibtex.md`
- Modify: `plugins/nasa-ads/skills/nasa-ads/SKILL.md`
- Modify: `README.md`

**Step 1: Remove `custom` from supported format lists**

Update the exported-format lists so every documented format maps to a supported command path.

**Step 2: Remove custom-format-specific instructions**

Delete the note that describes the extra `format` payload for `/export/custom`, since the repo will no longer advertise that path.

**Step 3: Re-read export examples**

Confirm the remaining GET/POST examples still match the documented formats.

### Task 2: Bring `ads-library` command up to README and skill coverage

**Files:**
- Modify: `plugins/nasa-ads/commands/ads-library.md`

**Step 1: Extend the argument hint**

Add subcommands for metadata updates, deletion, query-based edits, set operations, and permissions.

**Step 2: Add minimal curl examples per subcommand**

Mirror the ADS endpoints already described in the skill so Claude slash-command users can invoke the same workflows.

**Step 3: Keep descriptions explicit about destructive actions**

Make `delete` clearly mean deleting the library itself, not just removing contents.

### Task 3: Fix README wording and maintenance guidance

**Files:**
- Modify: `README.md`

**Step 1: Correct endpoint semantics**

Rewrite the `/biblib/documents/<id>` row so POST, PUT, and DELETE are described accurately.

**Step 2: Remove contradictory source-of-truth wording**

Change the README so it no longer claims `SKILL.md` is the sole source of truth while also requiring manual sync across multiple files.

### Task 4: Verify packaging and review the diff

**Files:**
- Review: `README.md`
- Review: `plugins/nasa-ads/commands/ads-bibtex.md`
- Review: `plugins/nasa-ads/commands/ads-library.md`
- Review: `plugins/nasa-ads/skills/nasa-ads/SKILL.md`

**Step 1: Validate Claude marketplace metadata**

Run: `claude plugin validate .`
Expected: validation passes

**Step 2: Inspect the git diff**

Run: `git diff -- README.md plugins/nasa-ads/commands/ads-bibtex.md plugins/nasa-ads/commands/ads-library.md plugins/nasa-ads/skills/nasa-ads/SKILL.md docs/plans/2026-04-11-nasa-ads-doc-alignment.md`
Expected: only the intended documentation and command changes appear
