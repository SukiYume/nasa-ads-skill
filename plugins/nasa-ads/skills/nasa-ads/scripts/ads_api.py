#!/usr/bin/env python3
"""Thin, dependency-free command-line client for stable NASA ADS API calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = "1.12.1"
API_BASE_URL = "https://api.adsabs.harvard.edu/v1"
TOKEN_URL = "https://ui.adsabs.harvard.edu/#user/settings/token"
DEFAULT_FIELDS = (
    "bibcode,title,author,abstract,year,pub,doi,identifier,"
    "citation_count,read_count,property,doctype"
)
DEFAULT_METRIC_TYPES = ("basic", "citations", "indicators")
EXPORT_FORMATS = (
    "bibtex",
    "bibtexabs",
    "ads",
    "endnote",
    "procite",
    "ris",
    "refworks",
    "medlars",
    "aastex",
    "icarus",
    "mnras",
    "soph",
    "dcxml",
    "refxml",
    "refabsxml",
    "votable",
    "rss",
    "ieee",
)
METRIC_TYPES = ("basic", "citations", "indicators", "histograms", "timeseries")
HISTOGRAM_TYPES = ("publications", "reads", "downloads", "citations")
RATE_LIMIT_HEADERS = (
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)


class CliError(Exception):
    """A concise, user-facing error with a stable process exit code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class ApiResponse:
    body: bytes
    headers: Mapping[str, str]


class RejectRedirectHandler(HTTPRedirectHandler):
    """Keep ADS credentials on the configured API origin."""

    def redirect_request(
        self,
        _request: Request,
        _file_pointer: Any,
        _code: int,
        _message: str,
        _headers: Mapping[str, str],
        _new_url: str,
    ) -> None:
        return None


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def rows_int(value: str) -> int:
    number = positive_int(value)
    if number > 2000:
        raise argparse.ArgumentTypeError("must be at most 2000")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be at least 0")
    return number


def bounded_timeout(value: str) -> float:
    number = float(value)
    if not 1 <= number <= 300:
        raise argparse.ArgumentTypeError("must be between 1 and 300 seconds")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Call stable, read-only NASA ADS API workflows. Research decisions "
            "and result synthesis remain in the nasa-ads skill instructions."
        )
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--timeout",
        type=bounded_timeout,
        default=30.0,
        help="request timeout in seconds (default: 30; range: 1-300)",
    )
    parser.add_argument(
        "--show-rate-limit",
        action="store_true",
        help="write ADS rate-limit response headers to stderr",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="search ADS literature")
    search.add_argument("-q", "--query", required=True, help="native ADS query")
    search.add_argument(
        "--fields",
        "--fl",
        default=DEFAULT_FIELDS,
        help="comma-separated fields to return",
    )
    search.add_argument("--rows", type=rows_int, default=10)
    search.add_argument("--start", type=nonnegative_int, default=0)
    search.add_argument("--sort", help='sort expression, for example "date desc"')
    search.add_argument(
        "--filter",
        "--fq",
        action="append",
        default=[],
        help="filter query; repeat for multiple fq values",
    )

    bigquery = subparsers.add_parser(
        "bigquery", help="look up many ADS bibcodes through the big-query endpoint"
    )
    bigquery.add_argument("bibcodes", nargs="*", help="bibcodes to look up")
    bigquery.add_argument(
        "--bibcodes-file",
        help="UTF-8 file containing one bibcode per line; use - for stdin",
    )
    bigquery.add_argument("-q", "--query", default="*:*", help="main ADS query")
    bigquery.add_argument("--fields", "--fl", default="bibcode,title")
    bigquery.add_argument("--rows", type=rows_int, default=2000)
    bigquery.add_argument("--start", type=nonnegative_int, default=0)
    bigquery.add_argument("--sort")
    bigquery.add_argument(
        "--filter",
        "--fq",
        action="append",
        default=[],
        help="additional filter query; repeat for multiple values",
    )

    export = subparsers.add_parser("export", help="export citations")
    export.add_argument("bibcodes", nargs="+")
    export.add_argument(
        "--format",
        choices=EXPORT_FORMATS,
        default="bibtex",
        help="citation format (default: bibtex)",
    )
    export.add_argument("--sort", help="ADS export sort expression")

    metrics = subparsers.add_parser("metrics", help="retrieve aggregate metrics")
    metrics.add_argument("bibcodes", nargs="+")
    metrics.add_argument(
        "--type",
        dest="types",
        choices=METRIC_TYPES,
        action="append",
        help="metric type; repeat as needed (default: basic, citations, indicators)",
    )
    metrics.add_argument(
        "--histogram",
        choices=HISTOGRAM_TYPES,
        action="append",
        help="histogram category; repeat as needed",
    )

    suggest = subparsers.add_parser(
        "suggest", help="suggest potentially missing citations"
    )
    suggest.add_argument(
        "bibcodes",
        nargs="+",
        help="two or more bibcodes that define the existing bibliography",
    )

    resolve = subparsers.add_parser(
        "resolve", help="resolve full-text, data, and related resource links"
    )
    resolve.add_argument("bibcode")
    resolve.add_argument(
        "--link-type",
        help="optional resolver type such as esource, data, citations, or references",
    )

    return parser


