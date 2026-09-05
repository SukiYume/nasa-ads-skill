from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "nasa-ads" / "skills" / "nasa-ads" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "fulltext.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("nasa_ads_fulltext", SCRIPT_PATH)
assert SPEC and SPEC.loader
fulltext = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fulltext
SPEC.loader.exec_module(fulltext)


class ChunkedResponse:
    def __init__(
        self,
        body: bytes,
        *,
        url: str = "https://example.org/paper",
        headers: dict[str, str] | None = None,
    ) -> None:
        self._body = io.BytesIO(body)
        self._url = url
        self.headers = Message()
        for name, value in (headers or {}).items():
            self.headers[name] = value

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> ChunkedResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class RecordingOpener:
    def __init__(self, response: ChunkedResponse) -> None:
        self.response = response
        self.requests = []
        self.timeouts = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response


class IdentifierTests(unittest.TestCase):
    def test_arxiv_identifiers_and_urls_are_normalized(self):
        self.assertEqual(
            fulltext.classify_identifier("arXiv:1901.04502v2"),
            ("arxiv", "1901.04502v2"),
        )
        self.assertEqual(
            fulltext.classify_identifier("https://arxiv.org/pdf/astro-ph/0601001.pdf"),
            ("arxiv", "astro-ph/0601001"),
        )

    def test_doi_and_bibcode_are_classified(self):
        self.assertEqual(
            fulltext.classify_identifier("https://doi.org/10.1093/mnras/stz1521"),
            ("doi", "10.1093/mnras/stz1521"),
        )
        self.assertEqual(
            fulltext.classify_identifier("2019MNRAS.489..176M"),
            ("bibcode", "2019MNRAS.489..176M"),
        )

    def test_arxiv_atom_metadata_fills_fresh_records(self):
        atom = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom' xmlns:arxiv='http://arxiv.org/schemas/atom'>
  <entry>
    <id>https://arxiv.org/abs/2608.30943v1</id>
    <title>The DSA Chronoscope survey</title>
    <summary>A complete survey forecast.</summary>
    <published>2026-08-31T00:00:00Z</published>
    <author><name>Liam Connor</name></author>
  </entry>
