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

    def test_all_routed_skill_resources_are_packaged(self):
        plugin = REPO_ROOT / "plugins" / "nasa-ads"
        skill = plugin / "skills" / "nasa-ads"
        required = (
            plugin / "commands" / "ads-fulltext.md",
            plugin / "commands" / "ads-memory.md",
            skill / "SKILL.md",
            skill / "agents" / "openai.yaml",
            skill / "scripts" / "ads_api.py",
            skill / "scripts" / "fulltext.py",
            skill / "scripts" / "literature_db.py",
            skill / "references" / "ads-cli.md",
            skill / "references" / "fulltext.md",
            skill / "references" / "literature-memory.md",
            skill / "references" / "digest-schema.md",
            skill / "references" / "libraries.md",
            skill / "references" / "http-fallback.md",
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
            "## Core Invariants",
            "## Task Routing",
            "## Literature Research",
            "## Failure Routing",
        ):
            self.assertIn(runtime_heading, skill)
        self.assertIn("references/ads-cli.md", skill)
        self.assertIn("references/digest-schema.md", skill)

    def test_standalone_install_checks_cover_every_routed_resource(self):
        required = (
            "SKILL.md",
            "agents/openai.yaml",
            "scripts/ads_api.py",
            "scripts/fulltext.py",
            "scripts/literature_db.py",
            "references/ads-cli.md",
            "references/fulltext.md",
            "references/literature-memory.md",
            "references/digest-schema.md",
            "references/libraries.md",
            "references/http-fallback.md",
        )
        for readme_name in ("README.md", "README.zh-CN.md"):
            text = (REPO_ROOT / readme_name).read_text(encoding="utf-8")
            prompt_blocks = re.findall(r"```text\n(.*?)\n```", text, re.DOTALL)
            self.assertTrue(prompt_blocks)
            install_prompt = prompt_blocks[0]
            for relative_path in required:
                with self.subTest(readme=readme_name, path=relative_path):
                    self.assertIn(relative_path, install_prompt)

    def test_persistent_memory_is_the_default_skill_behavior(self):
        skill_root = (
            REPO_ROOT / "plugins" / "nasa-ads" / "skills" / "nasa-ads"
        )
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        memory = (skill_root / "references" / "literature-memory.md").read_text(
            encoding="utf-8"
        )
        openai = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("Persistent literature memory is the default workflow.", skill)
        self.assertIn("Persistent storage is the default behavior", memory)
        self.assertIn("allow_implicit_invocation: true", openai)

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

    def test_skill_and_reference_relative_links_exist(self):
        skill_root = (
            REPO_ROOT / "plugins" / "nasa-ads" / "skills" / "nasa-ads"
        )
        markdown_files = [
            skill_root / "SKILL.md",
            *sorted((skill_root / "references").glob("*.md")),
        ]
        for markdown_file in markdown_files:
            text = markdown_file.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                target = target.strip().strip("<>")
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                path_part = target.partition("#")[0]
                if not path_part:
                    continue
                with self.subTest(file=markdown_file, target=target):
                    self.assertTrue((markdown_file.parent / path_part).exists())

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