def resolve_token(environ: Mapping[str, str]) -> str:
    primary = environ.get("ADS_API_TOKEN", "").strip()
    fallback = environ.get("ADS_DEV_KEY", "").strip()
    token = primary or fallback
    if not token:
        raise CliError(
            "Set ADS_API_TOKEN or ADS_DEV_KEY, then retry. "
            f"Create a token at {TOKEN_URL}",
            exit_code=2,
        )
    return token


def unique_nonempty(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(stripped)
    return result


def read_bibcodes_file(path: str, stdin: TextIO) -> list[str]:
    if path == "-":
        return unique_nonempty(stdin)
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return unique_nonempty(handle)
    except OSError as exc:
        raise CliError(f"Unable to read bibcode file {path!r}: {exc}") from exc


def build_url(path: str, query: Sequence[tuple[str, Any]] | None = None) -> str:
    url = f"{API_BASE_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"
    return url


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def concise_response_text(body: bytes, token: str) -> str:
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        detail = " ".join(text.split())
    else:
        if isinstance(payload, dict):
            detail = str(
                payload.get("error")
                or payload.get("message")
                or payload.get("detail")
                or payload
            )
        else:
            detail = str(payload)
    detail = " ".join(detail.split()).replace(token, "[redacted]")
    return detail[:800]


def application_error_text(body: bytes, token: str) -> str:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict) or not ("Error" in payload or "error" in payload):
        return ""

    parts = [
        payload.get("Error") or payload.get("error"),
        payload.get("Error Info") or payload.get("message") or payload.get("detail"),
    ]
    detail = ": ".join(str(part) for part in parts if part)
    detail = " ".join(detail.split()).replace(token, "[redacted]")
    return detail[:800] or "ADS returned an unspecified application error."


def format_rate_limit(headers: Mapping[str, str]) -> str:
    normalized = {name.lower(): value for name, value in headers.items()}
    values = []
    for name in RATE_LIMIT_HEADERS:
        value = normalized.get(name.lower())
        if value is not None:
            values.append(f"{name}={value}")
    return " ".join(values)