</feed>"""
        downloaded = fulltext.Downloaded(
            body=atom,
            final_url="https://export.arxiv.org/api/query?id_list=2608.30943",
            content_type="application/atom+xml",
            headers={},
        )
        with patch.object(fulltext, "fetch_external", return_value=downloaded):
            record = fulltext.arxiv_metadata_record(
                "2608.30943", timeout=10, max_bytes=1024 * 1024
            )
        self.assertIsNotNone(record)
        self.assertEqual(record["title"], ["The DSA Chronoscope survey"])
        self.assertEqual(record["author"], ["Liam Connor"])
        self.assertEqual(record["year"], "2026")


class CandidateTests(unittest.TestCase):
    def test_arxiv_candidates_use_html_and_pdf_not_abs(self):
        candidates = fulltext.arxiv_candidates("1901.04502v2")
        self.assertEqual(
            [candidate.url for candidate in candidates],
            [
                "https://arxiv.org/html/1901.04502v2",
                "https://arxiv.org/pdf/1901.04502v2",
            ],
        )
        self.assertFalse(any("/abs/" in candidate.url for candidate in candidates))

    def test_resolver_arxiv_abstract_link_is_not_fulltext(self):
        candidate = fulltext.resolver_candidate(
            {
                "url": "https://arxiv.org/abs/1901.04502",
                "link_type": "ESOURCE|EPRINT_HTML",
            },
            {"EPRINT_OPENACCESS"},
        )
        self.assertIsNone(candidate)

    def test_http_resolver_link_is_upgraded(self):
        candidate = fulltext.resolver_candidate(
            {
                "url": "http://publisher.example/paper.pdf",
                "link_type": "ESOURCE|PUB_PDF",
            },
            {"PUB_OPENACCESS"},
        )
        assert candidate
        self.assertEqual(candidate.url, "https://publisher.example/paper.pdf")
        self.assertEqual(candidate.access, "open")

    def test_direct_arxiv_discovery_does_not_require_ads_credentials(self):
        with patch.object(fulltext, "arxiv_metadata_record", return_value=None):
            result = fulltext.discover(
                "arXiv:1901.04502",
                source="auto",
                use_unpaywall=False,
                timeout=10,
                max_bytes=1024 * 1024,
                environ={},
            )
        self.assertIsNone(result["bibcode"])
        self.assertEqual(result["arxiv_ids"], ["1901.04502"])
        self.assertEqual(
            [candidate.url for candidate in result["candidates"]],
            [
                "https://arxiv.org/html/1901.04502",
                "https://arxiv.org/pdf/1901.04502",
            ],
        )

    def test_direct_arxiv_discovery_can_require_pdf(self):
        with patch.object(fulltext, "arxiv_metadata_record", return_value=None):
            result = fulltext.discover(
                "arXiv:1901.04502",
                source="arxiv",
                use_unpaywall=False,
                timeout=10,
                max_bytes=1024 * 1024,
                environ={},
                output_format="pdf",
            )
        self.assertEqual(result["requested_format"], "pdf")
        self.assertEqual(
            [(candidate.format, candidate.url) for candidate in result["candidates"]],
            [("pdf", "https://arxiv.org/pdf/1901.04502")],
        )


class HtmlExtractionTests(unittest.TestCase):
    def test_content_fingerprint_ignores_layout_whitespace_and_unicode_width(self):
        first = fulltext.canonical_text_sha256("Result\n\nＡ = 3")  # noqa: RUF001
        second = fulltext.canonical_text_sha256("Result   A = 3")
        self.assertEqual(first, second)

    def test_article_html_is_extracted_with_headings(self):
        paragraphs = " ".join(["measurement result evidence method"] * 100)
        body = (
            "<html><head><title>A stellar measurement</title></head><body>"
            "<nav>menu words</nav><article><h1>A stellar measurement</h1>"
            f"<h2>Methods</h2><p>{paragraphs}</p>"
            "<annotation>duplicate hidden formula tokens</annotation>"
            "<h2>Results</h2><p>The result is significant.</p>"
            "<h2>References</h2><p>A. Example, 2026.</p>"
            "<h2>Instructions for reporting errors</h2>"
            "<h2>Appendix A Additional checks</h2>"
            "</article></body></html>"
        ).encode()
        text, statistics = fulltext.extract_html(body, "A stellar measurement")
        self.assertIn("Methods", text)
        self.assertNotIn("menu words", text)
        self.assertNotIn("duplicate hidden", text)
        self.assertTrue(statistics["focused_article"])
        self.assertGreaterEqual(statistics["headings"], 3)
        self.assertIn("Methods", statistics["outline"])
        self.assertIn("Results", statistics["outline"])
        self.assertNotIn("Instructions for reporting errors", statistics["outline"])
        self.assertIn("Appendix A Additional checks", statistics["outline"])

    def test_prepared_text_outline_extracts_numbered_and_named_sections(self):
        article = """Abstract
