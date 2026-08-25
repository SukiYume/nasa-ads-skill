from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleaseSyncTests(unittest.TestCase):
    def test_release_versions_are_identical(self):
        marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        claude_manifest = json.loads(
            (
                REPO_ROOT / "plugins" / "nasa-ads" / ".claude-plugin" / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        codex_manifest = json.loads(
            (
                REPO_ROOT / "plugins" / "nasa-ads" / ".codex-plugin" / "plugin.json"
            ).read_text(encoding="utf-8")
        )
        versions = {
            marketplace["metadata"]["version"],
            claude_manifest["version"],
            codex_manifest["version"],
        }
        self.assertEqual(len(versions), 1)
        version = versions.pop()
        for script_name in ("ads_api.py", "fulltext.py", "literature_db.py"):
            script = (
                REPO_ROOT
                / "plugins"
                / "nasa-ads"
                / "skills"
                / "nasa-ads"
                / "scripts"
                / script_name
            ).read_text(encoding="utf-8")
            match = re.search(r'^VERSION = "([^"]+)"$', script, re.MULTILINE)
            self.assertIsNotNone(match)
            assert match
            self.assertEqual(match.group(1), version)
        for readme_name in ("README.md", "README.zh-CN.md"):
            readme = (REPO_ROOT / readme_name).read_text(encoding="utf-8")
            self.assertIn(f"version-{version}-", readme)

    def test_fulltext_and_literature_memory_resources_are_packaged(self):
        plugin = REPO_ROOT / "plugins" / "nasa-ads"
        required = (
            plugin / "commands" / "ads-fulltext.md",
            plugin / "skills" / "nasa-ads" / "references" / "ads-cli.md",
            plugin / "skills" / "nasa-ads" / "scripts" / "fulltext.py",
            plugin / "skills" / "nasa-ads" / "references" / "fulltext.md",
            plugin / "commands" / "ads-memory.md",
            plugin / "skills" / "nasa-ads" / "scripts" / "literature_db.py",
            plugin / "skills" / "nasa-ads" / "references" / "literature-memory.md",
        )
        for path in required:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_readme_and_skill_have_distinct_audiences(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        skill = (
            REPO_ROOT / "plugins" / "nasa-ads" / "skills" / "nasa-ads" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for user_heading in (
            "## Overview",
            "## Install",
            "## Configure the ADS Token",
            "## Troubleshooting",
        ):
            self.assertIn(user_heading, readme)
            self.assertNotIn(user_heading, skill)
        for runtime_heading in (
            "## Core Rules",
            "## Task Routing",
            "## Literature Research",
            "### Digest Standard",
        ):
            self.assertIn(runtime_heading, skill)
        self.assertIn("references/ads-cli.md", skill)

    def test_bilingual_readmes_keep_the_same_heading_shape(self):
        heading_shapes = []
        for readme_name in ("README.md", "README.zh-CN.md"):
            lines = (REPO_ROOT / readme_name).read_text(encoding="utf-8").splitlines()
            heading_shapes.append(
                [
                    len(match.group(1))
                    for line in lines
                    if (match := re.match(r"^(#{2,3}) ", line))
                ]
            )
        self.assertEqual(heading_shapes[0], heading_shapes[1])

    def test_readme_relative_links_and_internal_anchors(self):
        for readme_name in ("README.md", "README.zh-CN.md"):
            readme_path = REPO_ROOT / readme_name
            text = readme_path.read_text(encoding="utf-8")
            anchors = {
                self.github_anchor(match.group(1))
                for line in text.splitlines()
                if (match := re.match(r"^#{1,6}\s+(.+?)\s*$", line))
            }
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                target = target.strip().strip("<>")
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                path_part, separator, fragment = target.partition("#")
                if not path_part:
                    with self.subTest(readme=readme_name, anchor=fragment):
                        self.assertIn(fragment, anchors)
                    continue
                with self.subTest(readme=readme_name, target=target):
                    self.assertTrue((readme_path.parent / path_part).exists())
                if separator and fragment and path_part == readme_name:
                    self.assertIn(fragment, anchors)

    def test_markdown_fences_are_balanced(self):
        for path in REPO_ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            fences = sum(
                1 for line in text.splitlines() if re.match(r"^\s*(?:```|~~~)", line)
            )
            with self.subTest(path=path):
                self.assertEqual(fences % 2, 0)

    @staticmethod
    def github_anchor(heading: str) -> str:
        heading = re.sub(r"<[^>]+>", "", heading).strip().lower()
        heading = heading.replace("`", "")
        heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
        heading = re.sub(r"\s+", "-", heading)
        return re.sub(r"-+", "-", heading).strip("-")


if __name__ == "__main__":
    unittest.main()
