from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "nasa-ads" / "skills" / "nasa-ads" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "literature_db.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("nasa_ads_literature_db", SCRIPT_PATH)
assert SPEC and SPEC.loader
literature_db = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = literature_db
SPEC.loader.exec_module(literature_db)


def sample_digest(*, facets: list[dict] | None = None) -> dict:
    default_facets = [
        {
            "key": "activity-event-rate",
            "label": "活跃性与事件率",
            "aliases": ["activity", "burst rate", "event rate", "事件率"],
            "summary": "The source was highly active during the observing campaign.",
            "keywords": ["repeater", "rate"],
            "findings": [
                {
                    "statement": (
                        "The campaign detected 1076 bursts and reached 390 per hour."
                    ),
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.1", "figure": "1"},
                    "values": [
                        {"name": "burst count", "value": 1076, "unit": "bursts"},
                        {"name": "maximum rate", "value": 390, "unit": "hr^-1"},
                    ],
                    "keywords": ["burst count", "maximum event rate"],
                },
                {
                    "statement": "The activity varied strongly between sessions.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.1", "table": "1"},
                    "values": [],
                    "keywords": ["session variability"],
                },
            ],
            "methods": ["offline burst search"],
            "limitations": ["The measured rate depends on observing cadence."],
        },
        {
            "key": "circular-polarization",
            "label": "圆偏振属性",
            "aliases": ["circular polarization", "Stokes V", "圆偏振"],
            "summary": (
                "Many bursts showed strong and morphologically complex "
                "circular polarization."
            ),
            "keywords": ["polarimetry", "radiation mechanism"],
            "findings": [
                {
                    "statement": (
                        "Circular polarization can reverse sign across time "
                        "or frequency."
                    ),
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.3", "figure": "9"},
                    "values": [],
                    "keywords": ["sign reversal", "time-frequency morphology"],
                },
                {
                    "statement": "The high-quality RM sample remained near zero.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.3", "figure": "1"},
                    "values": [{"name": "mean RM", "value": -0.08, "unit": "rad m^-2"}],
                    "keywords": ["rotation measure"],
                },
            ],
            "methods": ["polarization calibration", "RM synthesis"],
            "limitations": ["The physical origin is not uniquely determined."],
        },
    ]
    chosen_facets = facets if facets is not None else default_facets
    sections = ["1", "2", "3.1", "3.2", "3.3", "4", "5"]
    facet_keys = [facet["key"] for facet in chosen_facets]
    coverage = [
        {
            "section": section,
            "role": "scientific" if section in {"3.1", "3.3"} else "context",
            "facet_keys": (
                facet_keys
                if section in {"3.1", "3.3"}
                else []
            ),
            "notes": (
                ""
                if section in {"3.1", "3.3"}
                else "This section supplies context, methods, or synthesis."
            ),
        }
        for section in sections
    ]
    return {
        "schema_version": literature_db.DIGEST_SCHEMA_VERSION,
        "language": "zh-CN",
        "overview": {
            "summary": (
                "FAST measured burst statistics and polarization for FRB 20220912A."
            ),
            "significance": (
                "The paper connects source activity, spectra, and polarization."
            ),
            "questions": [
                "What controls repeater activity?",
                "What do the polarization measurements imply?",
            ],
        },
        "keywords": ["fast radio burst", "FAST", "FRB 20220912A"],
        "entities": [
            {
                "name": "FRB 20220912A",
                "type": "repeating FRB",
                "description": "An active localized repeater.",
                "aliases": ["FRB20220912A"],
            }
        ],
        "datasets": [
            {
                "name": "FAST 2022 campaign",
                "description": "Seventeen L-band observations.",
                "instrument": "FAST",
                "sample": "1076 bursts",
                "time_span": "2022 October-December",
                "frequency": "1-1.5 GHz",
                "identifiers": ["ScienceDB 10.57760/sciencedb.08058"],
            }
        ],
        "methods": [
            {
                "name": "burst search",
                "description": "A classifier cross-checked with PRESTO.",
                "purpose": "Detect individual bursts.",
                "keywords": ["PRESTO", "classification"],
            }
        ],
        "facets": chosen_facets,
        "global_limitations": ["The observations cover only the FAST L band."],
        "data_products": [
            {
                "name": "Burst property table",
                "type": "table",
                "url": "https://doi.org/10.57760/sciencedb.08058",
                "availability": "Machine-readable table",
                "locator": "Table 1",
            }
        ],
        "reading": {
            "status": "full",
            "sections": sections,
            "page_ranges": [],
            "visual_page_ranges": [],
            "unread_sections": [],
            "notes": "Publisher HTML was read in full.",
            "coverage": coverage,
        },
    }


def sample_manifest(
    root: Path,
    *,
    body: bytes = b"<html>article one</html>",
    text_body: str = (
        "This full article contains a unique micropulse avalanche discussion.\n"
        "It also reports waiting times, spectral bandwidth, and polarization."
    ),
) -> dict:
    artifact = root / "publisher.html"
    text = root / "publisher.txt"
    artifact.write_bytes(body)
    text.write_text(text_body, encoding="utf-8")
    artifact_hash = hashlib.sha256(body).hexdigest()
    return {
        "schema_version": 1,
        "tool_version": "1.12.0",
        "status": "fulltext",
        "created_at": "2026-08-25T00:00:00Z",
        "input": "2023ApJ...955..142Z",
        "input_type": "bibcode",
        "normalized_identifier": "2023ApJ...955..142Z",
        "bibcode": "2023ApJ...955..142Z",
        "title": "FAST Observations of FRB 20220912A",
        "author": ["Zhang, Y. K.", "Li, D."],
        "abstract": "FAST detected many bursts and measured their polarization.",
        "doi": ["10.3847/1538-4357/aced0b", "10.48550/arXiv.2304.14665"],
        "arxiv_ids": ["2304.14665"],
        "property": ["REFEREED", "OPENACCESS"],
        "doctype": "article",
        "year": "2023",
        "pub": "The Astrophysical Journal",
        "citation_count": 122,
        "read_count": 266,
        "selected": {
            "candidate": {
                "source": "publisher",
                "version": "published",
                "format": "html",
            },
            "actual_format": "html",
            "final_url": "https://example.org/article",
            "artifact_path": str(artifact),
            "text_path": str(text),
            "sha256": artifact_hash,
            "retrieved_at": "2026-08-25T00:00:00Z",
            "status": "fulltext",
            "statistics": {"words": 7000, "pages": None},
        },
        "warnings": [],
    }


