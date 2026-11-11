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

    def test_outline_accepts_roman_sections_and_rejects_numeric_text_lines(self):
        article = """II Observations
II.1 Arecibo
III.3 Dispersion and Rotation Measures
I employ parallaxes from Gaia.
2017 to early 2020,
1970 and 2004 [20, 25].
0.976562 MHz channel bandwidth across 512 channels
1 from Effelsberg, 2 from the VLA, and 13 from Arecibo.
i) the first criterion
4 Discussion
"""
        self.assertEqual(
            fulltext.infer_text_outline(article),
            [
                "II Observations",
                "II.1 Arecibo",
                "III.3 Dispersion and Rotation Measures",
                "4 Discussion",
            ],
        )

    def test_outline_rejects_equation_and_table_fragments(self):
        article = """2 Data and models
1 + z 1028 cm
2 = 4.916) for the TPL model; and
2 = 3.529) is
10 3 p = 10 4
5. $\\tau_{s}$ ranges between 2.4 and 1.25 ms in the band
3 ($11\\leq\\log(M_{*}/M_{\\odot})\\leq 11.5$)
III.1.1 2025 October
5.2 21 cm power spectrum at z = 2
6 Conclusions
"""
        self.assertEqual(
            fulltext.infer_text_outline(article),
            [
                "2 Data and models",
                "III.1.1 2025 October",
                "5.2 21 cm power spectrum at z = 2",
                "6 Conclusions",
            ],
        )

    def test_pdf_manifest_outline_is_inferred_again_from_the_text(self):
        text = "1 Introduction\nBody.\n2 = 3.529) is\nMore body.\n2 Results\nEnd.\n"
        stored = ["1 Introduction", "2 = 3.529) is", "2 Results"]

        def headings(actual_format):
            manifest = {
                "selected": {
                    "actual_format": actual_format,
                    "statistics": {"outline": stored},
                }
            }
            return [s["heading"] for s in fulltext.article_outline(text, manifest)]

        self.assertEqual(headings("pdf"), ["1 Introduction", "2 Results"])
        # Headings of an HTML source come from its markup and are kept as stored.
        self.assertEqual(headings("html"), stored)

    def test_outline_skips_a_leading_table_of_contents(self):
        article = """Article contents
Abstract
Introduction
Discussion
References
Title of the paper
Abstract
We present a model.
1. Introduction
Context.
2. Methods
4. Discussion
References
Author, A. 2020, ApJ, 1, 1
Appendix A. Derivation
"""
        self.assertEqual(
            fulltext.infer_text_outline(article),
            [
                "Abstract",
                "1. Introduction",
                "2. Methods",
                "4. Discussion",
                "References",
                "Appendix A. Derivation",
            ],
        )

    def test_outline_cli_uses_html_headings_from_a_manifest(self):
        article = "Page chrome\nModelling spectra\nWe fit.\nCase studies\nTwo bursts.\n"
        with tempfile.TemporaryDirectory() as temporary:
            text_path = Path(temporary) / "article.txt"
            text_path.write_text(article, encoding="utf-8")
            manifest_path = Path(temporary) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "selected": {
                            "text_path": str(text_path),
                            "statistics": {"outline": ["Modelling spectra", "Case studies"]},
                        }
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()
            code = fulltext.run(["outline", str(manifest_path)], stdout=output)
        self.assertEqual(code, 0)
        self.assertEqual(
            [item["heading"] for item in json.loads(output.getvalue())["sections"]],
            ["Front matter", "Modelling spectra", "Case studies"],
        )

    def test_outline_cli_reports_section_lines_for_partial_reading(self):
        article = (
            "Title of the article\nAuthor list\n"
            "1 Introduction\nContext.\n\n"
            "2 Methods\nWe fit a model.\nIt converges.\n\n"
            "References\nAuthor, A. 2020, ApJ, 1, 1\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            text_path = Path(temporary) / "article.txt"
            text_path.write_text(article, encoding="utf-8")
            output = io.StringIO()
            code = fulltext.run(["outline", str(text_path)], stdout=output)
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["lines"], article.count("\n") + 1)
        self.assertEqual(
            [(item["heading"], item["line"], item["lines"]) for item in result["sections"]],
            [
                ("Front matter", 1, 2),
                ("1 Introduction", 3, 3),
                ("2 Methods", 6, 4),
                ("References", 10, 3),
            ],
        )
        self.assertEqual(result["sections"][2]["words"], 8)
        lines = article.split("\n")
        self.assertEqual(lines[result["sections"][3]["line"] - 1], "References")

    def test_access_page_is_rejected(self):
        body = (
            "<html><main><h1>Access denied</h1><p>Verify you are human. "
            + "word " * 350
            + "</p></main></html>"
        ).encode()
        with self.assertRaises(fulltext.FullTextError):
            fulltext.extract_html(body, None)

    def test_subscription_preview_with_long_references_is_rejected(self):
        references = "".join(
            f"<li>Author {index}, A study of bursts. Journal {index}, 1-10 (2015)</li>"
            for index in range(300)
        )
        body = (
            "<html><head><title>A repeating burst | Journal</title></head><body>"
            "<article><h1>A repeating burst</h1><h2>Abstract</h2><p>"
            + "abstract words " * 120
            + "</p><p>This is a preview of subscription content, access via your "
            "institution</p><h2>Access options</h2><p>Buy this article</p>"
            f"<h2>References</h2><ol>{references}</ol></article></body></html>"
        ).encode()
        with self.assertRaisesRegex(fulltext.FullTextError, "subscription preview"):
            fulltext.extract_html(body, "A repeating burst")

    def test_full_article_with_an_access_sidebar_is_accepted(self):
        paragraphs = " ".join(["measurement result evidence method"] * 500)
        body = (
            "<html><head><title>A repeating burst</title></head><body>"
            "<aside>Access through your institution</aside><article>"
            "<h1>A repeating burst</h1><h2>Introduction</h2>"
            f"<p>{paragraphs}</p><h2>Results</h2><p>{paragraphs}</p>"
            "<h2>References</h2><p>A. Example, 2026.</p></article></body></html>"
        ).encode()
        text, statistics = fulltext.extract_html(body, "A repeating burst")
        self.assertGreater(statistics["words"], 1500)

    def test_abstract_sized_landing_page_is_rejected(self):
        body = (
            "<html><body><h1>Paper title</h1><p>" + "word " * 400 + "</p></body></html>"
        ).encode()
        with self.assertRaises(fulltext.FullTextError):
            fulltext.extract_html(body, "Paper title")

    def test_landing_page_with_long_author_list_is_rejected(self):
        # Publisher abstract pages of large collaborations pass a word count
        # through their author and affiliation lists while the body loads later.
        authors = ", ".join(f"A. Author{index}{index % 9}" for index in range(1000))
        affiliations = "".join(
            f"<p>{index}Institute {index}, City {index}, Country</p>"
            for index in range(120)
        )
        references = "".join(
            f"<li>B. Cited{index}, Phys. Rev. Lett. {index}, 1 (2010).</li>"
            for index in range(118)
        )
        abstract = " ".join(["The detectors observed a transient signal."] * 30)
        body = (
            "<html><head><title>Observation of a merger</title></head><body><main>"
            f"<h1>Observation of a merger</h1><p>{authors}</p>{affiliations}"
            f"<h2>Abstract</h2><p>{abstract}</p><p>View figure in article</p>"
            "<h2>Article Text</h2><h2>References (118)</h2>"
            f"<ol>{references}</ol></main></body></html>"
        ).encode()
        with self.assertRaisesRegex(fulltext.FullTextError, "landing page"):
            fulltext.extract_html(body, "Observation of a merger")

    def test_body_prose_excludes_abstract_lists_and_references(self):
        abstract = " ".join(["We report a measured value of the spectral index."] * 10)
        body_paragraph = " ".join(["The fitted model describes the data well."] * 8)
        text = "\n\n".join(
            [
                "Contents\nAbstract\nReferences",
                "Title",
                "A. One, B. Two, C. Three, D. Four, E. Five, F. Six, G. Seven, H. Eight",
                "21Instituto de Física Teórica, Universidade Estadual Paulista and "
                "South American Institute for Fundamental Research, São Paulo SP Brazil",
                "Abstract",
                abstract,
                "1 Introduction",
                body_paragraph,
                "S. Chandrasekhar and S. L. Detweiler, Proc. R. Soc. A 344, 441 (1975).",
                "References (2)",
                body_paragraph,
            ]
        )
        self.assertEqual(
            fulltext.body_prose(text), (fulltext.count_words(body_paragraph), True)
        )

    def test_short_documents_without_an_abstract_are_not_landing_pages(self):
        telegram = " ".join(["We observed the source again and detected two bursts."] * 6)
        self.assertEqual(
            fulltext.body_prose(f"ATel #1\n\n{telegram}"),
            (fulltext.count_words(telegram), False),
        )
        self.assertFalse(fulltext.is_landing_page(*fulltext.body_prose(telegram)))

    def test_chinese_body_after_an_english_abstract_is_body_prose(self):
        abstract = " ".join(["We report a measured value of the spectral index."] * 10)
        body = "本文利用射电望远镜观测快速射电暴的偏振特性，并讨论其辐射机制。" * 30
        words, abstract_seen = fulltext.body_prose(
            f"Abstract\n\n{abstract}\n\n1 引言\n\n{body}"
        )
        self.assertTrue(abstract_seen)
        self.assertGreater(words, fulltext.MIN_BODY_PROSE_WORDS)

    def test_abstract_without_paragraph_breaks_keeps_its_excess_as_body(self):
        run_on = " ".join(["The spectral index of the burst emission is steep."] * 90)
        words, abstract_seen = fulltext.body_prose(f"Abstract\n{run_on}")
        self.assertTrue(abstract_seen)
        self.assertEqual(words, fulltext.count_words(run_on) - fulltext.ABSTRACT_SKIP_WORDS)


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

    def test_pdftotext_keeps_reading_order_for_two_column_pages(self):
        # Physical-layout mode puts both columns on one line, and whitespace
        # normalization would interleave them.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "paper.pdf"
            text = root / "paper.txt"
            pdf.write_bytes(b"%PDF-1.7\n")
            commands = []

            def extractor(command, **_kwargs):
                commands.append(command)
                text.write_text("I. INTRODUCTION\nBody text.\n", encoding="utf-8")
                return fulltext.subprocess.CompletedProcess(command, 0, "", "")

            with (
                patch.object(fulltext, "find_executable", return_value="pdftotext"),
                patch.object(fulltext.subprocess, "run", side_effect=extractor),
            ):
                extracted, _extractor, error = fulltext.extract_pdf_text(pdf, text, {})
        self.assertIsNone(error)
        self.assertEqual(extracted, "I. INTRODUCTION\nBody text.")
        self.assertNotIn("-layout", commands[0])
        _status, statistics, _warnings = fulltext.assess_pdf_text(
            "result method evidence " * 1000, 10, "pdftotext"
        )
        self.assertEqual(statistics["text_mode"], fulltext.PDF_TEXT_MODE)

    def test_lowercase_label_is_not_a_named_heading(self):
        outline = fulltext.infer_text_outline(
            "1 Introduction\nText.\ndata\nin\nResults\nMore text."
        )
        self.assertEqual(outline, ["1 Introduction", "Results"])

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

    def write_cached_selection(self, root, suffix, text_value, statistics):
        artifact = root / f"paper.{suffix}"
        text = root / "paper.txt"
        artifact.write_text("artifact", encoding="utf-8")
        text.write_text(text_value, encoding="utf-8")
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "status": "fulltext",
                    "selected": {
                        "actual_format": suffix,
                        "artifact_path": str(artifact),
                        "text_path": str(text),
                        "sha256": fulltext.sha256_file(artifact),
                        "text_sha256": fulltext.sha256_file(text),
                        "content_sha256": fulltext.canonical_text_sha256(text_value),
                        "statistics": statistics,
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest_path

    def test_cached_landing_page_is_retrieved_again(self):
        abstract = " ".join(["The detectors observed a transient signal."] * 30)
        body = " ".join(["The fitted model describes the data well."] * 60)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = {"text_mode": fulltext.HTML_TEXT_MODE}
            landing = self.write_cached_selection(
                root,
                "html",
                f"Title\n\nAbstract\n\n{abstract}\n\nReferences (118)",
                current,
            )
            self.assertIsNone(fulltext.cached_result(landing))
            # The cached artifact is no article, so it cannot be prepared again.
            self.assertIsNone(fulltext.prepare_cached_again(landing, {}))
            article = self.write_cached_selection(
                root,
                "html",
                f"Title\n\nAbstract\n\n{abstract}\n\n1 Introduction\n\n{body}",
                current,
            )
            self.assertIsNotNone(fulltext.cached_result(article))
            earlier = self.write_cached_selection(
                root,
                "html",
                f"Title\n\nAbstract\n\n{abstract}\n\n1 Introduction\n\n{body}",
                {},
            )
            self.assertIsNone(fulltext.cached_result(earlier))

    def test_cached_pdf_text_from_layout_extraction_is_retrieved_again(self):
        text_value = "result method evidence " * 400
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            layout = self.write_cached_selection(
                root, "pdf", text_value, {"extractor": "pdftotext"}
            )
            self.assertIsNone(fulltext.cached_result(layout))
            current = self.write_cached_selection(
                root, "pdf", text_value, {"text_mode": fulltext.PDF_TEXT_MODE}
            )
            self.assertIsNotNone(fulltext.cached_result(current))

    def test_reading_headings_fill_sections_joined_to_their_first_sentence(self):
        text = "\n".join(
            [
                "Front text",
                "I. INTRODUCTION",
                "Introduction body.",
                "matched-filter analyses and V. SEARCHES",
                # Reading-order extraction keeps a paragraph on one long line.
                "V. SEARCHES We searched the data with templates "
                + "covering the parameter space of the expected sources " * 4,
                "Search body.",
                "Results of the search are shown below.",
                "VI. SOURCE DISCUSSION",
                "Discussion body.",
            ]
        )
        sections = fulltext.article_outline(
            text,
            reading_headings=[
                "I. Introduction",
                "V. Searches",
                "Results",
                "VI. Source Discussion",
            ],
        )
        placed = {section["heading"]: section["line"] for section in sections}
        self.assertEqual(placed["V. Searches"], 5)
        # Unnumbered headings need a whole line; prose starting with one is no heading.
        self.assertNotIn("Results", placed)
        self.assertNotIn("I. Introduction", placed)
        self.assertEqual(placed["I. INTRODUCTION"], 2)
        self.assertEqual(placed["VI. SOURCE DISCUSSION"], 8)

    def test_page_ranges_are_limited_to_twenty_pages(self):
        self.assertEqual(fulltext.parse_page_range("3-20"), (3, 20))
        with self.assertRaises(fulltext.FullTextError):
            fulltext.parse_page_range("1-21")


ABSTRACT_TEXT = " ".join(["The detectors observed a transient signal."] * 30)
BODY_TEXT = " ".join(["The fitted model describes the data well."] * 60)


def article_html(title="Magnetar bursts", extra=""):
    return (
        f"<html><head><title>{title}</title></head><body><article>"
        f"<h1>{title}</h1><h2>Abstract</h2><p>{ABSTRACT_TEXT}</p>"
        f"<h2>1 Introduction</h2><p>{BODY_TEXT} {extra}</p>"
        "</article></body></html>"
    )


class MathMarkupTests(unittest.TestCase):
    def parse(self, html):
        parser = fulltext.ReadableHTMLParser()
        parser.feed(html)
        return parser.full_text()

    def test_superscripts_and_subscripts_keep_their_position(self):
        self.assertEqual(
            self.parse(
                "<p>B/P &gt; 2 × 10<sup>16</sup> G s<sup>−1</sup> and "
                "n<sub>e</sub> ~ 10<sup>5</sup> cm<sup>-3</sup>.</p>"
            ),
            "B/P > 2 × 10^{16} G s^{−1} and n_{e} ~ 10^{5} cm^{-3}.",
        )

    def test_empty_and_unclosed_scripts_end_at_their_block(self):
        self.assertEqual(
            self.parse("<p>value<sup> </sup> next</p><p>H<sub>2</p><p>tail</p>"),
            "value next\n\nH_{2}\n\ntail",
        )

    def test_mathml_contributes_its_tex(self):
        html = (
            r'<p>The luminosity is <math alttext="L=3.2\times 10^{42}" display="inline">'
            r"<semantics><mrow><mi>L</mi><mo>=</mo><mn>3.2</mn></mrow>"
            r'<annotation encoding="application/x-tex">L=3.2\times 10^{42}</annotation>'
            r"</semantics></math> erg.</p>"
        )
        self.assertEqual(self.parse(html), r"The luminosity is $L=3.2\times 10^{42}$ erg.")
        annotated = (
            "<p>Density <math><semantics><msup><mn>10</mn><mn>5</mn></msup>"
            '<annotation encoding="application/x-tex">10^{5}</annotation>'
            "</semantics></math>.</p>"
        )
        self.assertEqual(self.parse(annotated), "Density $10^{5}$.")

    def test_mathml_without_tex_keeps_scripts_fractions_and_roots(self):
        html = (
            "<p>A <math><msup><mn>10</mn><mn>42</mn></msup></math> and "
            "<math><mfrac><mi>a</mi><mi>b</mi></mfrac></math> and "
            "<math><msubsup><mi>x</mi><mi>i</mi><mn>2</mn></msubsup></math> and "
            "<math><msqrt><mi>y</mi></msqrt></math>.</p>"
        )
        self.assertEqual(
            self.parse(html), "A 10^{42} and (a)/(b) and x_{i}^{2} and sqrt(y)."
        )

    def test_displayed_math_stands_on_its_own_line(self):
        html = (
            '<p>Energy</p><math display="block" alttext="E=mc^{2}"><mi>E</mi></math>'
            "<p>follows.</p>"
        )
        self.assertEqual(self.parse(html), "Energy\n\n$$E=mc^{2}$$\n\nfollows.")

    def test_tex_scripts_replace_formula_images(self):
        html = (
            r'<p>dispersion of <span><img alt="$-5\sim -3$" role="math"></span>'
            r'<script type="math/tex">-5\sim -3</script> km s<sup>−1</sup>.</p>'
            r'<img alt="Equation (1)">'
            r'<script type="math/tex; mode=display">\frac{d\rho}{dt}=0</script>'
            "<script>var tracker = 1;</script>"
        )
        self.assertEqual(
            self.parse(html),
            "dispersion of $-5\\sim -3$ km s^{−1}.\n\n$$\\frac{d\\rho}{dt}=0$$",
        )

    def test_prose_detection_reads_past_math_markup(self):
        paragraph = (
            "We find that $L=3.2\\times 10^{42}$ erg s^{-1} for the burst, and the "
            "spectrum of the source steepens toward the lower band"
        )
        self.assertTrue(fulltext.is_prose(paragraph))
        self.assertEqual(fulltext.prose_words(paragraph), 19)

    def test_extracted_html_records_its_text_mode(self):
        text, statistics = fulltext.extract_html(
            article_html(extra="The field exceeds 2 × 10<sup>16</sup> G.").encode(),
            "Magnetar bursts",
        )
        self.assertEqual(statistics["text_mode"], fulltext.HTML_TEXT_MODE)
        self.assertIn("2 × 10^{16} G", text)


class CachedPreparationTests(unittest.TestCase):
    identifier = "arXiv:2401.00001"

    def cached_selection(self, cache_root, body, suffix, statistics, title):
        record_dir = cache_root / fulltext.cache_key(self.identifier)
        artifact = record_dir / "artifacts" / f"arxiv-preprint-{suffix}-0000.{suffix}"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(body)
        earlier_text = artifact.with_suffix(".txt")
        earlier_text.write_text("flattened 2 × 1016 G", encoding="utf-8")
        manifest_path = record_dir / "manifest-auto-resolver.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "status": "fulltext",
                    "input": self.identifier,
                    "normalized_identifier": "2401.00001",
                    "title": title,
                    "warnings": ["selected_fulltext_is_preprint"],
                    "selected": {
                        "candidate": {
                            "source": "arxiv",
                            "version": "preprint",
                            "format": suffix,
                            "url": f"https://arxiv.org/{suffix}/2401.00001",
                            "priority": 10,
                        },
                        "actual_format": suffix,
                        "final_url": f"https://arxiv.org/{suffix}/2401.00001",
                        "artifact_path": str(artifact),
                        "text_path": str(earlier_text),
                        "sha256": fulltext.sha256_file(artifact),
                        "text_sha256": fulltext.sha256_file(earlier_text),
                        "content_sha256": fulltext.canonical_text_sha256(
                            earlier_text.read_text(encoding="utf-8")
                        ),
                        "statistics": statistics,
                        "retrieved_at": "2026-01-01T00:00:00Z",
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest_path, earlier_text

    def fetch(self, cache_root):
        with patch.object(
            fulltext, "discover", side_effect=AssertionError("network request")
        ):
            return fulltext.fetch_one(
                self.identifier,
                source="auto",
                cache_root=cache_root,
                refresh=False,
                use_unpaywall=False,
                timeout=5,
                max_bytes=10_000_000,
                environ={},
            )

    def test_cached_html_from_an_earlier_extraction_is_prepared_again_locally(self):
        html = article_html(extra="The field exceeds 2 × 10<sup>16</sup> G.")
        with tempfile.TemporaryDirectory() as temporary:
            cache_root = Path(temporary)
            manifest_path, earlier_text = self.cached_selection(
                cache_root, html.encode(), "html", {"words": 10}, "Magnetar bursts"
            )
            result = self.fetch(cache_root)
            selected = result["selected"]
            self.assertEqual(selected["statistics"]["text_mode"], fulltext.HTML_TEXT_MODE)
            self.assertIn(
                "10^{16}", Path(selected["text_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(selected["retrieved_at"], "2026-01-01T00:00:00Z")
            self.assertTrue(result["cache_hit"])
            self.assertIn("text_prepared_again_from_cached_artifact", result["warnings"])
            self.assertIn("selected_fulltext_is_preprint", result["warnings"])
            # Earlier text stays in place for manifests that still name it.
            self.assertEqual(
                earlier_text.read_text(encoding="utf-8"), "flattened 2 × 1016 G"
            )
            self.assertIsNotNone(fulltext.cached_result(manifest_path))

    def test_cached_pdf_from_layout_extraction_is_prepared_again_locally(self):
        text = "Pulsar timing " + "residuals constrain the binary orbit well " * 60
        with tempfile.TemporaryDirectory() as temporary:
            cache_root = Path(temporary)
            self.cached_selection(
                cache_root,
                b"%PDF-1.4 cached article",
                "pdf",
                {"extractor": "pdftotext", "pages": 10},
                "Pulsar timing",
            )
            with patch.object(
                fulltext, "pdf_page_count", return_value=(10, "pdfinfo")
            ), patch.object(
                fulltext, "extract_pdf_text", return_value=(text, "pdftotext", None)
            ) as extract:
                result = self.fetch(cache_root)
            extract.assert_called_once()
            self.assertEqual(result["status"], "fulltext")
            self.assertEqual(
                result["selected"]["statistics"]["text_mode"], fulltext.PDF_TEXT_MODE
            )

    def test_cached_artifact_that_no_longer_validates_is_retrieved_again(self):
        landing = (
            "<html><head><title>Magnetar bursts</title></head><body><article>"
            f"<h1>Magnetar bursts</h1><h2>Abstract</h2><p>{ABSTRACT_TEXT}</p>"
            "<h2>References</h2></article></body></html>"
        )
        with tempfile.TemporaryDirectory() as temporary:
            cache_root = Path(temporary)
            manifest_path, _text = self.cached_selection(
                cache_root, landing.encode(), "html", {}, "Magnetar bursts"
            )
            self.assertIsNone(fulltext.prepare_cached_again(manifest_path, {}))
            with self.assertRaisesRegex(AssertionError, "network request"):
                self.fetch(cache_root)


DISCOVERED = {
    "input": "2017ApJ...834..199L",
    "input_type": "bibcode",
    "normalized_identifier": "2017ApJ...834..199L",
    "bibcode": "2017ApJ...834..199L",
    "title": "Magnetar bursts",
    "author": ["Lieu, Richard"],
    "abstract": "A model of fast radio bursts from young magnetars.",
    "doi": ["10.3847/1538-4357/834/2/199"],
    "arxiv_ids": [],
    "property": ["REFEREED"],
    "doctype": "article",
    "year": "2017",
    "pub": "The Astrophysical Journal",
    "citation_count": None,
    "read_count": None,
    "uat": [],
    "has": [],
    "volume": "834",
    "issue": "2",
    "page": ["199"],
    "eid": None,
    "pubdate": "2017-01-00",
    "requested_format": "auto",
    "candidates": [],
    "warnings": [],
}


class ImportTests(unittest.TestCase):
    def import_file(self, path, root, **kwargs):
        with patch.object(fulltext, "discover", return_value=dict(DISCOVERED)) as discover:
            manifest = fulltext.import_local(
                path,
                "2017ApJ...834..199L",
                version=kwargs.pop("version", "published"),
                source_url=kwargs.pop("source_url", None),
                cache_root=root / "cache",
                timeout=5,
                max_bytes=10_000_000,
                environ={},
            )
        return manifest, discover

    def test_user_supplied_html_becomes_a_full_text_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "Lieu 2017.html"
            path.write_text(article_html(), encoding="utf-8")
            manifest, discover = self.import_file(
                path, root, source_url="https://doi.org/10.3847/1538-4357/834/2/199"
            )
            self.assertFalse(discover.call_args.kwargs["find_candidates"])
            selected = manifest["selected"]
            self.assertEqual(manifest["status"], "fulltext")
            self.assertEqual(
                (selected["candidate"]["source"], selected["candidate"]["version"]),
                ("user", "published"),
            )
            self.assertEqual(
                selected["final_url"], "https://doi.org/10.3847/1538-4357/834/2/199"
            )
            self.assertEqual(manifest["volume"], "834")
            self.assertIn("user_supplied_artifact", manifest["warnings"])
            self.assertTrue(Path(manifest["manifest_path"]).is_file())
            self.assertTrue(Path(selected["text_path"]).is_file())
            # The local source path stays out of the manifest.
            self.assertNotIn(json.dumps(str(path))[1:-1], json.dumps(manifest))

    def test_import_checks_the_article_identity_and_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            other = root / "other.html"
            other.write_text(article_html(title="Solar wind turbulence"), encoding="utf-8")
            with self.assertRaisesRegex(fulltext.FullTextError, "title"):
                self.import_file(other, root)
            with self.assertRaisesRegex(fulltext.FullTextError, "HTTPS"):
                self.import_file(other, root, source_url="http://example.org/paper")
            with self.assertRaisesRegex(fulltext.FullTextError, "does not exist"):
                self.import_file(root / "missing.pdf", root)

    def test_import_command_captures_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "article.html"
            path.write_text(article_html(), encoding="utf-8")
            output = io.StringIO()
            with patch.object(fulltext, "discover", return_value=dict(DISCOVERED)):
                code = fulltext.run(
                    [
                        "import",
                        str(path),
                        "--identifier",
                        "2017ApJ...834..199L",
                        "--version",
                        "accepted",
                        "--cache-dir",
                        str(root / "cache"),
                        "--library-dir",
                        str(root / "library"),
                    ],
                    environ={},
                    stdout=output,
                )
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())["results"][0]
            self.assertEqual(result["selected"]["candidate"]["version"], "accepted")
            self.assertEqual(result["literature"]["status"], "captured")
            self.assertEqual(result["literature"]["unread_articles"], 1)
            self.assertTrue(
                any(
                    "the accepted version" in step and result["manifest_path"] in step
                    for step in result["literature"]["owed"]
                )
            )
            self.assertEqual(
                fulltext.prepared_article(result),
                {
                    "article_status": "fulltext",
                    "manifest_path": result["manifest_path"],
                    "version_kind": "accepted",
                    "artifact_sha256": result["selected"]["sha256"],
                    "content_sha256": result["selected"]["content_sha256"],
                    "arxiv_versions": [],
                },
            )
            self.assertEqual(
                fulltext.prepared_article({"status": "abstract_only", "selected": None}),
                {"article_status": "abstract_only", "manifest_path": None},
            )
            versioned = {
                "selected": {
                    "final_url": "https://arxiv.org/html/2304.14665v2",
                    "candidate": {"url": "https://arxiv.org/html/2304.14665V2"},
                }
            }
            self.assertEqual(
                fulltext.arxiv_version_labels(versioned), ["2304.14665v2"]
            )
            with self.assertRaises(SystemExit), patch("sys.stderr", io.StringIO()):
                fulltext.build_parser().parse_args(
                    ["import", str(path), "--identifier", "2017ApJ...834..199L"]
                )


class MetadataFieldTests(unittest.TestCase):
    def test_full_text_metadata_carries_the_bibliographic_fields_of_search(self):
        requests = []

        def fake_request(method, path, token, *, query=None, timeout=None, **_kwargs):
            requests.append(dict(query))
            body = {
                "response": {
                    "docs": [
                        {
                            "bibcode": "2017ApJ...834..199L",
                            "title": ["Magnetar bursts"],
                            "volume": "834",
                            "issue": "2",
                            "page": ["199"],
                            "eid": "199",
                            "pubdate": "2017-01-00",
                        }
                    ]
                }
            }
            return fulltext.ads_api.ApiResponse(json.dumps(body).encode(), {})

        with patch.object(fulltext.ads_api, "request_api", side_effect=fake_request):
            discovered = fulltext.discover(
                "2017ApJ...834..199L",
                source="auto",
                use_unpaywall=False,
                timeout=5,
                max_bytes=1_000_000,
                environ={"ADS_API_TOKEN": "test-token"},
                find_candidates=False,
            )
        self.assertEqual(requests[0]["fl"], fulltext.ads_api.DEFAULT_FIELDS)
        self.assertEqual(len(requests), 1)
        self.assertEqual(
            {field: discovered[field] for field in ("volume", "issue", "page", "eid", "pubdate")},
            {"volume": "834", "issue": "2", "page": ["199"], "eid": "199", "pubdate": "2017-01-00"},
        )
        self.assertEqual(discovered["candidates"], [])



class DiscoveryAndCacheTests(unittest.TestCase):
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
