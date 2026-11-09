from __future__ import annotations

import importlib.util
import io
import json
import sys
import threading
import unittest
from contextlib import redirect_stderr
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / "plugins"
    / "nasa-ads"
    / "skills"
    / "nasa-ads"
    / "scripts"
    / "ads_api.py"
)
SPEC = importlib.util.spec_from_file_location("ads_api", SCRIPT_PATH)
assert SPEC and SPEC.loader
ads_api = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ads_api
SPEC.loader.exec_module(ads_api)


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self.headers = Message()
        for name, value in (headers or {}).items():
            self.headers[name] = value

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class RecordingOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests = []
        self.timeouts = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.response


def run_cli(args, response, *, environ=None, stdin_text=""):
    stdout = io.StringIO()
    stderr = io.StringIO()
    opener = RecordingOpener(response)
    code = ads_api.run(
        ["--no-store", *args],
        environ=environ or {"ADS_API_TOKEN": "test-secret"},
        stdin=io.StringIO(stdin_text),
        stdout=stdout,
        stderr=stderr,
        opener=opener,
    )
    return code, stdout.getvalue(), stderr.getvalue(), opener


class TokenTests(unittest.TestCase):
    def test_token_is_stripped(self):
        self.assertEqual(
            ads_api.resolve_token({"ADS_API_TOKEN": " secret "}), "secret"
        )

    def test_retired_dev_key_is_not_read(self):
        with self.assertRaises(ads_api.CliError):
            ads_api.resolve_token({"ADS_DEV_KEY": "old"})

    def test_missing_token_returns_exit_two_without_request(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = ads_api.run(
            ["search", "--query", "stars"],
            environ={},
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Set ADS_API_TOKEN", stderr.getvalue())
        self.assertIn("https://scixplorer.org/user/settings/token", stderr.getvalue())


class ArgumentTests(unittest.TestCase):
    def test_rows_are_limited_to_ads_page_size(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as context:
            ads_api.build_parser().parse_args(
                ["search", "--query", "stars", "--rows", "2001"]
            )
        self.assertEqual(context.exception.code, 2)


class RequestTests(unittest.TestCase):
    def test_search_encodes_query_filters_and_pagination(self):
        response = FakeResponse(b'{"response":{"numFound":0,"docs":[]}}')
        code, stdout, stderr, opener = run_cli(
            [
                "search",
                "--query",
                'title:"A&B waves"',
                "--fields",
                "bibcode,title",
                "--rows",
                "25",
                "--start",
                "10",
                "--sort",
                "date desc",
                "--fq",
                "property:refereed",
                "--fq",
                "database:astronomy",
            ],
            response,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["response"]["numFound"], 0)
        request = opener.requests[0]
        parsed = urlsplit(request.full_url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "api.scixplorer.org")
        self.assertEqual(parsed.path, "/v1/search/query")
        self.assertEqual(query["q"], ['title:"A&B waves"'])
        self.assertEqual(query["fq"], ["property:refereed", "database:astronomy"])
        self.assertEqual(query["rows"], ["25"])
        self.assertEqual(query["start"], ["10"])
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertNotIn("test-secret", request.full_url)

    def test_bigquery_builds_csv_body_and_bitset_filter(self):
        response = FakeResponse(b'{"response":{"numFound":2,"docs":[]}}')
        code, _, _, opener = run_cli(
            [
                "bigquery",
                "2016PhRvL.116f1102A",
                "2017ApJ...848L..12A",
                "--fq",
                "property:refereed",
            ],
            response,
        )
        self.assertEqual(code, 0)
        request = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Content-type"), "big-query/csv")
        self.assertEqual(
            request.data,
            (b"bibcode\n2016PhRvL.116f1102A\n2017ApJ...848L..12A\n"),
        )
        query = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(query["fq"], ["{!bitset}", "property:refereed"])

    def test_bigquery_reads_utf8_file_input_from_stdin(self):
        response = FakeResponse(b'{"response":{"numFound":1,"docs":[]}}')
        code, _, _, opener = run_cli(
            ["bigquery", "--bibcodes-file", "-"],
            response,
            stdin_text="2016PhRvL.116f1102A\n2016PhRvL.116f1102A\n\n",
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            opener.requests[0].data,
            b"bibcode\n2016PhRvL.116f1102A\n",
        )

    def test_single_export_uses_encoded_get_and_plain_output(self):
        response = FakeResponse(b"@article{example}\n")
        code, stdout, _, opener = run_cli(["export", "2012A&A...542A..16R"], response)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "@article{example}\n")
        request = opener.requests[0]
        self.assertEqual(request.method, "GET")
        self.assertTrue(
            request.full_url.endswith("/v1/export/bibtex/2012A%26A...542A..16R")
        )

    def test_multiple_export_posts_json_and_unwraps_export(self):
        response = FakeResponse(b'{"export":"entry one\\nentry two\\n"}')
        code, stdout, _, opener = run_cli(
            [
                "export",
                "2016PhRvL.116f1102A",
                "2017ApJ...848L..12A",
                "--format",
                "ris",
                "--sort",
                "first_author asc",
            ],
            response,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "entry one\nentry two\n")
        request = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(
            json.loads(request.data),
            {
                "bibcode": [
                    "2016PhRvL.116f1102A",
                    "2017ApJ...848L..12A",
                ],
                "sort": "first_author asc",
            },
        )

    def test_metrics_uses_defaults_and_histogram_validation(self):
        response = FakeResponse(b'{"basic stats":{"number of papers":1}}')
        code, _, _, opener = run_cli(["metrics", "2016PhRvL.116f1102A"], response)
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(opener.requests[0].data),
            {
                "bibcodes": ["2016PhRvL.116f1102A"],
                "types": ["basic", "citations", "indicators"],
            },
        )

        code, _, stderr, opener = run_cli(
            [
                "metrics",
                "2016PhRvL.116f1102A",
                "--histogram",
                "citations",
            ],
            response,
        )
        self.assertEqual(code, 2)
        self.assertIn("--histogram requires --type histograms", stderr)
        self.assertEqual(opener.requests, [])

    def test_suggest_posts_bibcodes(self):
        response = FakeResponse(b"[]")
        code, stdout, _, opener = run_cli(
            ["suggest", "2016PhRvL.116f1102A", "2017ApJ...848L..12A"], response
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), [])
        self.assertEqual(
            json.loads(opener.requests[0].data),
            {"bibcodes": ["2016PhRvL.116f1102A", "2017ApJ...848L..12A"]},
        )

    def test_suggest_rejects_single_bibcode(self):
        response = FakeResponse(b"[]")
        code, _, stderr, opener = run_cli(["suggest", "2016PhRvL.116f1102A"], response)
        self.assertEqual(code, 2)
        self.assertIn("at least two distinct bibcodes", stderr)
        self.assertEqual(opener.requests, [])

    def test_resolver_encodes_bibcode_and_link_type(self):
        response = FakeResponse(b"[]")
        code, _, _, opener = run_cli(
            [
                "resolve",
                "2012A&A...542A..16R",
                "--link-type",
                "doi:10.1051/example/path",
            ],
            response,
        )
        self.assertEqual(code, 0)
        self.assertTrue(
            opener.requests[0].full_url.endswith(
                "/v1/resolver/2012A%26A...542A..16R/doi:10.1051%2Fexample%2Fpath"
            )
        )

    def test_reference_resolution_batches_and_nulls_unresolved_bibcodes(self):
        references = [f"Author, A. 20{index:02d}, ApJ, {index}, 1" for index in range(17)]
        bodies = []
        for batch in (references[:16], references[16:]):
            entries = [
                {"refstring": value, "score": "1.0", "bibcode": f"2000ApJ.....{i}...1A"}
                for i, value in enumerate(batch)
            ]
            bodies.append(entries)
        bodies[1][0].update(score="0.0", bibcode="...................")
        responses = iter(
            FakeResponse(json.dumps({"resolved": entries}).encode()) for entries in bodies
        )

        class SequenceOpener(RecordingOpener):
            def __call__(self, request, timeout):
                self.requests.append(request)
                self.timeouts.append(timeout)
                return next(responses)

        opener = SequenceOpener(FakeResponse(b""))
        stdout = io.StringIO()
        code = ads_api.run(
            ["reference", "--references-file", "-"],
            environ={"ADS_API_TOKEN": "test-secret"},
            stdin=io.StringIO("\n".join(references) + "\n"),
            stdout=stdout,
            stderr=io.StringIO(),
            opener=opener,
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            [len(json.loads(request.data)["reference"]) for request in opener.requests],
            [16, 1],
        )
        self.assertTrue(opener.requests[0].full_url.endswith("/v1/reference/text"))
        self.assertEqual(opener.requests[0].get_header("Accept"), "application/json")
        self.assertEqual(opener.timeouts, [120.0, 120.0])
        payload = json.loads(stdout.getvalue())
        self.assertEqual((payload["count"], payload["resolved_count"]), (17, 16))
        self.assertIsNone(payload["resolved"][16]["bibcode"])

    def test_reference_resolution_requires_input(self):
        code, _, stderr, opener = run_cli(["reference"], FakeResponse(b"{}"))
        self.assertEqual(code, 2)
        self.assertIn("at least one reference", stderr)
        self.assertEqual(opener.requests, [])

    def test_objects_resolve_names_or_translate_queries(self):
        response = FakeResponse(b"{}")
        code, _, _, opener = run_cli(["objects", "M31", "Crab Nebula"], response)
        self.assertEqual(code, 0)
        self.assertTrue(opener.requests[0].full_url.endswith("/v1/objects"))
        self.assertEqual(
            json.loads(opener.requests[0].data), {"identifiers": ["M31", "Crab Nebula"]}
        )
        self.assertEqual(opener.timeouts, [30.0])
        code, _, _, opener = run_cli(["objects", "--query", "object:M31"], response)
        self.assertEqual(code, 0)
        self.assertTrue(opener.requests[0].full_url.endswith("/v1/objects/query"))
        self.assertEqual(json.loads(opener.requests[0].data), {"query": ["object:M31"]})
        code, _, stderr, opener = run_cli(
            ["objects", "M31", "--query", "object:M31"], response
        )
        self.assertEqual(code, 2)
        self.assertEqual(opener.requests, [])

    def test_journals_search_and_summary_paths(self):
        response = FakeResponse(b'{"journal": []}')
        code, _, _, opener = run_cli(["journals", "Monthly Notices"], response)
        self.assertEqual(code, 0)
        self.assertTrue(
            opener.requests[0].full_url.endswith("/v1/journals/journal/Monthly%20Notices")
        )
        code, _, _, opener = run_cli(["journals", "A&A", "--summary"], response)
        self.assertEqual(code, 0)
        self.assertTrue(opener.requests[0].full_url.endswith("/v1/journals/summary/A%26A"))

    def test_rate_limit_headers_are_optional_stderr_metadata(self):
        response = FakeResponse(
            b'{"response":{"numFound":0,"docs":[]}}',
            {
                "x-ratelimit-limit": "5000",
                "x-ratelimit-remaining": "4999",
                "x-ratelimit-reset": "1234567890",
            },
        )
        code, _, stderr, _ = run_cli(
            ["--show-rate-limit", "search", "-q", "stars"], response
        )
        self.assertEqual(code, 0)
        self.assertIn("X-RateLimit-Remaining=4999", stderr)