class DigestValidationTests(unittest.TestCase):
    def test_rich_digest_is_valid(self):
        digest = literature_db.validate_digest(sample_digest())
        self.assertEqual(len(digest["facets"]), 2)
        self.assertEqual(digest["reading"]["status"], "full")

    def test_facet_requires_atomic_findings_and_locator(self):
        digest = sample_digest()
        digest["facets"][0]["findings"] = []
        with self.assertRaises(literature_db.LiteratureError):
            literature_db.validate_digest(digest)

    def test_unknown_nested_fields_are_rejected(self):
        digest = sample_digest()
        digest["facets"][0]["sumary"] = "misspelled summary"
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "unsupported fields: sumary"
        ):
            literature_db.validate_digest(digest)

    def test_equation_locator_is_accepted(self):
        digest = sample_digest()
        digest["facets"][0]["findings"][0]["locator"] = {
            "section": "Methods",
            "equation": "Equation 7",
        }

        validated = literature_db.validate_digest(digest)

        self.assertEqual(
            validated["facets"][0]["findings"][0]["locator"]["equation"],
            "Equation 7",
        )

    def test_scientific_latex_math_environment_is_accepted(self):
        digest = sample_digest()
        digest["facets"][0]["findings"][0]["statement"] = (
            r"The fitted relation is represented by \begin{aligned} y=ax+b \end{aligned}."
        )
        validated = literature_db.validate_digest(digest)
        self.assertIn(
            r"\begin{aligned}",
            validated["facets"][0]["findings"][0]["statement"],
        )

    def test_full_reading_requires_a_research_question(self):
        digest = sample_digest()
        digest["overview"]["questions"] = []
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "at least one research question"
        ):
            literature_db.validate_digest(digest)

    def test_complete_narrow_digest_is_valid(self):
        digest = sample_digest(facets=[sample_digest()["facets"][0]])
        digest["facets"][0]["findings"] = digest["facets"][0]["findings"][:1]
        digest["overview"]["questions"] = digest["overview"]["questions"][:1]
        digest["global_limitations"] = []

        validated = literature_db.validate_digest(digest)

        self.assertEqual(len(validated["overview"]["questions"]), 1)
        self.assertEqual(len(validated["facets"]), 1)
        self.assertEqual(len(validated["facets"][0]["findings"]), 1)
        self.assertEqual(validated["global_limitations"], [])

    def test_schema2_requires_section_coverage_for_every_read_section(self):
        digest = sample_digest()
        digest["reading"]["coverage"] = digest["reading"]["coverage"][:-1]
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "map digest.reading.sections exactly"
        ):
            literature_db.validate_digest(digest)

    def test_scientific_section_requires_a_facet_mapping(self):
        digest = sample_digest()
        digest["reading"]["coverage"][0].update(
            {"role": "scientific", "facet_keys": []}
        )
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "scientific section without a facet"
        ):
            literature_db.validate_digest(digest)

    def test_non_scientific_section_rejects_facet_mappings(self):
        digest = sample_digest()
        digest["reading"]["coverage"][0]["facet_keys"] = [
            digest["facets"][0]["key"]
        ]
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "Only scientific sections"
        ):
            literature_db.validate_digest(digest)

    def test_complete_schema2_digest_rejects_unread_sections(self):
        digest = sample_digest()
        digest["reading"]["unread_sections"] = ["Appendix A"]
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "cannot list unread sections"
        ):
            literature_db.validate_digest(digest)

    def test_legacy_digest_is_rejected(self):
        digest = sample_digest()
        digest["schema_version"] = 1
        digest["reading"].pop("coverage")
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "schema_version must be 2"
        ):
            literature_db.validate_digest(digest)

    def test_facets_are_domain_agnostic_and_not_a_fixed_ontology(self):
        digest = sample_digest(
            facets=[
                {
                    "key": "simulation-convergence",
                    "label": "Numerical convergence",
                    "aliases": ["resolution convergence", "收敛性"],
                    "summary": (
                        "The inferred structure is stable above the stated resolution."
                    ),
                    "keywords": ["simulation", "resolution study"],
                    "findings": [
                        {
                            "statement": (
                                "The target observable changes by less than "
                                "3% between the two highest-resolution runs."
                            ),
                            "kind": "constraint",
                            "confidence": "high",
                            "locator": {"section": "4.2", "table": "3"},
                            "values": [
                                {
                                    "name": "relative change",
                                    "value": 3,
                                    "unit": "%",
                                    "qualifier": "upper bound",
                                }
                            ],
                            "keywords": ["convergence test", "numerical resolution"],
                        }
                    ],
                    "methods": ["resolution study"],
                    "limitations": ["Only three resolution levels were tested."],
                },
                {
                    "key": "observable-predictions",
                    "label": "Observable predictions",
                    "aliases": ["testable predictions", "观测预言"],
                    "summary": "The model predicts a separately testable signature.",
                    "keywords": ["theory", "future test"],
                    "findings": [
                        {
                            "statement": (
                                "The signature should appear only inside the "
                                "specified parameter regime."
                            ),
                            "kind": "interpretation",
                            "confidence": "medium",
                            "locator": {"section": "5"},
                            "values": [],
                            "keywords": ["parameter regime", "prediction"],
                        }
                    ],
                    "methods": ["analytic model"],
                    "limitations": ["The prediction depends on the model assumptions."],
                },
            ]
        )
        digest["overview"] = {
            "summary": (
                "A numerical and analytic study of an arbitrary physical system."
            ),
            "significance": (
                "It tests convergence and derives an observable prediction."
            ),
            "questions": ["Are the results converged?", "How can the model be tested?"],
        }
        digest["keywords"] = ["numerical simulation", "analytic theory"]
        digest["entities"] = []
        digest["datasets"] = []
        digest["methods"] = [
            {
                "name": "resolution study",
                "description": "Three numerical resolutions were compared.",
                "purpose": "Separate numerical artifacts from stable behavior.",
                "keywords": ["convergence"],
            }
        ]
        digest["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Other scientific dimensions"],
            }
        )
        validated = literature_db.validate_digest(digest)
        self.assertEqual(
            [facet["key"] for facet in validated["facets"]],
            ["simulation-convergence", "observable-predictions"],
        )

        digest = sample_digest()
        digest["facets"][0]["findings"][0]["locator"] = {}
        with self.assertRaises(literature_db.LiteratureError):
            literature_db.validate_digest(digest)

    def test_template_is_intentionally_incomplete(self):
        template = literature_db.digest_template()
        self.assertEqual(
            template["schema_version"], literature_db.DIGEST_SCHEMA_VERSION
        )
        with self.assertRaises(literature_db.LiteratureError):
            literature_db.validate_digest(template)


class LibraryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.source = self.root / "source"
        self.source.mkdir()
        self.connection, self.fts5 = literature_db.connect_library(self.library)

    def tearDown(self):
        self.connection.close()
        self.temporary.cleanup()

    def ingest(
        self,
        *,
        manifest: dict | None = None,
        digest: dict | None = None,
        merge=False,
        replace_digest=False,
    ):
        chosen_manifest = manifest or sample_manifest(self.source)
        chosen_digest = digest or sample_digest()
        return literature_db.ingest_record(
            self.connection,
            self.fts5,
            self.library,
            chosen_manifest,
            chosen_digest,
            merge=merge,
            replace_digest=replace_digest,
        )

    def downgrade_digest_table_to_schema_1(self) -> int:
        current = self.connection.execute("SELECT * FROM digests").fetchone()
        assert current is not None
        current_id = int(current["id"])
        self.connection.commit()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        self.connection.execute("BEGIN IMMEDIATE")
        self.connection.execute(
            """
            CREATE TABLE digests_v1 (
                id INTEGER PRIMARY KEY,
                version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL,
                schema_version INTEGER NOT NULL,
                language TEXT NOT NULL,
                overview TEXT NOT NULL,
                significance TEXT NOT NULL,
                reading_status TEXT NOT NULL,
                digest_hash TEXT NOT NULL,
                digest_json TEXT NOT NULL,
                is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1)),
                created_at TEXT NOT NULL,
                UNIQUE(version_id, revision)
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO digests_v1(
                id, version_id, revision, schema_version, language, overview,
                significance, reading_status, digest_hash, digest_json,
                is_current, created_at
            )
            SELECT id, version_id, 2, schema_version, language, overview,
                   significance, reading_status, digest_hash, digest_json,
                   1, created_at
            FROM digests
            """
        )
        self.connection.execute(
            """
            INSERT INTO digests_v1(
                id, version_id, revision, schema_version, language, overview,
                significance, reading_status, digest_hash, digest_json,
                is_current, created_at
            )
            SELECT id + 1000, version_id, 1, schema_version, language, overview,
                   significance, reading_status, digest_hash || '-historical',
                   digest_json, 0, created_at
            FROM digests
            """
        )
        self.connection.execute("DROP TABLE digests")
        self.connection.execute("ALTER TABLE digests_v1 RENAME TO digests")
        self.connection.execute(
            "CREATE UNIQUE INDEX digests_one_current_idx "
            "ON digests(version_id) WHERE is_current = 1"
        )
        self.connection.execute("PRAGMA user_version = 1")
        self.connection.commit()
        self.connection.execute("PRAGMA foreign_keys = ON")
        return current_id

    def test_fresh_database_physically_enforces_one_digest_per_version(self):
        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(digests)")
        }
        self.assertEqual(
            self.connection.execute("PRAGMA user_version").fetchone()[0],
            literature_db.DATABASE_SCHEMA_VERSION,
        )
        self.assertNotIn("revision", columns)
        self.assertNotIn("is_current", columns)
        result = self.ingest()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO digests(
                    version_id, schema_version, language, overview, significance,
                    reading_status, digest_hash, digest_json, created_at
                )
                SELECT version_id, schema_version, language, overview, significance,
                       reading_status, digest_hash || '-duplicate', digest_json,
                       created_at
                FROM digests WHERE id = ?
                """,
                (result["digest_id"],),
            )
        self.connection.rollback()

    def test_schema_1_migration_removes_digest_history(self):
        self.ingest()
        current_id = self.downgrade_digest_table_to_schema_1()
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM digests").fetchone()[0],
            2,
        )
        self.connection.close()

        self.connection, self.fts5 = literature_db.connect_library(self.library)

        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(digests)")
        }
        self.assertEqual(
            self.connection.execute("PRAGMA user_version").fetchone()[0],
            literature_db.DATABASE_SCHEMA_VERSION,
        )
        self.assertNotIn("revision", columns)
        self.assertNotIn("is_current", columns)
        rows = self.connection.execute("SELECT id FROM digests").fetchall()
        self.assertEqual([int(row["id"]) for row in rows], [current_id])
        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=True
        )
        self.assertEqual(audit["errors"], [])
        self.assertEqual(audit["counts"]["digests"], 1)
        self.assertNotIn(
            "digests_with_history_markers", audit["database"]["relations"]
        )

    def test_read_command_does_not_migrate_schema_1(self):
        self.ingest()
        self.downgrade_digest_table_to_schema_1()
        self.connection.close()
        stderr = io.StringIO()

        code = literature_db.run(
            [
                "--library-dir",
                str(self.library),
                "lookup",
                "2023ApJ...955..142Z",
            ],
            stderr=stderr,
        )

        self.assertEqual(code, 2)
        self.assertIn("backup", stderr.getvalue().casefold())
        self.assertIn("init", stderr.getvalue().casefold())
        self.connection = sqlite3.connect(self.library / "literature.sqlite3")
        self.connection.row_factory = sqlite3.Row
        self.assertEqual(self.connection.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM digests").fetchone()[0],
            2,
        )

    def test_ingest_copies_fulltext_and_resolves_all_aliases(self):
        result = self.ingest()
        self.assertEqual(result["status"], "ingested")
        self.assertTrue(Path(result["object_paths"]["artifact"]).is_file())
        self.assertTrue(Path(result["object_paths"]["text"]).is_file())
        for identifier in (
            "2023ApJ...955..142Z",
            "10.3847/1538-4357/aced0b",
            "arXiv:2304.14665v3",
        ):
            lookup = literature_db.lookup_one(
                self.connection,
                identifier,
                topics=[],
                artifact_hash=None,
                include_digest=False,
            )
            self.assertTrue(lookup["found"])
            self.assertEqual(lookup["reuse_status"], "reusable")
            self.assertEqual(lookup["open_gate_action"], "reuse_complete_record")
            self.assertFalse(lookup["complete_ingest_required"])

    def test_lookup_exposes_per_article_open_gate(self):
        missing = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["one requested figure"],
            artifact_hash=None,
            include_digest=False,
        )
        self.assertEqual(missing["reuse_status"], "not_found")
        self.assertEqual(missing["open_gate_action"], "complete_ingest")
        self.assertTrue(missing["complete_ingest_required"])

        self.ingest()
        uncovered = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["energy distribution"],
            artifact_hash=None,
            include_digest=False,
        )
        self.assertEqual(uncovered["reuse_status"], "targeted_reading")
        self.assertEqual(uncovered["open_gate_action"], "targeted_merge")
        self.assertFalse(uncovered["complete_ingest_required"])

    def test_visual_ingest_keeps_raw_artifact_content_identity(self):
        manifest = sample_manifest(self.source)
        artifact = Path(manifest["selected"]["artifact_path"])
        artifact.write_bytes(b"%PDF-1.7\nscanned pages")
        artifact_hash = literature_db.fulltext.sha256_file(artifact)
        manifest["status"] = "needs_visual_reading"
        manifest["selected"].update(
            {
                "candidate": {
                    "source": "ads",
                    "version": "scan",
                    "format": "pdf",
                },
                "actual_format": "pdf",
                "sha256": artifact_hash,
                "content_sha256": artifact_hash,
                "status": "needs_visual_reading",
                "statistics": {"words": 2, "pages": 12},
            }
        )
        digest = sample_digest()
        digest["reading"].update(
            {
                "status": "visual",
                "sections": ["Pages 1-12 scientific content"],
                "visual_page_ranges": ["1-12"],
                "notes": "All twelve rendered pages were inspected.",
                "coverage": [
                    {
                        "section": "Pages 1-12 scientific content",
                        "role": "scientific",
                        "facet_keys": [
                            facet["key"] for facet in digest["facets"]
                        ],
                        "notes": "",
                    }
                ],
            }
        )

        result = self.ingest(manifest=manifest, digest=digest)

        self.assertEqual(result["content_sha256"], artifact_hash)
        version = literature_db.preferred_version(
            self.connection, int(result["paper_id"])
        )
        self.assertIsNotNone(version)
        self.assertEqual(version["content_sha256"], artifact_hash)
        self.assertEqual(version["reading_status"], "visual")
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=True,
        )
        self.assertEqual(audit["errors"], [])

    def test_new_paper_rejects_targeted_first_ingest(self):
        digest = sample_digest()
        digest["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Sections unrelated to the current claim"],
            }
        )
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "exact article version"
        ):
            self.ingest(digest=digest)
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["papers"], 0)
        self.assertEqual(list((self.library / "objects").rglob("*")), [])

    def test_targeted_ingest_rejects_paper_without_complete_digest(self):
        manifest = sample_manifest(self.source)
        targeted = sample_digest()
        targeted["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Remaining article sections"],
            }
        )
        targeted = literature_db.validate_digest(targeted)
        literature_db.validate_ingest_manifest(manifest, targeted)
        stored = literature_db.store_objects(self.library, manifest)
        aliases = literature_db.aliases_from_manifest(manifest)
        self.connection.execute("BEGIN IMMEDIATE")
        paper_id = literature_db.upsert_paper(self.connection, manifest, aliases)
        version_id, _created = literature_db.upsert_version(
            self.connection, paper_id, manifest, stored
        )
        literature_db.insert_digest(self.connection, version_id, targeted)
        self.connection.commit()

        lookup = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["event rate"],
            artifact_hash=None,
            include_digest=False,
        )
        self.assertEqual(lookup["reuse_status"], "needs_reading")
        self.assertEqual(lookup["open_gate_action"], "complete_ingest")
        self.assertTrue(lookup["complete_ingest_required"])

        with self.assertRaisesRegex(
            literature_db.LiteratureError, "exact article version"
        ):
            self.ingest(manifest=manifest, digest=targeted, merge=True)

    def test_ingest_accepts_narrow_complete_digest_with_full_coverage(self):
        digest = sample_digest(facets=[sample_digest()["facets"][0]])
        digest["facets"][0]["findings"] = digest["facets"][0]["findings"][:1]
        digest["overview"]["questions"] = digest["overview"]["questions"][:1]
        digest["global_limitations"] = []

        result = self.ingest(digest=digest)

        self.assertEqual(result["status"], "ingested")
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["papers"], 1)

    def test_missing_title_is_rejected_before_object_copy(self):
        manifest = sample_manifest(self.source)
        manifest["title"] = ""
        with self.assertRaisesRegex(literature_db.LiteratureError, "manifest.title"):
            self.ingest(manifest=manifest)
        self.assertEqual(list((self.library / "objects").rglob("*")), [])

    def test_existing_arxiv_record_can_receive_ads_metadata(self):
        initial = sample_manifest(self.source)
        initial.update(
            {
                "input": "arXiv:2304.14665",
                "input_type": "arxiv",
                "normalized_identifier": "2304.14665",
                "bibcode": None,
                "author": [],
                "abstract": None,
                "year": None,
                "pub": None,
            }
        )
        result = self.ingest(manifest=initial)
        stored_before = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        enriched_manifest = sample_manifest(self.source)
        enriched_manifest["doi"] = ["10.5555/new-metadata-record"]
        enriched = literature_db.enrich_paper_metadata(
            self.connection, self.fts5, enriched_manifest
        )
        stored_after = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        self.assertEqual(enriched["paper_id"], result["paper_id"])
        self.assertEqual(enriched["bibcode"], "2023ApJ...955..142Z")
        self.assertEqual(enriched["authors"], 2)
        self.assertTrue(enriched["abstract"])
        self.assertEqual(stored_after, stored_before)
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertIn("10.3847/1538-4357/aced0b", shown["paper"]["metadata"]["doi"])
        self.assertIn("10.5555/new-metadata-record", shown["paper"]["metadata"]["doi"])
        preserved = literature_db.enrich_paper_metadata(
            self.connection, self.fts5, initial
        )
        self.assertEqual(preserved["bibcode"], "2023ApJ...955..142Z")
        self.assertEqual(preserved["authors"], 2)
        self.assertTrue(preserved["abstract"])
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertIn("10.5555/new-metadata-record", shown["paper"]["metadata"]["doi"])

    def test_enrich_preserves_existing_nonempty_metadata(self):
        original = sample_manifest(self.source)
        self.ingest(manifest=original)
        conflict_root = self.root / "conflicting-metadata"
        conflict_root.mkdir()
        incoming = sample_manifest(conflict_root)
        incoming.update(
            {
                "title": "Conflicting replacement title",
                "author": ["Replacement, A."],
                "abstract": "Conflicting replacement abstract.",
                "year": "2025",
                "pub": "Replacement Journal",
                "doctype": "replacement",
                "doi": ["10.5555/new-metadata-record"],
            }
        )

        literature_db.enrich_paper_metadata(self.connection, self.fts5, incoming)
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )

        self.assertEqual(shown["paper"]["title"], original["title"])
        self.assertEqual(shown["paper"]["authors"], original["author"])
        self.assertEqual(shown["paper"]["abstract"], original["abstract"])
        self.assertEqual(shown["paper"]["year"], int(original["year"]))
        self.assertEqual(shown["paper"]["pub"], original["pub"])
        self.assertEqual(shown["paper"]["doctype"], original["doctype"])
        self.assertIn("10.5555/new-metadata-record", shown["paper"]["metadata"]["doi"])

    def test_new_article_rejects_schema1_digest_before_object_copy(self):
        digest = sample_digest()
        digest["schema_version"] = 1
        digest["reading"].pop("coverage")
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "schema_version must be 2"
        ):
            self.ingest(digest=digest)
        self.assertEqual(list((self.library / "objects").rglob("*")), [])

    def test_long_narrow_article_uses_structural_coverage(self):
        manifest = sample_manifest(
            self.source,
            text_body="word " * 12000,
        )
        digest = sample_digest(facets=[sample_digest()["facets"][0]])
        digest["facets"][0]["findings"] = digest["facets"][0]["findings"][:1]
        digest["overview"]["questions"] = digest["overview"]["questions"][:1]
        digest["global_limitations"] = []

        result = self.ingest(manifest=manifest, digest=digest)

        self.assertEqual(result["status"], "ingested")

    def test_fresh_arxiv_record_without_ads_bibcode_is_informational(self):
        manifest = sample_manifest(self.source)
        manifest.update(
            {
                "input": "arXiv:2608.31161",
                "input_type": "arxiv",
                "normalized_identifier": "2608.31161",
                "bibcode": None,
                "doi": [],
                "arxiv_ids": ["2608.31161"],
            }
        )
        self.ingest(manifest=manifest)
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=False,
        )
        warning_kinds = {item["kind"] for item in audit["warnings"]}
        self.assertNotIn("incomplete_metadata", warning_kinds)
        self.assertEqual(
            audit["information"]["arxiv_records_awaiting_ads_bibcode"],
            ["arxiv:2608.31161"],
        )

    def test_record_text_order_is_deterministic(self):
        first = {"z": "last", "a": "first", "nested": {"b": "two", "a": "one"}}
        second = {"nested": {"a": "one", "b": "two"}, "a": "first", "z": "last"}
        self.assertEqual(
            literature_db.join_record_text([first]),
            literature_db.join_record_text([second]),
        )

    def test_backup_is_consistent_and_audit_reports_quality(self):
        self.ingest()
        destination = self.root / "backup"
        result = literature_db.create_library_backup(
            self.connection, self.fts5, self.library, str(destination)
        )
        self.assertEqual(result["status"], "created")
        self.assertTrue((destination / "literature.sqlite3").is_file())
        self.assertTrue((destination / "backup.json").is_file())
        backup_manifest = json.loads(
            (destination / "backup.json").read_text(encoding="utf-8")
        )
        self.assertEqual(backup_manifest["backup_schema_version"], 1)
        self.assertEqual(
            backup_manifest["database_schema_version"],
            literature_db.DATABASE_SCHEMA_VERSION,
        )
        backup_connection = sqlite3.connect(destination / "literature.sqlite3")
        try:
            self.assertEqual(
                backup_connection.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            self.assertEqual(
                backup_connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
                1,
            )
        finally:
            backup_connection.close()
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=True,
        )
        self.assertEqual(audit["errors"], [])
        self.assertEqual(audit["warnings"], [])

    def test_audit_requires_text_path_for_fulltext_versions(self):
        self.ingest()
        self.connection.execute("UPDATE versions SET text_path = NULL")
        self.connection.commit()
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=False,
        )
        integrity = next(
            item for item in audit["errors"] if item["kind"] == "object_integrity"
        )
        self.assertIn(
            "missing_text_path",
            {item["kind"] for item in integrity["items"]},
        )

    def test_invalid_digest_does_not_make_its_objects_look_orphaned(self):
        result = self.ingest()
        row = self.connection.execute(
            "SELECT digest_json FROM digests WHERE id = ?", (result["digest_id"],)
        ).fetchone()
        digest = json.loads(row["digest_json"])
        digest["reading"]["unread_sections"] = ["Appendix A"]
        self.connection.execute(
            "UPDATE digests SET digest_json = ? WHERE id = ?",
            (literature_db.json_text(digest), result["digest_id"]),
        )
        self.connection.commit()

        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )

        self.assertIn(
            "invalid_digests", {item["kind"] for item in audit["errors"]}
        )
        self.assertNotIn(
            "orphan_object_directories",
            {item["kind"] for item in audit["warnings"]},
        )

    def test_topic_coverage_controls_reuse(self):
        self.ingest()
        covered = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["event rate", "圆偏振"],
            artifact_hash=None,
            include_digest=True,
        )
        self.assertEqual(covered["reuse_status"], "reusable")
        self.assertEqual(len(covered["matched_topics"]), 2)
        self.assertIn("digest", covered)
        self.assertEqual(covered["digest_schema_version"], 2)
        self.assertNotIn("coverage_upgrade_recommended", covered)

    def test_audit_rejects_schema1_digest(self):
        result = self.ingest()
        row = self.connection.execute(
            "SELECT digest_json FROM digests WHERE id = ?", (result["digest_id"],)
        ).fetchone()
        digest = json.loads(row["digest_json"])
        digest["schema_version"] = 1
        digest["reading"].pop("coverage")
        self.connection.execute(
            "UPDATE digests SET schema_version = 1, digest_json = ? WHERE id = ?",
            (literature_db.json_text(digest), result["digest_id"]),
        )
        self.connection.commit()

        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )
        self.assertIn(
            "invalid_digests", {item["kind"] for item in audit["errors"]}
        )
        self.assertFalse(literature_db.topic_match(sample_digest()["facets"][0], ""))

    def test_audit_rejects_incomplete_stored_reading(self):
        result = self.ingest()
        row = self.connection.execute(
            "SELECT digest_json FROM digests WHERE id = ?", (result["digest_id"],)
        ).fetchone()
        digest = json.loads(row["digest_json"])
        digest["reading"].update(
            {"status": "targeted", "unread_sections": ["Remaining sections"]}
        )
        digest = literature_db.validate_digest(digest)
        self.connection.execute(
            "UPDATE digests SET reading_status = 'targeted', digest_json = ? WHERE id = ?",
            (literature_db.json_text(digest), result["digest_id"]),
        )
        self.connection.commit()

        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )

        self.assertIn(
            "incomplete_reading_digests",
            {item["kind"] for item in audit["errors"]},
        )

    def test_search_covers_summary_metadata_and_fulltext(self):
        self.ingest()
        summary = literature_db.search_library(
            self.connection,
            self.fts5,
            "circular polarization",
            scope="summary",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(summary["count"], 1)
        self.assertEqual(
            summary["results"][0]["matched_facets"][0]["key"],
            "circular-polarization",
        )
        self.assertEqual(
            summary["results"][0]["matched_facets"][0]["findings"][0]["kind"],
            "measurement",
        )

        metadata = literature_db.search_library(
            self.connection,
            self.fts5,
            "FAST 20220912A",
            scope="metadata",
            mode="terms",
            topics=[],
            year_from=2023,
            year_to=2023,
            limit=10,
        )
        self.assertEqual(metadata["count"], 1)

        article = literature_db.search_library(
            self.connection,
            self.fts5,
            "micropulse avalanche",
            scope="fulltext",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(article["count"], 1)

        chinese = literature_db.search_library(
            self.connection,
            self.fts5,
            "圆偏振 属性",
            scope="summary",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(chinese["count"], 1)
        self.assertEqual(chinese["search_engine"], "substring")

        cross_facet = literature_db.search_library(
            self.connection,
            self.fts5,
            "event reversal",
            scope="summary",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(cross_facet["count"], 1)
        matched_keys = {
            facet["key"] for facet in cross_facet["results"][0]["matched_facets"]
        }
        self.assertEqual(
            matched_keys,
            {"activity-event-rate", "circular-polarization"},
        )

    def test_topic_filter_is_independent_of_free_text_query(self):
        self.ingest()
        result = literature_db.search_library(
            self.connection,
            self.fts5,
            "FAST",
            scope="all",
            mode="terms",
            topics=["Stokes V"],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(result["count"], 1)

        absent = literature_db.search_library(
            self.connection,
            self.fts5,
            "FAST",
            scope="all",
            mode="terms",
            topics=["gravitational lensing"],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(absent["count"], 0)

    def test_topic_filter_scans_past_early_nonmatching_candidates(self):
        for index in range(6):
            manifest = sample_manifest(
                self.source,
                body=f"<html>commonterm paper {index}</html>".encode(),
                text_body=f"commonterm scientific content for paper {index}",
            )
            bibcode = f"2026TEST{index:011d}A"
            manifest.update(
                {
                    "input": bibcode,
                    "normalized_identifier": bibcode,
                    "bibcode": bibcode,
                    "title": f"Commonterm paper {index}",
                    "doi": [f"10.5555/commonterm.{index}"],
                    "arxiv_ids": [],
                }
            )
            digest = sample_digest()
            if index == 5:
                digest["facets"][0]["aliases"].append("late-topic")
            self.ingest(manifest=manifest, digest=digest)

        result = literature_db.search_library(
            self.connection,
            False,
            "commonterm",
            scope="all",
            mode="terms",
            topics=["late-topic"],
            year_from=None,
            year_to=None,
            limit=1,
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["title"], "Commonterm paper 5")

    def test_empty_search_query_is_rejected(self):
        self.ingest()
        with self.assertRaisesRegex(literature_db.LiteratureError, "cannot be empty"):
            literature_db.search_library(
                self.connection,
                self.fts5,
                "   ",
                scope="all",
                mode="terms",
                topics=[],
                year_from=None,
                year_to=None,
                limit=10,
            )

    def test_list_uses_the_preferred_article_version(self):
        preprint_manifest = sample_manifest(self.source, body=b"preprint shell")
        preprint_manifest["selected"]["candidate"]["version"] = "preprint"
        self.ingest(manifest=preprint_manifest)

        published_root = self.root / "published"
        published_root.mkdir()
        published_manifest = sample_manifest(
            published_root,
            body=b"published shell",
            text_body="The published article contains revised full text.",
        )
        self.ingest(manifest=published_manifest)

        listed = literature_db.list_library(
            self.connection,
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["results"][0]["version_kind"], "published")

    def test_duplicate_ingest_is_unchanged(self):
        manifest = sample_manifest(self.source)
        first = self.ingest(manifest=manifest)
        second = self.ingest(manifest=manifest)
        self.assertTrue(first["digest_created"])
        self.assertFalse(second["digest_created"])
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["papers"], 1)
        self.assertEqual(stats["counts"]["versions"], 1)
        self.assertEqual(stats["counts"]["digests"], 1)

    def test_merge_adds_a_facet_in_place(self):
        manifest = sample_manifest(self.source)
        original = self.ingest(manifest=manifest)
        new_facet = {
            "key": "waiting-time",
            "label": "等待时间分布",
            "aliases": ["waiting time"],
            "summary": "The distribution is bimodal.",
            "keywords": ["lognormal"],
            "findings": [
                {
                    "statement": "The two waiting-time peaks are near 18 s and 51 ms.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.1", "figure": "2"},
                    "values": [
                        {"name": "long peak", "value": 18, "unit": "s"},
                        {"name": "short peak", "value": 51, "unit": "ms"},
                    ],
                    "keywords": ["bimodal"],
                }
            ],
            "methods": ["two-lognormal fit"],
            "limitations": [],
        }
        incoming = sample_digest(facets=[new_facet])
        incoming["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Previously covered dimensions"],
            }
        )
        result = self.ingest(manifest=manifest, digest=incoming, merge=True)
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["digest_id"], original["digest_id"])
        self.assertEqual(len(result["facets"]), 3)
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertEqual(
            len(shown["versions"][0]["digest"]["digest"]["facets"]), 3
        )

    def test_replace_digest_updates_the_single_digest_in_place(self):
        manifest = sample_manifest(self.source)
        original = self.ingest(manifest=manifest)
        replacement_facet = {
            "key": "waiting-time-distribution",
            "label": "Waiting-time distribution",
            "aliases": ["waiting time"],
            "summary": "The complete analysis identifies two waiting-time regimes.",
            "keywords": ["bimodal waiting time"],
            "findings": [
                {
                    "statement": "The two fitted peaks occur near 18 s and 51 ms.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.2", "figure": "2"},
                    "values": [
                        {"name": "long-timescale peak", "value": 18, "unit": "s"},
                        {"name": "short-timescale peak", "value": 51, "unit": "ms"},
                    ],
                    "keywords": ["waiting-time peaks"],
                }
            ],
            "methods": ["two-lognormal fit"],
            "limitations": [],
        }
        replacement_facet["findings"].append(
            {
                "statement": "Intervals longer than one second are near Poissonian.",
                "kind": "interpretation",
                "confidence": "medium",
                "locator": {"section": "3.2"},
                "values": [],
                "keywords": ["Poisson process"],
            }
        )
        supporting = sample_digest()["facets"][1]
        replacement = sample_digest(facets=[replacement_facet, supporting])

        result = self.ingest(
            manifest=manifest,
            digest=replacement,
            replace_digest=True,
        )

        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["digest_id"], original["digest_id"])
        self.assertEqual(
            result["facets"],
            ["waiting-time-distribution", "circular-polarization"],
        )
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        stored = shown["versions"][0]["digest"]
        self.assertIsNotNone(stored)
        self.assertEqual(
            [facet["key"] for facet in stored["digest"]["facets"]],
            ["waiting-time-distribution", "circular-polarization"],
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM digests").fetchone()[0],
            1,
        )

    def test_replace_digest_requires_existing_digest(self):
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "requires an existing paper"
        ):
            self.ingest(replace_digest=True)

    def test_replace_digest_rejects_new_version_before_copy(self):
        self.ingest()
        before = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        changed_manifest = sample_manifest(
            self.source,
            body=b"<html>article two</html>",
            text_body="A scientifically distinct second article version.",
        )
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "this exact article version"
        ):
            self.ingest(
                manifest=changed_manifest,
                replace_digest=True,
            )
        after = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        self.assertEqual(after, before)

    def test_replace_digest_rejects_targeted_replacement(self):
        manifest = sample_manifest(self.source)
        self.ingest(manifest=manifest)
        targeted = sample_digest()
        targeted["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Remaining article sections"],
            }
        )
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "requires a complete full"
        ):
            self.ingest(
                manifest=manifest,
                digest=targeted,
                replace_digest=True,
            )

    def test_changed_digest_requires_merge_to_prevent_facet_loss(self):
        manifest = sample_manifest(self.source)
        self.ingest(manifest=manifest)
        reduced = sample_digest(facets=[sample_digest()["facets"][0]])
        reduced["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Polarization dimensions"],
            }
        )
        with self.assertRaises(literature_db.LiteratureError):
            self.ingest(manifest=manifest, digest=reduced, merge=False)
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["digests"], 1)

    def test_digest_conflict_is_rejected_before_a_new_wrapper_is_copied(self):
        self.ingest(manifest=sample_manifest(self.source, body=b"<html>first</html>"))
        refreshed_root = self.root / "refreshed-wrapper"
        refreshed_root.mkdir()
        refreshed = sample_manifest(refreshed_root, body=b"<html>second</html>")
        reduced = sample_digest(facets=[sample_digest()["facets"][0]])
        reduced["reading"].update(
            {"status": "targeted", "unread_sections": ["Polarization dimensions"]}
        )
        artifact_hash = refreshed["selected"]["sha256"]
        object_dir = self.library / "objects" / artifact_hash[:2] / artifact_hash

        with self.assertRaisesRegex(
            literature_db.LiteratureError, "already has a different digest"
        ):
            self.ingest(manifest=refreshed, digest=reduced, merge=False)

        self.assertFalse(object_dir.exists())

    def test_new_article_content_creates_a_new_version(self):
        first_manifest = sample_manifest(self.source, body=b"<html>version one</html>")
        self.ingest(manifest=first_manifest)
        second_root = self.root / "second"
        second_root.mkdir()
        second_manifest = sample_manifest(
            second_root,
            body=b"<html>version two</html>",
            text_body="The scientific article now contains a revised result.",
        )
        second = self.ingest(manifest=second_manifest)
        self.assertTrue(second["version_created"])
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["versions"], 2)
        changed = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=[],
            artifact_hash="0" * 64,
            include_digest=False,
        )
        self.assertEqual(changed["reuse_status"], "version_changed")
        self.assertEqual(changed["open_gate_action"], "complete_ingest")
        self.assertTrue(changed["complete_ingest_required"])

    def test_changed_article_rejects_targeted_first_digest(self):
        first_manifest = sample_manifest(self.source, body=b"<html>version one</html>")
        self.ingest(manifest=first_manifest)
        second_root = self.root / "targeted-second-version"
        second_root.mkdir()
        second_manifest = sample_manifest(
            second_root,
            body=b"<html>version two</html>",
            text_body="The scientific article now contains a revised result.",
        )
        targeted = sample_digest()
        targeted["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Sections outside the requested facet"],
            }
        )
        artifact_hash = second_manifest["selected"]["sha256"]
        object_dir = self.library / "objects" / artifact_hash[:2] / artifact_hash

        with self.assertRaisesRegex(
            literature_db.LiteratureError, "exact article version"
        ):
            self.ingest(manifest=second_manifest, digest=targeted)

        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["versions"], 1)
        self.assertFalse(object_dir.exists())

    def test_changed_html_wrapper_with_same_text_reuses_the_version(self):
        first_manifest = sample_manifest(self.source, body=b"<html>shell one</html>")
        first = self.ingest(manifest=first_manifest)
        second_root = self.root / "wrapper-refresh"
        second_root.mkdir()
        second_manifest = sample_manifest(
            second_root,
            body=b"<html data-request-id='new'>shell two</html>",
        )
        second = self.ingest(manifest=second_manifest)
        self.assertFalse(second["version_created"])
        self.assertEqual(second["version_id"], first["version_id"])
        self.assertEqual(second["content_sha256"], first["content_sha256"])
        self.assertNotEqual(second["artifact_sha256"], first["artifact_sha256"])
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["versions"], 1)
        self.assertEqual(stats["counts"]["artifacts"], 2)
        reused = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=[],
            artifact_hash=second["content_sha256"],
            include_digest=False,
        )
        self.assertEqual(reused["reuse_status"], "reusable")
        self.assertEqual(reused["open_gate_action"], "reuse_complete_record")
        self.assertFalse(reused["complete_ingest_required"])
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertEqual(len(shown["versions"][0]["artifacts"]), 2)

    def test_hash_mismatch_is_rejected(self):
        manifest = sample_manifest(self.source)
        manifest["selected"]["sha256"] = "0" * 64
        with self.assertRaises(literature_db.LiteratureError):
            self.ingest(manifest=manifest)

    def test_reindex_restores_search_documents(self):
        self.ingest()
        self.connection.execute("DELETE FROM search_documents")
        if self.fts5:
            self.connection.execute("DELETE FROM search_fts")
        self.connection.commit()
        rebuilt = literature_db.rebuild_index(self.connection, self.fts5)
        self.assertEqual(rebuilt["documents"], 1)
        result = literature_db.search_library(
            self.connection,
            self.fts5,
            "micropulse",
            scope="fulltext",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(result["count"], 1)


class CliTests(unittest.TestCase):
    def test_template_and_validation_do_not_create_a_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", temporary, "template"], stdout=output
            )
            self.assertEqual(code, 0)
            self.assertFalse((Path(temporary) / "literature.sqlite3").exists())

            digest_path = Path(temporary) / "digest.json"
            digest_path.write_text(json.dumps(sample_digest()), encoding="utf-8")
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", temporary, "validate-digest", str(digest_path)],
                stdout=output,
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "valid")
            self.assertFalse((Path(temporary) / "literature.sqlite3").exists())

    def test_audit_uses_a_read_only_database_connection(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "library"
            stderr = io.StringIO()
            code = literature_db.run(
                ["--library-dir", str(library), "audit"], stderr=stderr
            )
            self.assertEqual(code, 2)
            self.assertIn("does not exist", stderr.getvalue())
            self.assertFalse((library / "literature.sqlite3").exists())

            connection, _fts5 = literature_db.connect_library(library)
            connection.close()
            database = library / "literature.sqlite3"
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", str(library), "audit"], stdout=output
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "healthy")
            after = hashlib.sha256(database.read_bytes()).hexdigest()
            self.assertEqual(after, before)

    def test_lookup_on_missing_library_is_read_only_and_returns_not_found(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "missing-library"
            output = io.StringIO()

            code = literature_db.run(
                [
                    "--library-dir",
                    str(library),
                    "lookup",
                    "2023ApJ...955..142Z",
                ],
                stdout=output,
            )

            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())["results"][0]
            self.assertEqual(result["reuse_status"], "not_found")
            self.assertFalse(library.exists())


if __name__ == "__main__":
    unittest.main()
