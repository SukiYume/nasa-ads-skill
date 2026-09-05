from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_literature_db import literature_db as lib, sample_digest, sample_manifest
from test_ads_api import FakeResponse, RecordingOpener

import ads_api
import library_catalog as catalog
import library_web


def source_record(
    bibcode="2023ApJ...955..142Z", title="FAST Observations of FRB 20220912A"
):
    return {
        "bibcode": bibcode,
        "title": [title],
        "author": ["Zhang, Y. K."],
        "abstract": "FAST observations measure burst statistics and circular polarization.",
        "year": "2023",
        "pub": "The Astrophysical Journal",
        "doctype": "article",
        "doi": ["10.3847/1538-4357/aced0b"],
        "identifier": ["arXiv:2304.14665"],
        "volume": "955",
        "page": ["142"],
    }


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "library"
        self.source = self.root / "source"
        self.source.mkdir()
        self.connection, self.fts = lib.connect_library(self.library)

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def capture(self, records=None, **kwargs):
        records = [source_record()] if records is None else records
        return catalog.capture_search(
            self.connection,
            self.fts,
            {"response": {"numFound": 50, "docs": records}},
            query="FRB polarization",
            parameters={"rows": len(records), "start": 0},
            **kwargs,
        )

    def ingest(self, manifest=None, digest=None, **kwargs):
        return lib.ingest_record(
            self.connection,
            self.fts,
            self.library,
            manifest or sample_manifest(self.source),
            digest or sample_digest(),
            merge=kwargs.pop("merge", False),
            **kwargs,
        )

    def lookup(self, identifier="2023ApJ...955..142Z", sha=None):
        return lib.lookup_one(
            self.connection,
            identifier,
            topics=[],
            artifact_hash=sha,
            include_digest=True,
        )

    def test_legacy_manifest_cache_paths_use_verified_durable_objects(self):
        result = self.ingest()
        manifest_path = Path(self.lookup()["version"]["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["selected"]["artifact_path"] = str(self.root / "deleted-cache.html")
        manifest["selected"]["text_path"] = str(self.root / "deleted-cache.txt")
        digest = sample_digest()
        digest["reading"]["status"] = "targeted"
        digest["reading"]["unread_sections"] = ["Previously read sections"]
        self.assertEqual(
            self.ingest(manifest, digest, merge=True)["version_id"],
            result["version_id"],
        )

    def test_completion_requires_summary_and_classification(self):
        result = self.capture()
        record = result["records"][0]
        catalog.summarize(
            self.connection,
            [
                {
                    "identifier": record["identifier"],
                    "source_hash": record["source_hash"],
                    "summary": "A source-grounded summary.",
                }
            ],
        )
        report = catalog.completion_report(self.connection, run_id=result["run_id"])
        self.assertEqual(
            (report["status"], report["pending_summaries"], report["uncategorized"]),
            ("incomplete", 0, 1),
        )
        output = io.StringIO()
        self.assertEqual(
            lib.run(
                [
                    "--library-dir",
                    str(self.library),
                    "check",
                    "--run-id",
                    str(result["run_id"]),
                ],
                stdout=output,
            ),
            1,
        )
        batch = [
            {
                "identifier": record["identifier"],
                "collections": ["FRB/Polarization"],
                "tags": ["FAST"],
                "roles": ["discussion"],
            }
        ]
        catalog.organize_batch(self.connection, batch)
        catalog.organize_batch(self.connection, batch)
        self.assertEqual(
            catalog.completion_report(self.connection)["status"], "complete"
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM paper_tags").fetchone()[0], 1
        )

    def test_organization_batch_is_atomic_on_invalid_second_record(self):
        self.capture()
        with self.assertRaises(lib.LiteratureError):
            catalog.organize_batch(
                self.connection,
                [
                    {
                        "identifier": "2023ApJ...955..142Z",
                        "collections": ["FRB/Polarization"],
                    },
                    {
                        "identifier": "2023ApJ...955..142Z",
                        "collections": ["FRB"],
                        "roles": ["invalid"],
                    },
                ],
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM paper_collections"
            ).fetchone()[0],
            0,
        )

    def test_reading_check_requires_complete_reading_after_summary_completion(self):
        record = self.capture()["records"][0]
        catalog.summarize(self.connection, [{
            "identifier": record["identifier"], "source_hash": record["source_hash"],
            "summary": "A source-grounded summary.", "collections": ["FRB/Polarization"],
        }])
        self.assertEqual(catalog.completion_report(self.connection)["status"], "complete")
        report = catalog.reading_completion_report(self.connection, [record["identifier"]])
        self.assertEqual((report["status"], report["pending_readings"]), ("incomplete", 1))
        self.ingest()
        report = catalog.reading_completion_report(self.connection, [record["identifier"]])
        self.assertEqual((report["status"], report["complete_readings"]), ("complete", 1))

    def test_reading_check_covers_exact_version_integrity_and_classification(self):
        self.ingest()
        identifier = "2023ApJ...955..142Z"
        report = catalog.reading_completion_report(self.connection, [identifier, identifier])
        self.assertEqual(report["requested_versions"], 1)
        self.assertEqual(report["complete_readings"], 1)
        self.assertEqual(report["needs_classification"], [identifier])
        catalog.annotate_paper(self.connection, report["results"][0]["paper_id"], collections=["FRB/Polarization"])
        missing = catalog.reading_completion_report(self.connection, ["arXiv:2304.14665v99"])
        self.assertEqual(missing["pending_readings"], 1)
        Path(self.lookup()["version"]["artifact_path"]).write_text("corrupted artifact", encoding="utf-8")
        broken = catalog.reading_completion_report(self.connection, [identifier])
        self.assertEqual(broken["pending_readings"], 1)
        self.assertIn("changed", broken["needs_reading"][0]["reason"])

    def test_reading_check_cli_uses_explicit_list_and_readonly_missing_library(self):
        shortlist = self.root / "shortlist.txt"
        shortlist.write_text("\ufeff2023ApJ...955..142Z\n\n2023ApJ...955..142Z\n", encoding="utf-8")
        output = io.StringIO()
        empty = self.root / "new-library"
        code = lib.run(["--library-dir", str(empty), "reading-check", "--identifiers-file", str(shortlist)], stdout=output)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["requested_versions"], 1)
        self.assertFalse(empty.exists())
        self.assertEqual(lib.run(["--library-dir", str(empty), "reading-check"], stderr=io.StringIO()), 2)

    def test_full_digest_has_list_summary_without_search_brief(self):
        self.ingest()
        item = catalog.browse(self.connection, self.fts)["results"][0]
        self.assertEqual(item["snippet"], sample_digest()["overview"]["summary"])

    def test_browse_sorts_before_pagination_and_filters_unclassified(self):
        first = source_record(title="Zeta")
        second = source_record("2016PhRvL.116f1102A", "Alpha")
        second.update(year="2016", doi=[], identifier=[])
        self.capture([first, second])
        catalog.organize_batch(
            self.connection, [{"identifier": first["bibcode"], "collections": ["FRB"]}]
        )
        self.assertEqual(
            catalog.browse(self.connection, self.fts, sort="year-asc", limit=1)[
                "results"
            ][0]["title"],
            "Alpha",
        )
        self.assertEqual(
            catalog.browse(self.connection, self.fts, uncategorized=True)["count"], 1
        )
        self.assertEqual(
            catalog.browse(self.connection, self.fts, year_from=2020)["count"], 1
        )

    def test_official_export_import_preserves_tex_and_rejects_unknown_record_atomically(
        self,
    ):
        self.capture()
        entry = "@ARTICLE{2023ApJ...955..142Z, title={{FRB} and {\\alpha}}, author={{Zhang}, Y.}}\n"
        with self.assertRaises(lib.LiteratureError):
            catalog.import_ads_citations(
                self.connection, entry + "@article{2016PhRvL.116f1102A, title={Other}}"
            )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM citations").fetchone()[0], 0
        )
        catalog.import_ads_citations(self.connection, entry)
        self.assertEqual(
            catalog.citation_for_paper(self.connection, 1)["bibtex"], entry
        )

    def test_completion_rejects_unknown_run(self):
        with self.assertRaises(lib.LiteratureError):
            catalog.completion_report(self.connection, run_id=999)

    def test_malformed_note_rolls_back_summary_batch(self):
        result = self.capture()["records"][0]
        with self.assertRaises(lib.LiteratureError):
            catalog.summarize(
                self.connection,
                [
                    {
                        "identifier": result["identifier"],
                        "source_hash": result["source_hash"],
                        "summary": "A source summary.",
                        "note": 42,
                    }
                ],
            )
        self.assertEqual(catalog.pending_summaries(self.connection)["count"], 1)

    def test_citation_from_preprint_is_not_used_for_published_metadata(self):
        self.capture()
        with self.connection:
            self.connection.execute(
                "INSERT INTO citations VALUES (1, ?, ?, ?, ?)",
                (
                    "2023arXiv230414665Z",
                    "@misc{2023arXiv230414665Z, title={Preprint}}",
                    "ads",
                    "2026-01-01",
                ),
            )
        citation = catalog.citation_for_paper(self.connection, 1)
        self.assertEqual(citation["citekey"], "2023ApJ...955..142Z")
        self.assertEqual(citation["source"], "stored-metadata")

    def test_backup_can_be_relocated_before_restoration(self):
        self.ingest()
        backup = self.root / "backup"
        lib.create_library_backup(self.connection, self.fts, self.library, backup)
        relocated = self.root / "archives" / "moved-backup"
        relocated.parent.mkdir()
        backup.rename(relocated)
        restored = self.root / "restored"
        lib.restore_library(relocated, restored)
        connection, fts = lib.connect_library_readonly(restored)
        try:
            self.assertEqual(
                lib.audit_library(connection, fts, restored, verify_hashes=True)[
                    "errors"
                ],
                [],
            )
        finally:
            connection.close()

    def test_capture_retains_every_returned_record_and_pending_source(self):
        result = self.capture()
        self.assertEqual(result["pending_summaries"], 1)
        self.assertEqual(result["captured"], 1)
        self.assertEqual(self.lookup()["reuse_status"], "needs_reading")
        self.assertEqual(self.lookup()["brief"]["summary_status"], "pending")
        self.assertEqual(
            catalog.pending_summaries(self.connection, run_id=result["run_id"])[
                "count"
            ],
            1,
        )
        audit = lib.audit_library(
            self.connection, self.fts, self.library, verify_hashes=True
        )
        self.assertEqual(audit["errors"], [])

    def test_summarize_and_repeat_capture_reuse_without_fabricated_full_reading(self):
        result = self.capture()
        item = result["records"][0]
        summary = {
            "identifier": item["identifier"],
            "source_hash": item["source_hash"],
            "summary": "FAST 观测约束了该源的爆发统计与圆偏振。",
            "keywords": ["圆偏振"],
            "collections": ["FRB/Polarization"],
            "roles": ["intro", "discussion"],
        }
        catalog.summarize(self.connection, [summary])
        catalog.summarize(self.connection, [summary])
        repeated = self.capture()
        self.assertEqual(repeated["pending_summaries"], 0)
        self.assertEqual(repeated["reused_summaries"], 1)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0], 1
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM briefs").fetchone()[0], 1
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0], 2
        )
        found = lib.search_library(
            self.connection,
            self.fts,
            "圆偏振",
            scope="summary",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=20,
        )
        self.assertEqual(found["count"], 1)
        self.assertEqual(found["results"][0]["reading_status"], "abstract")
        self.assertEqual(self.lookup()["reuse_status"], "needs_reading")

    def test_new_abstract_preserves_old_summary_and_requires_new_one(self):
        first = self.capture()
        catalog.summarize(
            self.connection,
            [
                {
                    "identifier": first["records"][0]["identifier"],
                    "source_hash": first["records"][0]["source_hash"],
                    "summary": "Original evidence summary.",
                }
            ],
        )
        updated = source_record()
        updated["abstract"] = "Updated abstract with a revised conclusion."
        second = self.capture([updated])
        self.assertEqual(second["pending_summaries"], 1)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM briefs WHERE summary <> ''"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            catalog.pending_summaries(self.connection, run_id=first["run_id"])["count"],
            0,
        )

    def test_summaries_reject_wrong_hash_and_overwrite(self):
        result = self.capture()
        record = result["records"][0]
        with self.assertRaises(lib.LiteratureError):
            catalog.summarize(
                self.connection,
                [
                    {
                        "identifier": record["identifier"],
                        "source_hash": "bad",
                        "summary": "A summary.",
                    }
                ],
            )
        summary = {
            "identifier": record["identifier"],
            "source_hash": record["source_hash"],
            "summary": "A source-based summary.",
        }
        catalog.summarize(self.connection, [summary])
        with self.assertRaises(lib.LiteratureError):
            catalog.summarize(
                self.connection, [{**summary, "summary": "Unreviewed replacement."}]
            )

    def test_capture_validates_entire_batch_before_writing(self):
        with self.assertRaises(lib.LiteratureError):
            self.capture([source_record(), {"bibcode": "bad"}])
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0], 0
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0], 0
        )

    def test_metadata_only_evidence_is_explicit(self):
        record = source_record()
        record.pop("abstract")
        self.capture([record])
        self.assertEqual(self.lookup()["brief"]["evidence_level"], "metadata")

    def test_nested_collections_count_distinct_papers_and_preserve_notes(self):
        result = self.capture(
            collections=["FRB/Polarization/Circular", "FRB/Polarization"],
            roles=["methods"],
        )
        paper_id = result["records"][0]["paper_id"]
        with self.connection:
            catalog.annotate_paper(
                self.connection, paper_id, tags=["FAST"], note="My method comparison."
            )
            catalog.annotate_paper(self.connection, paper_id, note="My second reading.")
        tree = catalog.collection_tree(self.connection)
        self.assertEqual(tree["collections"][0]["count"], 1)
        self.assertEqual(tree["collections"][0]["children"][0]["count"], 1)
        found = catalog.browse(
            self.connection, self.fts, collection="FRB", role="methods", tag="FAST"
        )
        self.assertEqual(found["count"], 1)
        self.assertEqual(len(found["results"][0]["notes"]), 2)
        self.assertEqual(
            catalog.browse(self.connection, self.fts, collection="FR")["count"], 0
        )

    def test_collection_path_validation_and_literal_characters(self):
        for invalid in ("../x", "A//B", "A/..", "A\\B"):
            with self.subTest(invalid=invalid), self.assertRaises(lib.LiteratureError):
                catalog.collection_path(invalid)
        self.capture(collections=["Rate_100%/Limits"])
        self.assertEqual(
            catalog.browse(self.connection, self.fts, collection="Rate_100%")["count"],
            1,
        )
        self.assertEqual(
            catalog.browse(self.connection, self.fts, collection="Rate_")["count"], 0
        )

    def test_bibtex_offline_metadata_is_escaped_and_identified(self):
        result = self.capture([source_record(title="A & B {sample} 50%")])
        citation = catalog.citation_for_paper(
            self.connection, result["records"][0]["paper_id"]
        )
        self.assertEqual(citation["source"], "stored-metadata")
        self.assertIn(r"A \& B \{sample\} 50\%", citation["bibtex"])
        self.assertIn("volume = {955}", citation["bibtex"])
        self.assertIn("pages = {142}", citation["bibtex"])
        self.assertIn("doi = {10.3847/1538-4357/aced0b}", citation["bibtex"])

    def test_official_citation_is_cached_and_survives_offline_export(self):
        result = self.capture()
        paper_id = result["records"][0]["paper_id"]
        body = b"@ARTICLE{2023ApJ...955..142Z,\n title={Verified ADS entry}\n}\n"
        with patch.object(
            catalog.ads_api, "request_api", return_value=ads_api.ApiResponse(body, {})
        ) as request:
            catalog.cache_ads_citation(self.connection, paper_id, "test-token")
        self.assertEqual(request.call_count, 1)
        with patch.object(
            catalog.ads_api,
            "request_api",
            side_effect=AssertionError("Offline export made a network call"),
        ):
            self.assertEqual(
                catalog.export_citations(self.connection, [paper_id, paper_id]),
                body.decode(),
            )

    def test_citation_response_identity_is_checked(self):
        paper_id = self.capture()["records"][0]["paper_id"]
        with patch.object(
            catalog.ads_api,
            "request_api",
            return_value=ads_api.ApiResponse(b"@article{different,title={Wrong}}", {}),
        ):
            with self.assertRaises(lib.LiteratureError):
                catalog.cache_ads_citation(self.connection, paper_id, "token")
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM citations").fetchone()[0], 0
        )

    def test_capture_then_complete_ingest_keeps_one_paper_and_organization(self):
        result = self.capture(collections=["FRB/Methods"])
        paper_id = result["records"][0]["paper_id"]
        ingested = self.ingest()
        self.assertEqual(ingested["paper_id"], paper_id)
        self.assertEqual(self.lookup()["reuse_status"], "reusable")
        self.assertIn("FRB/Methods", self.lookup()["collections"])
        self.assertEqual(
            lib.list_library(
                self.connection, topics=[], year_from=None, year_to=None, limit=10
            )["count"],
            1,
        )

    def test_published_metadata_upgrades_preprint_without_losing_alias(self):
        preprint = source_record(bibcode="2023arXiv230414665Z")
        preprint.update(doctype="eprint", pub="arXiv e-prints")
        self.capture([preprint])
        self.capture()
        self.assertEqual(self.lookup()["bibcode"], "2023ApJ...955..142Z")
        self.assertEqual(
            self.lookup("2023arXiv230414665Z")["paper_id"], self.lookup()["paper_id"]
        )

    def test_explicit_version_requires_exact_arxiv_label(self):
        manifest = sample_manifest(self.source)
        manifest["selected"]["candidate"].update(
            source="arxiv",
            version="preprint",
            url="https://arxiv.org/html/2304.14665v2",
        )
        manifest["selected"]["final_url"] = "https://arxiv.org/html/2304.14665v2"
        self.ingest(manifest)
        self.assertEqual(self.lookup("arXiv:2304.14665v2")["reuse_status"], "reusable")
        self.assertEqual(
            self.lookup("arXiv:2304.14665v1")["reuse_status"], "version_changed"
        )
        self.assertEqual(self.lookup("arXiv:2304.14665")["reuse_status"], "reusable")

    def test_lookup_rejects_missing_or_modified_fulltext_objects(self):
        result = self.ingest()
        Path(result["object_paths"]["text"]).write_text("tampered", encoding="utf-8")
        assessment = self.lookup()
        self.assertEqual(assessment["reuse_status"], "needs_reading")
        self.assertIn("reason", assessment)
        self.assertNotIn("digest", assessment)

    def test_historical_artifact_hash_and_audit_retain_provenance(self):
        first = self.ingest()
        manifest = sample_manifest(
            self.source, body=b"<html>new wrapper, same text</html>"
        )
        self.ingest(manifest)
        self.assertEqual(
            self.lookup(sha=first["artifact_sha256"])["reuse_status"], "reusable"
        )
        audit = lib.audit_library(
            self.connection, self.fts, self.library, verify_hashes=True
        )
        self.assertEqual(audit["errors"], [])
        self.assertNotIn(
            "orphan_object_directories", [item["kind"] for item in audit["warnings"]]
        )

    def test_targeted_merge_preserves_paper_overview_and_named_record_details(self):
        original = sample_digest()
        addition = sample_digest()
        addition["reading"]["status"] = "targeted"
        addition["overview"]["summary"] = "Only one requested detail."
        addition["methods"] = [
            {"name": "burst search", "keywords": ["new method term"]}
        ]
        merged = lib.merge_digests(original, lib.validate_digest(addition))
        self.assertEqual(merged["overview"], original["overview"])
        self.assertEqual(
            merged["methods"][0]["description"], original["methods"][0]["description"]
        )
        self.assertIn("new method term", merged["methods"][0]["keywords"])

    def test_stored_manifest_supports_merge_after_download_cache_disappears(self):
        result = self.ingest()
        manifest = json.loads(
            Path(result["object_paths"]["manifest"]).read_text(encoding="utf-8")
        )
        for path in self.source.iterdir():
            path.unlink()
        addition = sample_digest()
        addition["reading"]["status"] = "targeted"
        addition["keywords"].append("cached-only verification")
        self.ingest(manifest, addition, merge=True)
        self.assertIn("cached-only verification", self.lookup()["digest"]["keywords"])

    def test_changed_extraction_of_same_artifact_creates_separate_text_object(self):
        first = self.ingest()
        manifest = sample_manifest(
            self.source, text_body="A corrected extraction includes another equation."
        )
        second = self.ingest(manifest)
        self.assertEqual(first["artifact_sha256"], second["artifact_sha256"])
        self.assertNotEqual(
            first["object_paths"]["text"], second["object_paths"]["text"]
        )
        self.assertTrue(Path(first["object_paths"]["text"]).is_file())
        self.assertEqual(
            lib.audit_library(
                self.connection, self.fts, self.library, verify_hashes=True
            )["errors"],
            [],
        )

    def test_transaction_merge_keeps_concurrent_update_with_same_digest_id(self):
        self.ingest()
        addition = sample_digest()
        addition["reading"]["status"] = "targeted"
        addition["keywords"].append("update-A")
        original_store = lib.store_objects

        def interleaved_store(library, manifest):
            other, other_fts = lib.connect_library(library)
            try:
                row = other.execute("SELECT * FROM digests").fetchone()
                concurrent = json.loads(row["digest_json"])
                concurrent["keywords"].append("update-B")
                with other:
                    lib.insert_digest(other, row["version_id"], concurrent)
            finally:
                other.close()
            return original_store(library, manifest)

        with patch.object(lib, "store_objects", side_effect=interleaved_store):
            self.ingest(sample_manifest(self.source), addition, merge=True)
        self.assertIn("update-A", self.lookup()["digest"]["keywords"])
        self.assertIn("update-B", self.lookup()["digest"]["keywords"])

    def test_methods_sections_can_trace_method_facets(self):
        digest = sample_digest()
        for coverage in digest["reading"]["coverage"]:
            if coverage["facet_keys"]:
                coverage.update(
                    role="methods", notes="Technical methods and their evidence."
                )
        self.assertEqual(lib.validate_digest(digest)["reading"]["status"], "full")

    def test_visual_reading_rejects_gaps_invalid_ranges_and_unknown_counts(self):
        manifest = sample_manifest(self.source)
        manifest["status"] = "needs_visual_reading"
        manifest["selected"]["content_sha256"] = manifest["selected"]["sha256"]
        manifest["selected"]["statistics"]["pages"] = 12
        digest = sample_digest()
        digest["reading"]["status"] = "visual"
        for ranges in (["1-5"], ["all"], ["0-12"], ["1-13"], ["1-5", "7-12"]):
            digest["reading"]["visual_page_ranges"] = ranges
            with self.subTest(ranges=ranges), self.assertRaises(lib.LiteratureError):
                lib.validate_ingest_manifest(manifest, lib.validate_digest(digest))
        digest["reading"]["visual_page_ranges"] = ["1-6", "7-12"]
        lib.validate_ingest_manifest(manifest, lib.validate_digest(digest))
        manifest["selected"]["statistics"]["pages"] = None
        with self.assertRaises(lib.LiteratureError):
            lib.validate_ingest_manifest(manifest, digest)

    def test_nonfinite_measurement_values_are_rejected(self):
        for value in (float("nan"), float("inf")):
            digest = sample_digest()
            digest["facets"][0]["findings"][0]["values"][0]["value"] = value
            with self.assertRaises(lib.LiteratureError):
                lib.validate_digest(digest)

    def test_backup_and_restore_work_without_original_library(self):
        self.capture(collections=["FRB/Methods"])
        self.ingest()
        backup = self.root / "backup"
        lib.create_library_backup(self.connection, self.fts, self.library, str(backup))
        self.connection.close()
        self.library.rename(self.root / "unavailable-original")
        restored = self.root / "restored"
        lib.restore_library(backup, restored)
        self.connection, self.fts = lib.connect_library_readonly(restored)
        lookup = self.lookup()
        self.assertEqual(lookup["reuse_status"], "reusable")
        self.assertTrue(Path(lookup["version"]["text_path"]).is_relative_to(restored))
        self.assertEqual(
            lib.audit_library(self.connection, self.fts, restored, verify_hashes=True)[
                "errors"
            ],
            [],
        )
        self.assertEqual(catalog.collection_tree(self.connection)["count"], 2)

    def test_restore_rejects_existing_destination(self):
        with self.assertRaises(lib.LiteratureError):
            lib.restore_library(self.root, self.library)

    def test_write_commands_require_explicit_schema_migration(self):
        self.connection.execute("PRAGMA user_version=2")
        self.connection.commit()
        with self.assertRaises(lib.LiteratureError):
            lib.connect_library(self.library)
        self.assertEqual(
            self.connection.execute("PRAGMA user_version").fetchone()[0], 2
        )
        out = io.StringIO()
        self.assertEqual(
            lib.run(["--library-dir", str(self.library), "init"], stdout=out), 0
        )
        self.assertTrue(
            Path(json.loads(out.getvalue())["migration_backup"]["destination"]).is_dir()
        )
        self.assertEqual(
            self.connection.execute("PRAGMA user_version").fetchone()[0], 3
        )

    def test_unhealthy_audit_returns_nonzero(self):
        result = self.ingest()
        Path(result["object_paths"]["artifact"]).unlink()
        out = io.StringIO()
        self.assertEqual(
            lib.run(["--library-dir", str(self.library), "audit"], stdout=out), 1
        )
        self.assertEqual(json.loads(out.getvalue())["status"], "unhealthy")

    def test_substring_wildcards_are_literal_and_fts_requires_engine(self):
        self.ingest()
        found = lib.search_library(
            self.connection,
            False,
            "%",
            scope="fulltext",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=20,
        )
        self.assertEqual(found["count"], 0)
        with self.assertRaises(lib.LiteratureError):
            lib.search_library(
                self.connection,
                False,
                "FRB OR FAST",
                scope="all",
                mode="fts",
                topics=[],
                year_from=None,
                year_to=None,
                limit=20,
            )

    def test_default_api_search_captures_in_requested_library(self):
        payload = {"response": {"numFound": 1, "docs": [source_record()]}}
        opener = RecordingOpener(FakeResponse(json.dumps(payload).encode()))
        out, err = io.StringIO(), io.StringIO()
        code = ads_api.run(
            [
                "--library-dir",
                str(self.library),
                "search",
                "-q",
                "FRB",
                "--collection",
                "FRB",
            ],
            environ={"ADS_API_TOKEN": "test-secret"},
            stdout=out,
            stderr=err,
            opener=opener,
        )
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(
            json.loads(out.getvalue())["literature"]["pending_summaries"], 1
        )
        self.assertEqual(self.lookup()["brief"]["evidence_level"], "abstract")
        self.assertNotIn("test-secret", out.getvalue())

    def test_failed_capture_preserves_ads_response_and_failure_status(self):
        payload = {"response": {"numFound": 1, "docs": [{"bibcode": "bad"}]}}
        out, err = io.StringIO(), io.StringIO()
        code = ads_api.run(
            ["--library-dir", str(self.library), "search", "-q", "FRB"],
            environ={"ADS_API_TOKEN": "token"},
            stdout=out,
            stderr=err,
            opener=RecordingOpener(FakeResponse(json.dumps(payload).encode())),
        )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["response"], payload["response"])
        self.assertEqual(json.loads(out.getvalue())["literature"]["status"], "failed")


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.library = Path(self.temp.name) / "library"
        connection, fts = lib.connect_library(self.library)
        result = catalog.capture_search(
            connection,
            fts,
            {
                "response": {
                    "numFound": 1,
                    "docs": [
                        source_record(title="<script>alert(1)</script> Polarization")
                    ],
                }
            },
            query="polarization",
            parameters={},
            collections=["FRB/Polarization"],
        )
        self.paper_id = result["records"][0]["paper_id"]
        connection.close()
        self.server = library_web.make_server(self.library, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def get(self, path, headers=None):
        return urlopen(Request(self.base + path, headers=headers or {}), timeout=5)

    def test_search_detail_hierarchy_and_citation_export(self):
        with self.get("/api/papers?query=Polarization&collection=FRB") as response:
            data = json.load(response)
        self.assertEqual(data["count"], 1)
        with self.get("/api/paper?id=" + str(self.paper_id)) as response:
            paper = json.load(response)
        self.assertIn("<script>", paper["paper"]["title"])
        self.assertEqual(paper["brief"]["summary_status"], "pending")
        with self.get("/api/citations?ids=" + str(self.paper_id)) as response:
            self.assertIn("attachment", response.headers["Content-Disposition"])
            self.assertIn("@article", response.read().decode())
        with self.get("/api/collections") as response:
            self.assertEqual(
                json.load(response)["collections"][0]["children"][0]["name"],
                "Polarization",
            )

    def test_filtered_export_and_live_library_stats(self):
        with self.get(
            "/api/citations?view=filtered&collection=FRB&year_from=2020"
        ) as response:
            self.assertIn("2023ApJ...955..142Z", response.read().decode())
        with self.get("/api/stats") as response:
            stats = json.load(response)
        self.assertEqual(stats["library_dir"], str(self.library))
        self.assertEqual(stats["uncategorized"], 0)
        self.assertTrue(stats["read_only"])
        with self.assertRaises(HTTPError) as context:
            self.get("/api/citations?view=filtered&year_from=2025")
        self.assertEqual(context.exception.code, 400)

    def test_cross_origin_and_dns_rebinding_hosts_are_blocked(self):
        for headers in (
            {"Origin": "https://evil.example"},
            {"Host": "evil.example"},
            {"Sec-Fetch-Site": "cross-site"},
        ):
            with self.subTest(headers=headers), self.assertRaises(HTTPError) as context:
                self.get("/api/papers", headers)
            self.assertEqual(context.exception.code, 403)

    def test_static_assets_and_input_bounds(self):
        for path in ("/", "/app.js", "/style.css"):
            with self.get(path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(
                    "script-src 'self'", response.headers["Content-Security-Policy"]
                )
        for path in (
            "/api/papers?limit=10001",
            "/api/papers?scope=sql",
            "/api/citations?ids=1;DROP",
            "/api/artifact?version=1&kind=../secrets",
        ):
            with self.subTest(path=path), self.assertRaises(HTTPError) as context:
                self.get(path)
            self.assertEqual(context.exception.code, 400)

    def test_http_writes_are_unavailable(self):
        with self.assertRaises(HTTPError) as context:
            urlopen(
                Request(self.base + "/api/papers", data=b"{}", method="POST"), timeout=5
            )
        self.assertEqual(context.exception.code, 501)


if __name__ == "__main__":
    unittest.main()