class ErrorTests(unittest.TestCase):
    def test_application_error_returns_nonzero(self):
        response = FakeResponse(
            b'{"Error":"Unable to get results!",'
            b'"Error Info":"No data available to generate metrics"}'
        )
        code, stdout, stderr, _ = run_cli(
            ["metrics", "2016PhRvL.116f1102A", "--type", "timeseries"],
            response,
        )
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("application error", stderr)
        self.assertIn("No data available to generate metrics", stderr)

    def test_redirect_is_rejected_before_token_reaches_target(self):
        forwarded_authorization = []

        class TargetHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                forwarded_authorization.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, _format, *_args):
                return None

        target_server = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
        target_thread = threading.Thread(
            target=target_server.serve_forever,
            daemon=True,
        )
        target_thread.start()
        target_url = (
            f"http://127.0.0.1:{target_server.server_port}/unexpected-destination"
        )

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", target_url)
                self.end_headers()

            def log_message(self, _format, *_args):
                return None

        redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        redirect_thread = threading.Thread(
            target=redirect_server.serve_forever,
            daemon=True,
        )
        redirect_thread.start()

        try:
            with (
                patch.object(
                    ads_api,
                    "API_BASE_URL",
                    f"http://127.0.0.1:{redirect_server.server_port}",
                ),
                self.assertRaises(ads_api.CliError) as context,
            ):
                ads_api.request_api(
                    "GET",
                    "/start",
                    "test-secret",
                    timeout=5,
                )
            self.assertIn("redirect was not followed", str(context.exception))
            self.assertEqual(forwarded_authorization, [])
        finally:
            redirect_server.shutdown()
            target_server.shutdown()
            redirect_server.server_close()
            target_server.server_close()
            redirect_thread.join(timeout=5)
            target_thread.join(timeout=5)

    def test_http_error_is_concise_and_redacts_token(self):
        headers = Message()
        headers["X-RateLimit-Remaining"] = "0"

        def failing_opener(request, timeout):
            self.assertEqual(timeout, 30.0)
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                headers,
                io.BytesIO(b'{"error":"test-secret exhausted"}'),
            )

        stdout = io.StringIO()
        stderr = io.StringIO()
        code = ads_api.run(
            ["search", "-q", "stars"],
            environ={"ADS_API_TOKEN": "test-secret"},
            stdout=stdout,
            stderr=stderr,
            opener=failing_opener,
        )
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("HTTP 429", stderr.getvalue())
        self.assertIn("[redacted] exhausted", stderr.getvalue())
        self.assertIn("X-RateLimit-Remaining=0", stderr.getvalue())
        self.assertNotIn("test-secret", stderr.getvalue())


