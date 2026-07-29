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
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch


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

    def __enter__(self) -> "FakeResponse":
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
        args,
        environ=environ or {"ADS_API_TOKEN": "test-secret"},
        stdin=io.StringIO(stdin_text),
        stdout=stdout,
        stderr=stderr,
        opener=opener,
    )
    return code, stdout.getvalue(), stderr.getvalue(), opener


class TokenTests(unittest.TestCase):
    def test_primary_token_takes_precedence(self):
        token = ads_api.resolve_token(
            {"ADS_API_TOKEN": "primary", "ADS_DEV_KEY": "fallback"}
        )
        self.assertEqual(token, "primary")

    def test_legacy_token_is_used_as_fallback(self):
        token = ads_api.resolve_token(
            {"ADS_API_TOKEN": "  ", "ADS_DEV_KEY": " fallback "}
        )
        self.assertEqual(token, "fallback")

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
        self.assertIn("Set ADS_API_TOKEN or ADS_DEV_KEY", stderr.getvalue())


class ArgumentTests(unittest.TestCase):
    def test_rows_are_limited_to_ads_page_size(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as context:
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
        code, stdout, _, opener = run_cli(["suggest", "2016PhRvL.116f1102A"], response)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), [])
        self.assertEqual(
            json.loads(opener.requests[0].data),
            {"bibcodes": ["2016PhRvL.116f1102A"]},
        )

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
            with patch.object(
                ads_api,
                "API_BASE_URL",
                f"http://127.0.0.1:{redirect_server.server_port}",
            ):
                with self.assertRaises(ads_api.CliError) as context:
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


if __name__ == "__main__":
    unittest.main()
