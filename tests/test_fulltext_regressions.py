from __future__ import annotations

import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_fulltext import fulltext, ChunkedResponse, RecordingOpener


class FulltextRegressionTests(unittest.TestCase):
    def test_pinned_arxiv_discovery_excludes_other_versions_and_publisher(self):
        record = {
            "bibcode": "2023ApJ...955..142Z",
            "title": ["Title"],
            "identifier": ["arXiv:2304.14665"],
            "property": [],
        }
        with (
            patch.object(fulltext, "ads_search_record", return_value=record),
            patch.object(fulltext, "arxiv_metadata_record", return_value=None),
            patch.object(
                fulltext,
                "ads_resolver_records",
                return_value=[
                    {
                        "link_type": "ESOURCE|PUB_PDF",
                        "url": "https://example.org/published.pdf",
                    }
                ],
            ),
        ):
            result = fulltext.discover(
                "arXiv:2304.14665v2",
                source="auto",
                use_unpaywall=False,
                timeout=5,
                max_bytes=10000,
                environ={"ADS_API_TOKEN": "token"},
            )
        self.assertIsNone(result["abstract"])
        self.assertEqual(len(result["candidates"]), 2)
        self.assertTrue(
            all(
                candidate.url.endswith("2304.14665v2")
                for candidate in result["candidates"]
            )
        )

    def test_fetch_captures_abstract_only_metadata_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            result = {
                "status": "abstract_only",
                "bibcode": "2023ApJ...955..142Z",
                "title": "FAST Observations",
                "abstract": "Reported circular polarization.",
            }
            with patch.object(fulltext, "fetch_one", return_value=result):
                code = fulltext.run(
                    ["fetch", "2023ApJ...955..142Z", "--library-dir", temporary],
                    stdout=output,
                    environ={},
                )
            payload = json.loads(output.getvalue())["results"][0]
            self.assertEqual(code, 0)
            self.assertEqual(payload["literature"]["pending_summaries"], 1)
            self.assertTrue((Path(temporary) / "literature.sqlite3").exists())

    def test_pinned_arxiv_download_rejects_version_redirect(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = fulltext.arxiv_candidates("2304.14665v2")[1]
            response = ChunkedResponse(
                b"%PDF-1.7", url="https://arxiv.org/pdf/2304.14665v3"
            )
            with self.assertRaisesRegex(fulltext.FullTextError, "requested version"):
                fulltext.materialize_candidate(
                    candidate,
                    Path(temporary),
                    None,
                    timeout=5,
                    max_bytes=10000,
                    environ={},
                    opener=RecordingOpener(response),
                )

    def test_similar_hostname_is_not_an_arxiv_identifier(self):
        self.assertIsNone(
            fulltext.arxiv_id_from_value("https://evilarxiv.org/abs/2304.14665")
        )
        self.assertEqual(
            fulltext.classify_identifier("bibcode:2023ApJ...955..142Z"),
            ("bibcode", "2023ApJ...955..142Z"),
        )

    def test_authority_ranking_precedes_access_priority(self):
        accepted = fulltext.Candidate(
            "author", "accepted", "html", "https://example.org/accepted", 30
        )
        published = fulltext.Candidate(
            "publisher", "published", "pdf", "https://example.org/published", 35
        )
        self.assertEqual(
            fulltext.deduplicate_candidates([accepted, published]),
            [published, accepted],
        )

    def test_pdf_content_type_requires_real_pdf_signature(self):
        with self.assertRaises(fulltext.FullTextError):
            fulltext.actual_format(
                fulltext.Downloaded(
                    b"Access denied", "https://example.org", "application/pdf", {}
                )
            )

    def test_scan_with_sparse_text_reuses_raw_content_fingerprint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "article.pdf"
            text = root / "article.txt"
            artifact.write_bytes(b"%PDF-1.7 scanned pages")
            text.write_text("page 1", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "status": "needs_visual_reading",
                        "selected": {
                            "artifact_path": str(artifact),
                            "text_path": str(text),
                            "sha256": fulltext.sha256_file(artifact),
                            "text_sha256": fulltext.sha256_file(text),
                            "content_sha256": fulltext.sha256_file(artifact),
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(fulltext.cached_result(manifest)["cache_hit"])

    def test_render_cache_is_bound_to_pdf_hash_dpi_and_complete_page_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "article.pdf"
            pdf.write_bytes(b"%PDF-1.7 first edition")
            calls = []

            def renderer(command, **_kwargs):
                calls.append(command)
                prefix = Path(command[-1])
                for page in (1, 2):
                    prefix.with_name(prefix.name + f"-{page}.png").write_bytes(
                        b"PNG page"
                    )
                return fulltext.subprocess.CompletedProcess(command, 0, "", "")

            def render(dpi=150):
                return fulltext.render_pdf(
                    pdf,
                    pages="1-2",
                    output_dir=root / "pages",
                    dpi=dpi,
                    refresh=False,
                    timeout=5,
                    environ={},
                )

            with (
                patch.object(fulltext, "pdf_page_count", return_value=(2, "test")),
                patch.object(fulltext, "find_executable", return_value="pdftoppm"),
                patch.object(fulltext.subprocess, "run", side_effect=renderer),
            ):
                first = render()
                self.assertEqual(render()["status"], "cached")
                Path(first["images"][0]).unlink()
                self.assertEqual(render()["status"], "rendered")
                self.assertEqual(render(200)["status"], "rendered")
                pdf.write_bytes(b"%PDF-1.7 revised edition")
                self.assertEqual(render()["status"], "rendered")
            self.assertEqual(len(calls), 4)


if __name__ == "__main__":
    unittest.main()