def json_body(request):
    return json.loads(request.data.decode("utf-8"))


class LiteratureServiceTests(unittest.TestCase):
    def test_search_highlights_use_quoted_phrases_and_map_ids_to_bibcodes(self):
        response = FakeResponse(
            json.dumps(
                {
                    "response": {
                        "numFound": 2,
                        "docs": [
                            {"id": "11", "bibcode": "2017ApJ...834..199L"},
                            {"id": "12", "bibcode": "2018ApJ...111..222X"},
                        ],
                    },
                    "highlighting": {
                        "11": {"body": ["the <em>Schwinger mechanism</em> powers"]},
                        "12": {},
                    },
                }
            ).encode()
        )
        code, stdout, _, opener = run_cli(
            [
                "search",
                "--query",
                'full:"Schwinger mechanism" year:2017',
                "--fields",
                "bibcode",
                "--highlight",
                "body",
                "--param",
                "hl.fragsize=300",
            ],
            response,
        )
        self.assertEqual(code, 0)
        query = parse_qs(urlsplit(opener.requests[0].full_url).query)
        self.assertEqual(query["fl"], ["bibcode,id"])
        self.assertEqual(query["hl"], ["true"])
        self.assertEqual(query["hl.fl"], ["body"])
        self.assertEqual(query["hl.q"], ['"Schwinger mechanism"'])
        self.assertEqual(query["hl.snippets"], ["3"])
        self.assertEqual(query["hl.fragsize"], ["300"])
        self.assertEqual(
            json.loads(stdout)["highlights"],
            [
                {
                    "bibcode": "2017ApJ...834..199L",
                    "id": "11",
                    "fields": {"body": ["the <em>Schwinger mechanism</em> powers"]},
                }
            ],
        )

    def test_highlights_need_terms(self):
        response = FakeResponse(b'{"response":{"numFound":0,"docs":[]}}')
        code, _, stderr, opener = run_cli(
            ["search", "--query", "year:2017", "--highlight", "abstract"], response
        )
        self.assertEqual(code, 2)
        self.assertIn("--highlight-query", stderr)
        self.assertEqual(opener.requests, [])
        code, _, _, opener = run_cli(
            [
                "search",
                "--query",
                "year:2017",
                "--highlight",
                "abstract",
                "--highlight-query",
                "magnetar",
            ],
            response,
        )
        self.assertEqual(code, 0)
        query = parse_qs(urlsplit(opener.requests[0].full_url).query)
        self.assertEqual(query["hl.q"], ["magnetar"])

    def test_each_facet_and_statistics_field_gets_its_own_request(self):
        # The SciX gateway keeps one value per facet or statistics field.
        response = FakeResponse(
            json.dumps(
                {
                    "response": {"numFound": 5031, "docs": []},
                    "facet_counts": {
                        "facet_fields": {
                            "year": ["2025", 672],
                            "bibstem_facet": ["ApJ", 474],
                        }
                    },
                    "stats": {
                        "stats_fields": {
                            "citation_count": {"max": 1268.0},
                            "read_count": {"max": 900.0},
                        }
                    },
                }
            ).encode()
        )
        code, stdout, _, opener = run_cli(
            [
                "search",
                "--query",
                'abs:"fast radio burst"',
                "--rows",
                "0",
                "--fq",
                "year:2020",
                "--facet",
                "year",
                "--facet",
                "bibstem_facet",
                "--facet-limit",
                "5",
                "--stats",
                "citation_count",
                "--stats",
                "read_count",
                "--param",
                "facet.mincount=2",
            ],
            response,
        )
        self.assertEqual(code, 0)
        queries = [parse_qs(urlsplit(request.full_url).query) for request in opener.requests]
        self.assertEqual(len(queries), 3)
        self.assertEqual(queries[0]["rows"], ["0"])
        self.assertEqual(queries[0]["facet.field"], ["year"])
        self.assertEqual(queries[0]["stats.field"], ["citation_count"])
        self.assertEqual(queries[0]["facet.mincount"], ["2"])
        self.assertEqual(queries[1]["facet.field"], ["bibstem_facet"])
        self.assertEqual(queries[1]["facet.limit"], ["5"])
        self.assertEqual(queries[1]["facet.mincount"], ["2"])
        self.assertEqual(queries[1]["fq"], ["year:2020"])
        self.assertEqual(queries[1]["rows"], ["0"])
        self.assertEqual(queries[2]["stats.field"], ["read_count"])
        self.assertNotIn("facet", queries[2])
        merged = json.loads(stdout)
        self.assertEqual(
            sorted(merged["facet_counts"]["facet_fields"]), ["bibstem_facet", "year"]
        )
        self.assertEqual(
            sorted(merged["stats"]["stats_fields"]), ["citation_count", "read_count"]
        )

    def test_count_only_search_writes_nothing_to_the_library(self):
        import tempfile

        response = FakeResponse(b'{"response":{"numFound":7,"docs":[]}}')
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "library"
            stdout = io.StringIO()
            code = ads_api.run(
                ["--library-dir", str(library), "search", "-q", "stars", "--rows", "0"],
                environ={"ADS_API_TOKEN": "test-secret"},
                stdin=io.StringIO(),
                stdout=stdout,
                stderr=io.StringIO(),
                opener=RecordingOpener(response),
            )
            self.assertEqual(code, 0)
            self.assertNotIn("literature", json.loads(stdout.getvalue()))
            self.assertFalse(library.exists())

    def test_passthrough_parameters_cannot_replace_managed_options(self):
        response = FakeResponse(b'{"response":{"numFound":0,"docs":[]}}')
        for item in ("rows=5", "fq=year:2020", "facet.limit"):
            with self.subTest(item=item):
                code, _, stderr, opener = run_cli(
                    ["search", "--query", "stars", "--param", item], response
                )
                self.assertEqual(code, 2)
                self.assertEqual(opener.requests, [])

    def test_csl_and_custom_exports_post_their_formats(self):
        response = FakeResponse(b'{"msg":"ok","export":"Abbott, B. P. 2016, PhRvL"}')
        code, stdout, _, opener = run_cli(
            [
                "export",
                "2016PhRvL.116f1102A",
                "--format",
                "csl",
                "--style",
                "aastex",
                "--csl-format",
                "latex",
                "--journal-format",
                "full",
            ],
            response,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Abbott, B. P. 2016, PhRvL\n")
        request = opener.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertTrue(request.full_url.endswith("/v1/export/csl"))
        self.assertEqual(
            json_body(request),
            {
                "bibcode": ["2016PhRvL.116f1102A"],
                "style": "aastex",
                "format": 3,
                "journalformat": 3,
            },
        )
        code, _, _, opener = run_cli(
            ["export", "2016PhRvL.116f1102A", "--format", "custom", "--custom-format", "%R"],
            response,
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            json_body(opener.requests[0]),
            {"bibcode": ["2016PhRvL.116f1102A"], "format": "%R"},
        )

    def test_export_options_match_their_format(self):
        response = FakeResponse(b'{"export":""}')
        for args in (
            ["--format", "csl"],
            ["--format", "custom"],
            ["--format", "bibtex", "--style", "mnras"],
            ["--format", "bibtex", "--custom-format", "%R"],
            ["--format", "csl", "--style", "mnras", "--journal-format", "full"],
        ):
            with self.subTest(args=args):
                code, _, _, opener = run_cli(
                    ["export", "2016PhRvL.116f1102A", *args], response
                )
                self.assertEqual(code, 2)
                self.assertEqual(opener.requests, [])

    def test_network_and_word_cloud_requests(self):
        graph = FakeResponse(
            b'{"msg":{"numFound":2},"data":{"summaryGraph":{"nodes":[]},"fullGraph":{"nodes":[1,2]}}}'
        )
        code, stdout, _, opener = run_cli(
            ["network", "paper", "2016PhRvL.116f1102A", "2017ApJ...848L..12A"], graph
        )
        self.assertEqual(code, 0)
        self.assertTrue(opener.requests[0].full_url.endswith("/v1/vis/paper-network"))
        self.assertEqual(opener.timeouts, [120.0])
        self.assertEqual(
            json_body(opener.requests[0]),
            {"bibcodes": ["2016PhRvL.116f1102A", "2017ApJ...848L..12A"]},
        )
        trimmed = json.loads(stdout)
        self.assertNotIn("fullGraph", trimmed["data"])
        self.assertEqual(trimmed["omitted"], ["data.fullGraph"])
        code, stdout, _, _ = run_cli(
            ["network", "paper", "2016PhRvL.116f1102A", "--full"], graph
        )
        self.assertIn("fullGraph", json.loads(stdout)["data"])
        ungrouped = FakeResponse(b'{"msg":{"numFound":2},"data":{"fullGraph":{"nodes":[1]}}}')
        code, stdout, _, _ = run_cli(
            ["network", "paper", "2016PhRvL.116f1102A", "2017ApJ...848L..12A"], ungrouped
        )
        self.assertIn("fullGraph", json.loads(stdout)["data"])
        code, _, _, opener = run_cli(
            ["network", "author", "2016PhRvL.116f1102A"], graph
        )
        self.assertTrue(opener.requests[0].full_url.endswith("/v1/vis/author-network"))
        cloud = FakeResponse(b'{"magnetar":{"idf":2.1,"record_count":4}}')
        code, _, _, opener = run_cli(
            ["wordcloud", "--query", "abs:magnetar", "--rows", "50", "--sort", "date desc"],
            cloud,
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            json_body(opener.requests[0]),
            {"q": ["abs:magnetar"], "rows": [50], "sort": ["date desc"]},
        )
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ads_api.build_parser().parse_args(["wordcloud", "-q", "x", "--rows", "501"])

    def test_journal_summary_omits_completeness_unless_requested(self):
        summary = {
            "summary": {
                "master": {"bibstem": "MNRAS", "completeness_details": [{"volume": 1}]},
                "idents": [],
            }
        }
        response = FakeResponse(json.dumps(summary).encode())
        code, stdout, _, _ = run_cli(["journals", "MNRAS", "--summary"], response)
        self.assertEqual(code, 0)
        trimmed = json.loads(stdout)
        self.assertEqual(trimmed["summary"]["master"], {"bibstem": "MNRAS"})
        self.assertEqual(trimmed["omitted"], ["summary.master.completeness_details"])
        code, stdout, _, _ = run_cli(
            ["journals", "MNRAS", "--summary", "--completeness"], response
        )
        self.assertIn("completeness_details", json.loads(stdout)["summary"]["master"])


if __name__ == "__main__":
    unittest.main()
