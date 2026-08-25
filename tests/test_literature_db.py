from __future__ import annotations

import hashlib
import importlib.util
import io
import json
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
                }
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
                }
            ],
            "methods": ["polarization calibration", "RM synthesis"],
            "limitations": ["The physical origin is not uniquely determined."],
        },
    ]
    return {
        "schema_version": 1,
        "language": "zh-CN",
        "overview": {
            "summary": (
                "FAST measured burst statistics and polarization for FRB 20220912A."
            ),
            "significance": (
                "The paper connects source activity, spectra, and polarization."
            ),
            "questions": ["What controls repeater activity?"],
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
        "facets": facets if facets is not None else default_facets,
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
            "sections": ["1", "2", "3.1", "3.2", "3.3", "4", "5"],
            "page_ranges": [],
            "visual_page_ranges": [],
            "unread_sections": [],
            "notes": "Publisher HTML was read in full.",
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
        "tool_version": "1.8.0",
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
            "statistics": {"words": 8000, "pages": None},
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
        self.assertEqual(template["schema_version"], 1)
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
        self, *, manifest: dict | None = None, digest: dict | None = None, merge=False
    ):
        chosen_manifest = manifest or sample_manifest(self.source)
        chosen_digest = literature_db.validate_digest(digest or sample_digest())
        return literature_db.ingest_record(
            self.connection,
            self.fts5,
            self.library,
            chosen_manifest,
            chosen_digest,
            merge=merge,
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
                "sections": [],
                "visual_page_ranges": ["1-12"],
                "notes": "All twelve rendered pages were inspected.",
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

        missing = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["host galaxy morphology"],
            artifact_hash=None,
            include_digest=False,
        )
        self.assertEqual(missing["reuse_status"], "targeted_reading")
        self.assertEqual(missing["missing_topics"], ["host galaxy morphology"])
        self.assertFalse(literature_db.topic_match(sample_digest()["facets"][0], ""))

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

    def test_merge_adds_a_facet_as_a_new_revision(self):
        manifest = sample_manifest(self.source)
        self.ingest(manifest=manifest)
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
        result = self.ingest(manifest=manifest, digest=incoming, merge=True)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(len(result["facets"]), 3)
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            history=True,
            include_fulltext=False,
        )
        self.assertEqual(len(shown["versions"][0]["digests"]), 2)

    def test_changed_digest_requires_merge_to_prevent_facet_loss(self):
        manifest = sample_manifest(self.source)
        self.ingest(manifest=manifest)
        reduced = sample_digest(facets=[sample_digest()["facets"][0]])
        with self.assertRaises(literature_db.LiteratureError):
            self.ingest(manifest=manifest, digest=reduced, merge=False)
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["digests"], 1)

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
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            history=False,
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


if __name__ == "__main__":
    unittest.main()