1 Introduction
1.1 Survey design
1.8 Jy
1 ms
30 January 2017
I employ parallaxes from Gaia.
1 mas yr-1, respectively. I only consider the clean sample
6.3370 ± 0.0460
§ 2. I describe the data used in this paper
§ 2 Definitions
Figure 1: simulated sky
2 Methods
3 Results
References
I. Example Author
Appendix A Additional checks
A.1 Robustness tests
"""
        self.assertEqual(
            fulltext.infer_text_outline(article),
            [
                "Abstract",
                "1 Introduction",
                "1.1 Survey design",
                "§ 2 Definitions",
                "2 Methods",
                "3 Results",
                "References",
                "Appendix A Additional checks",
                "A.1 Robustness tests",
            ],
        )

    def test_access_page_is_rejected(self):
        body = (
            "<html><main><h1>Access denied</h1><p>Verify you are human. "
            + "word " * 350
            + "</p></main></html>"
        ).encode()
        with self.assertRaises(fulltext.FullTextError):
            fulltext.extract_html(body, None)

    def test_abstract_sized_landing_page_is_rejected(self):
        body = (
            "<html><body><h1>Paper title</h1><p>" + "word " * 400 + "</p></body></html>"
        ).encode()
        with self.assertRaises(fulltext.FullTextError):
            fulltext.extract_html(body, "Paper title")


class PdfAssessmentTests(unittest.TestCase):
    def test_dense_pdf_text_is_fulltext(self):
        status, statistics, warnings = fulltext.assess_pdf_text(
            "result method evidence " * 1000,
            10,
            "pdftotext",
        )
        self.assertEqual(status, "fulltext")
        self.assertGreater(statistics["characters_per_page"], 100)
        self.assertEqual(warnings, [])

    def test_sparse_pdf_text_requires_visual_reading(self):
        status, _, warnings = fulltext.assess_pdf_text("page 1", 12, "pdftotext")
        self.assertEqual(status, "needs_visual_reading")
        self.assertIn("pdf_text_layer_sparse_or_missing", warnings)

    def test_missing_extractor_requires_visual_reading(self):
        status, _, warnings = fulltext.assess_pdf_text(None, 5, None)
        self.assertEqual(status, "needs_visual_reading")
        self.assertIn("pdf_text_extractor_unavailable", warnings)

    def test_pdftotext_timeout_becomes_a_structured_extraction_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "paper.pdf"
            text = root / "paper.txt"
            pdf.write_bytes(b"%PDF-1.7\n")
            with (
                patch.object(fulltext, "find_executable", return_value="pdftotext"),
                patch.object(
                    fulltext.subprocess,
                    "run",
                    side_effect=fulltext.subprocess.TimeoutExpired("pdftotext", 180),
                ),
            ):
                extracted, extractor, error = fulltext.extract_pdf_text(pdf, text, {})
        self.assertIsNone(extracted)
        self.assertEqual(extractor, "pdftotext")
        self.assertIn("failed", error)

    def test_renderer_timeout_becomes_a_fulltext_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.7\n")
            with (
                patch.object(fulltext, "pdf_page_count", return_value=(1, "test")),
                patch.object(fulltext, "find_executable", return_value="pdftoppm"),
                patch.object(
                    fulltext.subprocess,
                    "run",
                    side_effect=fulltext.subprocess.TimeoutExpired("pdftoppm", 10),
                ),
                self.assertRaises(fulltext.FullTextError),
            ):
                fulltext.render_pdf(
                    pdf,
                    pages="1",
                    output_dir=None,
                    dpi=150,
                    refresh=False,
                    timeout=10,
                    environ={},
                )


class ExternalRequestTests(unittest.TestCase):
    def test_external_request_never_receives_ads_token(self):
        response = ChunkedResponse(
            b"%PDF-1.7\n",
            headers={"content-type": "application/pdf"},
        )
        opener = RecordingOpener(response)
        downloaded = fulltext.fetch_external(
            "https://example.org/paper.pdf",
            timeout=10,
            max_bytes=1024,
            opener=opener,
        )
        self.assertEqual(downloaded.content_type, "application/pdf")
        request = opener.requests[0]
        self.assertIsNone(request.get_header("Authorization"))
        self.assertNotIn(
            "ADS",
            " ".join(f"{name}: {value}" for name, value in request.header_items()),
        )

    def test_external_response_is_size_bounded(self):
        response = ChunkedResponse(b"x" * 20)
        opener = RecordingOpener(response)
        with self.assertRaises(fulltext.FullTextError):
            fulltext.fetch_external(
                "https://example.org/large",
                timeout=10,
                max_bytes=10,
                opener=opener,
            )

    def test_private_targets_are_rejected(self):
        for url in (
            "http://example.org/paper",
            "https://localhost/paper",
            "https://127.0.0.1/paper",
            "https://10.0.0.2/paper",
        ):
            with self.subTest(url=url), self.assertRaises(fulltext.FullTextError):
                fulltext.validate_external_url(url)


class WorkflowTests(unittest.TestCase):
    def test_sparse_pdf_uses_raw_artifact_as_content_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            body = b"%PDF-1.7\nscan"
            candidate = fulltext.Candidate(
                source="ads",
                version="scan",
                format="pdf",
                url="https://example.org/scan.pdf",
                priority=70,
                link_type="ESOURCE|ADS_PDF",
                license=None,
                access="open",
            )
            response = ChunkedResponse(body, headers={"Content-Type": "application/pdf"})
            with (
                patch.object(fulltext, "pdf_page_count", return_value=(12, "test")),
                patch.object(
                    fulltext,
                    "extract_pdf_text",
                    return_value=("page 1", "pdftotext", None),
                ),
            ):
                result = fulltext.materialize_candidate(
                    candidate,
                    Path(temporary),
                    None,
                    timeout=10,
                    max_bytes=1000,
                    environ={},
                    opener=RecordingOpener(response),
                )

            self.assertEqual(result["status"], "needs_visual_reading")
            self.assertEqual(result["content_sha256"], fulltext.sha256_bytes(body))
            self.assertNotEqual(
                result["content_sha256"], fulltext.canonical_text_sha256("page 1")
            )

    def test_failed_html_refresh_preserves_existing_cached_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            record_dir = Path(temporary)
            body = b"<html><article>short</article></html>"
            artifact_hash = fulltext.sha256_bytes(body)
            artifact = (
                record_dir
                / "artifacts"
                / f"publisher-published-html-{artifact_hash[:16]}.html"
            )
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(body)
            candidate = fulltext.Candidate(
                source="publisher",
                version="published",
                format="html",
                url="https://example.org/article",
                priority=10,
                link_type="ESOURCE|PUB_HTML",
                license=None,
                access="open",
            )
            response = ChunkedResponse(body, headers={"Content-Type": "text/html"})

            with self.assertRaises(fulltext.FullTextError):
                fulltext.materialize_candidate(
                    candidate,
                    record_dir,
                    "Example article",
                    timeout=10,
                    max_bytes=1000,
                    environ={},
                    opener=RecordingOpener(response),
                )

            self.assertEqual(artifact.read_bytes(), body)

    def test_required_pdf_rejects_html_response(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate = fulltext.Candidate(
                source="publisher",
                version="published",
                format="pdf",
                url="https://example.org/article.pdf",
                priority=15,
                link_type="ESOURCE|PUB_PDF",
                license=None,
                access="open",
            )
            response = ChunkedResponse(
                b"<html><article>" + b"word " * 400 + b"</article></html>",
                headers={"Content-Type": "text/html"},
            )

            with self.assertRaisesRegex(fulltext.FullTextError, "pdf was required"):
                fulltext.materialize_candidate(
                    candidate,
                    Path(temporary),
                    None,
                    required_format="pdf",
                    timeout=10,
                    max_bytes=10000,
                    environ={},
                    opener=RecordingOpener(response),
                )

            self.assertEqual(list(Path(temporary).rglob("*")), [])

    def test_refresh_does_not_downgrade_a_cached_published_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache_root = Path(temporary)
            record_dir = cache_root / fulltext.cache_key("example")
            artifact = record_dir / "published.html"
            text_path = record_dir / "published.txt"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("published", encoding="utf-8")
            text_path.write_text("published text", encoding="utf-8")
            manifest_path = record_dir / "manifest-auto-resolver.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "fulltext",
                        "selected": {
                            "candidate": {
                                "version": "published",
                                "source": "publisher",
                            },
                            "artifact_path": str(artifact),
                            "text_path": str(text_path),
                            "sha256": fulltext.sha256_file(artifact),
                            "text_sha256": fulltext.sha256_file(text_path),
                            "content_sha256": fulltext.canonical_text_sha256(
                                text_path.read_text(encoding="utf-8")
                            ),
                        },
                    }
                ),
                encoding="utf-8",
            )
            preprint = fulltext.Candidate(
                source="arxiv",
                version="preprint",
                format="html",
                url="https://arxiv.org/html/1234.56789",
                priority=50,
                link_type="DIRECT|ARXIV_HTML",
                license=None,
                access="open",
            )
            discovery = {
                "input": "example",
                "input_type": "arxiv",
                "normalized_identifier": "1234.56789",
                "bibcode": None,
                "title": "Example",
                "abstract": "Abstract",
                "doi": [],
                "arxiv_ids": ["1234.56789"],
                "property": [],
                "doctype": None,
                "year": None,
                "pub": None,
                "candidates": [preprint],
                "warnings": [],
            }
            refreshed = {
                "candidate": fulltext.asdict(preprint),
                "actual_format": "html",
                "final_url": preprint.url,
                "artifact_path": "preprint.html",
                "text_path": "preprint.txt",
                "sha256": "abc",
                "bytes": 10,
                "content_type": "text/html",
                "retrieved_at": "now",
                "status": "fulltext",
                "statistics": {"words": 1000},
                "warnings": [],
            }
            with (
                patch.object(fulltext, "discover", return_value=discovery),
                patch.object(fulltext, "materialize_candidate", return_value=refreshed),
            ):
                result = fulltext.fetch_one(
                    "example",
                    source="auto",
                    cache_root=cache_root,
                    refresh=True,
                    use_unpaywall=False,
                    timeout=10,
                    max_bytes=1000,
                    environ={},
                )
        self.assertEqual(result["selected"]["candidate"]["version"], "published")
        self.assertTrue(result["refresh"]["kept_cached_authority"])

    def test_html_failure_falls_back_to_pdf(self):
        candidates = fulltext.arxiv_candidates("1602.03837")
        discovery = {
            "input": "1602.03837",
            "input_type": "arxiv",
            "normalized_identifier": "1602.03837",
            "bibcode": None,
            "title": "Target title",
            "abstract": "Abstract",
            "doi": [],
            "arxiv_ids": ["1602.03837"],
            "property": [],
            "doctype": None,
            "year": None,
            "pub": None,
            "candidates": candidates,
            "warnings": [],
        }
        pdf_result = {
            "candidate": fulltext.asdict(candidates[1]),
            "actual_format": "pdf",
            "final_url": candidates[1].url,
            "artifact_path": "paper.pdf",
            "text_path": "paper.txt",
            "sha256": "abc",
            "bytes": 10,
            "content_type": "application/pdf",
            "retrieved_at": "now",
            "status": "fulltext",
            "statistics": {"words": 1000},
            "warnings": [],
        }
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(fulltext, "discover", return_value=discovery),
            patch.object(
                fulltext,
                "materialize_candidate",
                side_effect=[
                    fulltext.FullTextError("HTTP 404"),
                    pdf_result,
                ],
            ),
        ):
            manifest = fulltext.fetch_one(
                "1602.03837",
                source="arxiv",
                cache_root=Path(temporary),
                refresh=True,
                use_unpaywall=False,
                timeout=10,
                max_bytes=1000,
                environ={},
            )
        self.assertEqual(manifest["status"], "fulltext")
        self.assertEqual(
            [attempt["status"] for attempt in manifest["attempts"]],
            ["failed", "fulltext"],
        )

    def test_cached_manifest_requires_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "paper.pdf"
            text = root / "paper.txt"
            artifact.write_bytes(b"%PDF-")
            text.write_text("full text", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "fulltext",
                        "selected": {
                            "artifact_path": str(artifact),
                            "text_path": str(text),
                            "sha256": fulltext.sha256_file(artifact),
                            "text_sha256": fulltext.sha256_file(text),
                            "content_sha256": fulltext.canonical_text_sha256(
                                text.read_text(encoding="utf-8")
                            ),
                        }
                    }
                ),
                encoding="utf-8",
            )
            cached = fulltext.cached_result(manifest_path)
            self.assertIsNotNone(cached)
            assert cached
            self.assertTrue(cached["cache_hit"])
            text.unlink()
            self.assertIsNone(fulltext.cached_result(manifest_path))

    def test_cached_manifest_rejects_modified_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "paper.html"
            text = root / "paper.txt"
            artifact.write_text("original artifact", encoding="utf-8")
            text.write_text("original full text", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "status": "fulltext",
                        "selected": {
                            "artifact_path": str(artifact),
                            "text_path": str(text),
                            "sha256": fulltext.sha256_file(artifact),
                            "text_sha256": fulltext.sha256_file(text),
                            "content_sha256": fulltext.canonical_text_sha256(
                                text.read_text(encoding="utf-8")
                            ),
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNotNone(fulltext.cached_result(manifest_path))
            text.write_text("modified full text", encoding="utf-8")
            self.assertIsNone(fulltext.cached_result(manifest_path))

    def test_page_ranges_are_limited_to_twenty_pages(self):
        self.assertEqual(fulltext.parse_page_range("3-20"), (3, 20))
        with self.assertRaises(fulltext.FullTextError):
            fulltext.parse_page_range("1-21")


if __name__ == "__main__":
    unittest.main()