def request_api(
    method: str,
    path: str,
    token: str,
    *,
    query: Sequence[tuple[str, Any]] | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 30.0,
    opener: Any = None,
) -> ApiResponse:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
        "User-Agent": (
            f"nasa-ads-skill/{VERSION} (+https://github.com/SukiYume/nasa-ads-skill)"
        ),
    }
    if content_type:
        headers["Content-Type"] = content_type

    request = Request(
        build_url(path, query),
        data=body,
        headers=headers,
        method=method,
    )
    open_request = opener or build_opener(RejectRedirectHandler()).open
    try:
        with open_request(request, timeout=timeout) as response:
            response_body = response.read()
            detail = application_error_text(response_body, token)
            if detail:
                raise CliError(f"ADS API returned an application error. {detail}")
            return ApiResponse(
                body=response_body, headers=dict(response.headers.items())
            )
    except HTTPError as exc:
        response_body = exc.read()
        if 300 <= exc.code < 400:
            raise CliError(
                f"ADS API returned HTTP {exc.code} {exc.reason}; "
                "the redirect was not followed."
            ) from exc
        detail = concise_response_text(response_body, token)
        rate_limit = format_rate_limit(exc.headers or {})
        message = f"ADS API returned HTTP {exc.code} {exc.reason}."
        if detail:
            message = f"{message} {detail}"
        if rate_limit:
            message = f"{message} {rate_limit}"
        raise CliError(message) from exc
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise CliError(f"Unable to reach the ADS API: {reason}") from exc


def search_query(
    args: argparse.Namespace,
) -> tuple[str, list[tuple[str, Any]], bytes | None, str | None]:
    query: list[tuple[str, Any]] = [
        ("q", args.query),
        ("fl", args.fields),
        ("rows", args.rows),
        ("start", args.start),
    ]
    if args.sort:
        query.append(("sort", args.sort))
    query.extend(("fq", value) for value in args.filter)
    return "/search/query", query, None, None


def bigquery_request(
    args: argparse.Namespace, stdin: TextIO
) -> tuple[str, list[tuple[str, Any]], bytes, str]:
    bibcodes = list(args.bibcodes)
    if args.bibcodes_file:
        bibcodes.extend(read_bibcodes_file(args.bibcodes_file, stdin))
    bibcodes = unique_nonempty(bibcodes)
    if not bibcodes:
        raise CliError("Provide at least one bibcode or --bibcodes-file.", exit_code=2)

    query: list[tuple[str, Any]] = [
        ("q", args.query),
        ("fl", args.fields),
        ("rows", args.rows),
        ("start", args.start),
        ("fq", "{!bitset}"),
    ]
    if args.sort:
        query.append(("sort", args.sort))
    query.extend(("fq", value) for value in args.filter)
    body = ("bibcode\n" + "\n".join(bibcodes) + "\n").encode("utf-8")
    return "/search/bigquery", query, body, "big-query/csv"


def export_request(
    args: argparse.Namespace,
) -> tuple[str, str, list[tuple[str, Any]], bytes | None, str | None]:
    bibcodes = unique_nonempty(args.bibcodes)
    if not bibcodes:
        raise CliError("Provide at least one bibcode.", exit_code=2)
    encoded_format = quote(args.format, safe="")
    if len(bibcodes) == 1:
        encoded_bibcode = quote(bibcodes[0], safe="")
        return (
            "GET",
            f"/export/{encoded_format}/{encoded_bibcode}",
            [],
            None,
            None,
        )
    payload: dict[str, Any] = {"bibcode": bibcodes}
    if args.sort:
        payload["sort"] = args.sort
    return (
        "POST",
        f"/export/{encoded_format}",
        [],
        json_bytes(payload),
        "application/json",
    )


def metrics_request(
    args: argparse.Namespace,
) -> tuple[str, list[tuple[str, Any]], bytes, str]:
    bibcodes = unique_nonempty(args.bibcodes)
    if not bibcodes:
        raise CliError("Provide at least one bibcode.", exit_code=2)
    payload: dict[str, Any] = {
        "bibcodes": bibcodes,
        "types": args.types or list(DEFAULT_METRIC_TYPES),
    }
    if args.histogram:
        if "histograms" not in payload["types"]:
            raise CliError("--histogram requires --type histograms.", exit_code=2)
        payload["histograms"] = args.histogram
    return "/metrics", [], json_bytes(payload), "application/json"


def suggest_request(
    args: argparse.Namespace,
) -> tuple[str, list[tuple[str, Any]], bytes, str]:
    bibcodes = unique_nonempty(args.bibcodes)
    if len(bibcodes) < 2:
        raise CliError(
            "Citation helper requires at least two distinct bibcodes.", exit_code=2
        )
    payload = {"bibcodes": bibcodes}
    return "/citation_helper", [], json_bytes(payload), "application/json"


def resolve_path(args: argparse.Namespace) -> str:
    path = f"/resolver/{quote(args.bibcode, safe='')}"
    if args.link_type:
        path = f"{path}/{quote(args.link_type, safe=':')}"
    return path


def decode_json_response(response: ApiResponse, label: str) -> Any:
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(f"ADS returned an invalid {label} response.") from exc


def write_json(value: Any, stdout: TextIO) -> None:
    json.dump(value, stdout, ensure_ascii=False, indent=2)
    stdout.write("\n")


def execute(
    args: argparse.Namespace,
    token: str,
    *,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    opener: Any = None,
) -> None:
    if args.command == "search":
        path, query, body, content_type = search_query(args)
        response = request_api(
            "GET",
            path,
            token,
            query=query,
            body=body,
            content_type=content_type,
            timeout=args.timeout,
            opener=opener,
        )
        write_json(decode_json_response(response, "search"), stdout)
    elif args.command == "bigquery":
        path, query, body, content_type = bigquery_request(args, stdin)
        response = request_api(
            "POST",
            path,
            token,
            query=query,
            body=body,
            content_type=content_type,
            timeout=args.timeout,
            opener=opener,
        )
        write_json(decode_json_response(response, "big-query"), stdout)
    elif args.command == "export":
        method, path, query, body, content_type = export_request(args)
        response = request_api(
            method,
            path,
            token,
            query=query,
            body=body,
            content_type=content_type,
            timeout=args.timeout,
            opener=opener,
        )
        if method == "POST":
            payload = decode_json_response(response, "citation export")
            if not isinstance(payload, dict) or not isinstance(
                payload.get("export"), str
            ):
                raise CliError("ADS citation export response lacks an export field.")
            export_text = payload["export"]
        else:
            try:
                export_text = response.body.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CliError("ADS returned an invalid citation export.") from exc
        stdout.write(export_text)
        if not export_text.endswith("\n"):
            stdout.write("\n")
    elif args.command == "metrics":
        path, query, body, content_type = metrics_request(args)
        response = request_api(
            "POST",
            path,
            token,
            query=query,
            body=body,
            content_type=content_type,
            timeout=args.timeout,
            opener=opener,
        )
        write_json(decode_json_response(response, "metrics"), stdout)
    elif args.command == "suggest":
        path, query, body, content_type = suggest_request(args)
        response = request_api(
            "POST",
            path,
            token,
            query=query,
            body=body,
            content_type=content_type,
            timeout=args.timeout,
            opener=opener,
        )
        write_json(decode_json_response(response, "citation-helper"), stdout)
    elif args.command == "resolve":
        response = request_api(
            "GET",
            resolve_path(args),
            token,
            timeout=args.timeout,
            opener=opener,
        )
        write_json(decode_json_response(response, "resolver"), stdout)
    else:
        raise CliError(f"Unsupported command: {args.command}", exit_code=2)

    if args.show_rate_limit:
        rate_limit = format_rate_limit(response.headers)
        if rate_limit:
            stderr.write(f"{rate_limit}\n")


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    opener: Any = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    try:
        token = resolve_token(environ if environ is not None else os.environ)
        execute(
            args,
            token,
            stdin=input_stream,
            stdout=output_stream,
            stderr=error_stream,
            opener=opener,
        )
    except CliError as exc:
        error_stream.write(f"error: {exc}\n")
        return exc.exit_code
    return 0


def configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def main() -> None:
    configure_stdio()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
