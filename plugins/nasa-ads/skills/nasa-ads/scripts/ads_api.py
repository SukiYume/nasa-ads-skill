#!/usr/bin/env python3
"""Thin, dependency-free command-line client for stable SciX API calls."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = "3.2.0"
API_BASE_URL = "https://api.scixplorer.org/v1"
TOKEN_URL = "https://scixplorer.org/user/settings/token"
TOKEN_ENV = "ADS_API_TOKEN"
ABSTRACT_URL = "https://scixplorer.org/abs/{}/abstract"
DEFAULT_FIELDS = (
    "bibcode,title,author,abstract,year,pub,doi,identifier,"
    "citation_count,read_count,property,doctype,esources,volume,issue,page,eid,"
    "pubdate,uat,has"
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
    "csl",
    "custom",
)
CSL_STYLES = ("aastex", "icarus", "mnras", "soph", "aspc", "apsj", "aasj", "ieee")
CSL_FORMATS = {"unicode": 1, "html": 2, "latex": 3}
JOURNAL_FORMATS = {"macros": 1, "abbreviations": 2, "full": 3}
JOURNAL_FORMAT_STYLES = ("aastex", "aspc", "aasj")
# Search parameters the CLI sets from its own options.
MANAGED_SEARCH_PARAMETERS = {"q", "fl", "rows", "start", "sort", "fq", "wt"}
WORD_CLOUD_MAX_ROWS = 500
METRIC_TYPES = ("basic", "citations", "indicators", "histograms", "timeseries")
HISTOGRAM_TYPES = ("publications", "reads", "downloads", "citations")
# The reference service resolves at most 16 strings per request and silently
# drops the rest, so the CLI sends larger lists in batches. A full batch, like a
# network or word-cloud computation, can take tens of seconds.
REFERENCE_BATCH_SIZE = 16
DEFAULT_TIMEOUT = 30.0
COMMAND_TIMEOUTS = {"reference": 120.0, "network": 120.0, "wordcloud": 120.0}
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
    """Keep SciX credentials on the configured API origin."""

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


def search_rows(value: str) -> int:
    """Rows for a search; 0 returns only counts, facets, and statistics."""
    number = nonnegative_int(value)
    if number > 2000:
        raise argparse.ArgumentTypeError("must be at most 2000")
    return number


def word_cloud_rows(value: str) -> int:
    number = positive_int(value)
    if number > WORD_CLOUD_MAX_ROWS:
        raise argparse.ArgumentTypeError(f"must be at most {WORD_CLOUD_MAX_ROWS}")
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
            "Call stable, read-only SciX API workflows. Research decisions "
            "and result synthesis remain in the nasa-ads skill instructions."
        )
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--library-dir", help="personal literature library used by search capture"
    )
    parser.add_argument(
        "--no-store",
        action="store_true",
        help="run a metadata/API check without local search capture",
    )
    parser.add_argument(
        "--timeout",
        type=bounded_timeout,
        help=(
            "request timeout in seconds (default: 30; 120 per reference batch and "
            "for network and wordcloud; "
            "range: 1-300)"
        ),
    )
    parser.add_argument(
        "--show-rate-limit",
        action="store_true",
        help="write SciX rate-limit response headers to stderr",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="search SciX literature")
    search.add_argument("-q", "--query", required=True, help="native SciX query")
    search.add_argument(
        "--fields",
        "--fl",
        default=DEFAULT_FIELDS,
        help="comma-separated fields to return",
    )
    search.add_argument(
        "--rows",
        type=search_rows,
        default=10,
        help="records to return (0-2000; 0 returns only counts, facets, and stats)",
    )
    search.add_argument("--start", type=nonnegative_int, default=0)
    search.add_argument("--sort", help='sort expression, for example "date desc"')
    search.add_argument(
        "--highlight",
        action="append",
        default=[],
        metavar="FIELD",
        help="return matching snippets from a field such as title, abstract, or body",
    )
    search.add_argument(
        "--highlight-query",
        help="terms to highlight (default: the quoted phrases of --query)",
    )
    search.add_argument(
        "--facet",
        action="append",
        default=[],
        metavar="FIELD",
        help="count matches by a facet field such as year, bibstem_facet, or doctype",
    )
    search.add_argument(
        "--facet-limit",
        type=positive_int,
        default=20,
        help="facet values to return per field (default: 20)",
    )
    search.add_argument(
        "--stats",
        action="append",
        default=[],
        metavar="FIELD",
        help="summary statistics of a numeric field such as citation_count",
    )
    search.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="another search parameter, such as hl.fragsize=300 or facet.pivot=year,doctype",
    )
    search.add_argument("--collection", action="append", default=[])
    search.add_argument(
        "--role",
        action="append",
        choices=("review", "intro", "methods", "discussion", "comparison"),
        default=[],
    )
    search.add_argument(
        "--filter",
        "--fq",
        action="append",
        default=[],
        help="filter query; repeat for multiple fq values",
    )

    bigquery = subparsers.add_parser(
        "bigquery", help="look up many bibcodes through the big-query endpoint"
    )
    bigquery.add_argument("bibcodes", nargs="*", help="bibcodes to look up")
    bigquery.add_argument(
        "--bibcodes-file",
        help="UTF-8 file containing one bibcode per line; use - for stdin",
    )
    bigquery.add_argument("-q", "--query", default="*:*", help="main SciX query")
    bigquery.add_argument("--fields", "--fl", default=DEFAULT_FIELDS)
    bigquery.add_argument("--collection", action="append", default=[])
    bigquery.add_argument(
        "--role",
        action="append",
        choices=("review", "intro", "methods", "discussion", "comparison"),
        default=[],
    )
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
    export.add_argument("--sort", help="SciX export sort expression")
    export.add_argument(
        "--style",
        choices=CSL_STYLES,
        help="journal style of the csl format",
    )
    export.add_argument(
        "--csl-format",
        choices=tuple(CSL_FORMATS),
        default="unicode",
        help="text encoding of the csl format (default: unicode)",
    )
    export.add_argument(
        "--journal-format",
        choices=tuple(JOURNAL_FORMATS),
        help="journal names in aastex, aspc, and aasj csl styles",
    )
    export.add_argument(
        "--custom-format",
        help='custom format string, for example "%%1H:%%Y:%%q" (custom format only)',
    )

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

    reference = subparsers.add_parser(
        "reference", help="resolve free-text reference strings to bibcodes"
    )
    reference.add_argument(
        "references", nargs="*", help="reference strings, each shell-quoted"
    )
    reference.add_argument(
        "--references-file",
        help="UTF-8 file containing one reference per line; use - for stdin",
    )

    objects = subparsers.add_parser(
        "objects", help="resolve astronomical object names through SIMBAD and NED"
    )
    objects.add_argument("identifiers", nargs="*", help="object names or identifiers")
    objects.add_argument(
        "--query",
        dest="object_query",
        help="translate an object: query into the SciX search query it runs",
    )

    journals = subparsers.add_parser(
        "journals", help="find journals and their bibstems in the SciX journal database"
    )
    journals.add_argument("term", help="journal name or abbreviation, or a bibstem")
    journals.add_argument(
        "--summary",
        action="store_true",
        help="return the journal summary for the bibstem given as the term",
    )
    journals.add_argument(
        "--completeness",
        action="store_true",
        help="keep the per-volume completeness details in a journal summary",
    )

    network = subparsers.add_parser(
        "network", help="group papers by shared references or shared authors"
    )
    network.add_argument("kind", choices=("paper", "author"))
    network.add_argument("bibcodes", nargs="*")
    network.add_argument(
        "--bibcodes-file",
        help="UTF-8 file containing one bibcode per line; use - for stdin",
    )
    network.add_argument(
        "--full",
        action="store_true",
        help="keep the per-paper graph of a paper network",
    )

    cloud = subparsers.add_parser(
        "wordcloud", help="weighted terms across the records a query returns"
    )
    cloud.add_argument("-q", "--query", required=True, help="native SciX query")
    cloud.add_argument(
        "--rows",
        type=word_cloud_rows,
        default=150,
        help=f"records to use (default: 150; at most {WORD_CLOUD_MAX_ROWS})",
    )
    cloud.add_argument("--sort", help="sort expression for selecting the records")

    return parser


def abstract_url(bibcode: str) -> str:
    return ABSTRACT_URL.format(quote(bibcode, safe=""))


def token_if_available(environ: Mapping[str, str]) -> str | None:
    return environ.get(TOKEN_ENV, "").strip() or None


def resolve_token(environ: Mapping[str, str]) -> str:
    token = token_if_available(environ)
    if not token:
        raise CliError(
            f"Set {TOKEN_ENV}, then retry. Create a token at {TOKEN_URL}",
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
        raise CliError(f"Unable to read input file {path!r}: {exc}") from exc


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
    return detail[:800] or "SciX returned an unspecified application error."


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
    accept: str = "application/json, text/plain;q=0.9, */*;q=0.8",
) -> ApiResponse:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
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
                raise CliError(f"SciX API returned an application error. {detail}")
            return ApiResponse(
                body=response_body, headers=dict(response.headers.items())
            )
    except HTTPError as exc:
        response_body = exc.read()
        if 300 <= exc.code < 400:
            raise CliError(
                f"SciX API returned HTTP {exc.code} {exc.reason}; "
                "the redirect was not followed."
            ) from exc
        detail = concise_response_text(response_body, token)
        rate_limit = format_rate_limit(exc.headers or {})
        message = f"SciX API returned HTTP {exc.code} {exc.reason}."
        if detail:
            message = f"{message} {detail}"
        if rate_limit:
            message = f"{message} {rate_limit}"
        raise CliError(message) from exc
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise CliError(f"Unable to reach the SciX API: {reason}") from exc


def search_query(
    args: argparse.Namespace,
) -> tuple[str, list[tuple[str, Any]], bytes | None, str | None]:
    query: list[tuple[str, Any]] = [
        ("q", args.query),
        ("fl", capture_fields(args)),
        ("rows", args.rows),
        ("start", args.start),
    ]
    if args.sort:
        query.append(("sort", args.sort))
    query.extend(("fq", value) for value in args.filter)
    query.extend(search_extras(args))
    return "/search/query", query, None, None


def quoted_phrases(query: str) -> list[str]:
    return [phrase.strip() for phrase in re.findall(r'"([^"]+)"', query) if phrase.strip()]


def passthrough_parameters(args: argparse.Namespace) -> list[tuple[str, str]]:
    parameters: list[tuple[str, str]] = []
    for item in args.param:
        key, separator, value = item.partition("=")
        key = key.strip()
        if not separator or not key:
            raise CliError(f"--param needs KEY=VALUE: {item!r}", exit_code=2)
        if key in MANAGED_SEARCH_PARAMETERS:
            raise CliError(f"Set {key} with its own search option.", exit_code=2)
        parameters.append((key, value))
    return parameters


def with_overrides(
    parameters: list[tuple[str, Any]],
    defaults: dict[str, Any],
    passthrough: list[tuple[str, str]],
) -> list[tuple[str, Any]]:
    """Defaults that a passthrough parameter of the same key replaces."""
    replaced = {key for key, _value in passthrough}
    return [
        *parameters,
        *((key, value) for key, value in defaults.items() if key not in replaced),
        *passthrough,
    ]


def facet_parameters(args: argparse.Namespace, field: str) -> tuple[list, dict]:
    return (
        [("facet", "true"), ("facet.field", field), ("facet.limit", args.facet_limit)],
        {"facet.mincount": 1},
    )


def search_extras(args: argparse.Namespace) -> list[tuple[str, Any]]:
    """Highlight, facet, statistics, and passthrough parameters of a search.

    SciX returns highlights only for an explicit ``hl.q``, so the quoted
    phrases of the query become the highlight terms unless others are given.
    The SciX gateway keeps one value per facet or statistics field, so this
    request carries the first of each and ``count_queries`` covers the rest.
    """
    extras: list[tuple[str, Any]] = []
    defaults: dict[str, Any] = {}
    if args.highlight:
        terms = args.highlight_query or " OR ".join(
            f'"{phrase}"' for phrase in quoted_phrases(args.query)
        )
        if not terms:
            raise CliError(
                "Give --highlight-query with the terms to highlight; "
                "--query has no quoted phrase.",
                exit_code=2,
            )
        extras += [
            ("hl", "true"),
            ("hl.fl", ",".join(unique_nonempty(args.highlight))),
            ("hl.q", terms),
        ]
        defaults.update({"hl.snippets": 3, "hl.fragsize": 200})
    facets = unique_nonempty(args.facet)
    if facets:
        parameters, facet_defaults = facet_parameters(args, facets[0])
        extras += parameters
        defaults.update(facet_defaults)
    statistics = unique_nonempty(args.stats)
    if statistics:
        extras += [("stats", "true"), ("stats.field", statistics[0])]
    return with_overrides(extras, defaults, passthrough_parameters(args))


def count_queries(args: argparse.Namespace) -> list[tuple[str, str, list[tuple[str, Any]]]]:
    """Count-only requests for each facet and statistics field after the first."""
    base: list[tuple[str, Any]] = [
        ("q", args.query),
        ("fl", "id"),
        ("rows", 0),
        ("start", 0),
        *(("fq", value) for value in args.filter),
    ]
    passthrough = passthrough_parameters(args)
    queries = []
    for field in unique_nonempty(args.facet)[1:]:
        parameters, defaults = facet_parameters(args, field)
        own = [(key, value) for key, value in passthrough if key.startswith("facet.")]
        queries.append(("facet", field, with_overrides([*base, *parameters], defaults, own)))
    for field in unique_nonempty(args.stats)[1:]:
        own = [(key, value) for key, value in passthrough if key.startswith("stats.")]
        queries.append(
            ("stats", field, [*base, ("stats", "true"), ("stats.field", field), *own])
        )
    return queries


def merge_counts(payload: Any, extra: Any, kind: str, field: str) -> None:
    """Add one field's facet counts or statistics to the main search response."""
    if not isinstance(payload, dict) or not isinstance(extra, dict):
        return
    section, entries = (
        ("facet_counts", "facet_fields") if kind == "facet" else ("stats", "stats_fields")
    )
    source = (extra.get(section) or {}).get(entries) or {}
    if field in source:
        target = payload.setdefault(section, {}).setdefault(entries, {})
        target[field] = source[field]


def search_highlights(payload: Any) -> list[dict[str, Any]]:
    """Nonempty highlight snippets keyed by bibcode instead of the record id."""
    highlighting = payload.get("highlighting") if isinstance(payload, dict) else None
    if not isinstance(highlighting, dict):
        return []
    docs = (payload.get("response") or {}).get("docs") or []
    bibcodes = {
        str(doc.get("id")): doc.get("bibcode") for doc in docs if isinstance(doc, dict)
    }
    return [
        {"bibcode": bibcodes.get(str(record_id)), "id": record_id, "fields": fields}
        for record_id, fields in highlighting.items()
        if fields
    ]


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
        ("fl", capture_fields(args)),
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
    if args.format == "csl" and not args.style:
        raise CliError("The csl format requires --style.", exit_code=2)
    if args.format == "custom" and not args.custom_format:
        raise CliError("The custom format requires --custom-format.", exit_code=2)
    if args.style and args.format != "csl":
        raise CliError("--style applies to the csl format.", exit_code=2)
    if args.custom_format and args.format != "custom":
        raise CliError("--custom-format applies to the custom format.", exit_code=2)
    if args.journal_format and args.style not in JOURNAL_FORMAT_STYLES:
        raise CliError(
            "--journal-format applies to the aastex, aspc, and aasj csl styles.",
            exit_code=2,
        )
    encoded_format = quote(args.format, safe="")
    if len(bibcodes) == 1 and args.format not in {"csl", "custom"}:
        encoded_bibcode = quote(bibcodes[0], safe="")
        return (
            "GET",
            f"/export/{encoded_format}/{encoded_bibcode}",
            [],
            None,
            None,
        )
    payload: dict[str, Any] = {"bibcode": bibcodes}
    if args.format == "csl":
        payload["style"] = args.style
        payload["format"] = CSL_FORMATS[args.csl_format]
        if args.journal_format:
            payload["journalformat"] = JOURNAL_FORMATS[args.journal_format]
    elif args.format == "custom":
        payload["format"] = args.custom_format
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


def reference_batches(args: argparse.Namespace, stdin: TextIO) -> list[list[str]]:
    """Reference strings in batches of the reference service's request limit."""
    references = list(args.references)
    if args.references_file:
        references.extend(read_bibcodes_file(args.references_file, stdin))
    references = unique_nonempty(references)
    if not references:
        raise CliError(
            "Provide at least one reference string or --references-file.", exit_code=2
        )
    return [
        references[start : start + REFERENCE_BATCH_SIZE]
        for start in range(0, len(references), REFERENCE_BATCH_SIZE)
    ]


def resolved_references(payloads: Sequence[Any]) -> dict[str, Any]:
    """Merge reference-service batches; an unresolved entry gets a null bibcode."""
    resolved: list[dict[str, Any]] = []
    for payload in payloads:
        entries = payload.get("resolved") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise CliError("SciX reference service response lacks a resolved list.")
        for entry in entries:
            if not isinstance(entry, dict):
                raise CliError("SciX reference service returned an invalid entry.")
            entry = dict(entry)
            bibcode = entry.get("bibcode")
            if not isinstance(bibcode, str) or not bibcode.strip(". "):
                entry["bibcode"] = None
            resolved.append(entry)
    return {
        "count": len(resolved),
        "resolved_count": sum(1 for entry in resolved if entry["bibcode"]),
        "resolved": resolved,
    }


def objects_request(args: argparse.Namespace) -> tuple[str, bytes]:
    identifiers = unique_nonempty(args.identifiers)
    if bool(identifiers) == bool(args.object_query):
        raise CliError(
            "Provide object identifiers or --query, but not both.", exit_code=2
        )
    if args.object_query:
        return "/objects/query", json_bytes({"query": [args.object_query]})
    return "/objects", json_bytes({"identifiers": identifiers})


def journals_path(args: argparse.Namespace) -> str:
    term = args.term.strip()
    if not term:
        raise CliError("Provide a journal name, abbreviation, or bibstem.", exit_code=2)
    route = "summary" if args.summary else "journal"
    return f"/journals/{route}/{quote(term, safe='')}"


def trimmed_journal_summary(payload: Any, keep_completeness: bool) -> Any:
    """Drop the per-volume completeness table, which dwarfs the rest of a summary."""
    summary = payload.get("summary") if isinstance(payload, dict) else None
    master = summary.get("master") if isinstance(summary, dict) else None
    if keep_completeness or not isinstance(master, dict):
        return payload
    if "completeness_details" not in master:
        return payload
    summary["master"] = {
        key: value for key, value in master.items() if key != "completeness_details"
    }
    payload["omitted"] = ["summary.master.completeness_details"]
    return payload


def network_request(args: argparse.Namespace, stdin: TextIO) -> tuple[str, bytes]:
    bibcodes = list(args.bibcodes)
    if args.bibcodes_file:
        bibcodes.extend(read_bibcodes_file(args.bibcodes_file, stdin))
    bibcodes = unique_nonempty(bibcodes)
    if not bibcodes:
        raise CliError("Provide at least one bibcode or --bibcodes-file.", exit_code=2)
    return f"/vis/{args.kind}-network", json_bytes({"bibcodes": bibcodes})


def trimmed_paper_network(payload: Any, keep_full: bool) -> Any:
    """Keep the paper groups and drop the per-paper graph unless requested.

    Small paper sets yield no groups; their per-paper graph is all there is.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if (
        keep_full
        or not isinstance(data, dict)
        or "fullGraph" not in data
        or not data.get("summaryGraph")
    ):
        return payload
    payload["data"] = {key: value for key, value in data.items() if key != "fullGraph"}
    payload["omitted"] = ["data.fullGraph"]
    return payload


def word_cloud_payload(args: argparse.Namespace) -> bytes:
    payload: dict[str, Any] = {"q": [args.query], "rows": [args.rows]}
    if args.sort:
        payload["sort"] = [args.sort]
    return json_bytes(payload)


def decode_json_response(response: ApiResponse, label: str) -> Any:
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(f"SciX returned an invalid {label} response.") from exc


def write_json(value: Any, stdout: TextIO) -> None:
    json.dump(value, stdout, ensure_ascii=False, indent=2)
    stdout.write("\n")


def capture_fields(args: argparse.Namespace) -> str:
    fields = args.fields.split(",")
    if getattr(args, "highlight", None):
        fields.append("id")  # SciX keys highlight snippets by the record id.
    if not args.no_store:
        fields += DEFAULT_FIELDS.split(",")
    return ",".join(unique_nonempty(fields))


def write_search_result(payload, args, stdout, environ, token):
    # A count-only search returns no records to capture.
    if args.no_store or args.rows == 0:
        write_json(payload, stdout)
        return
    if not isinstance(payload, dict):
        raise CliError("SciX search returned an invalid response object.")
    import literature_db
    import library_catalog
    import fulltext
    from pathlib import Path
    import sqlite3

    library_dir = (
        Path(args.library_dir).expanduser().resolve()
        if args.library_dir
        else literature_db.default_library_dir(environ)
    )
    connection = None
    try:
        connection, fts5 = literature_db.connect_library(library_dir)
        capture = library_catalog.capture_search(
            connection,
            fts5,
            payload,
            query=args.query,
            parameters={
                "command": args.command,
                "fields": capture_fields(args),
                "start": args.start,
                "rows": args.rows,
                "sort": args.sort,
                "filters": args.filter,
                **(
                    {"params": args.param}
                    if getattr(args, "param", None)
                    else {}
                ),
            },
            collections=args.collection,
            roles=args.role,
        )
    except (
        literature_db.LiteratureError,
        fulltext.FullTextError,
        sqlite3.Error,
        OSError,
        ValueError,
    ) as exc:
        detail = str(exc).replace(token, "[redacted]")
        write_json(
            {**payload, "literature": {"status": "failed", "error": detail}}, stdout
        )
        raise CliError(
            "Search succeeded; literature capture failed. Save the response and retry capture. "
            + detail
        ) from exc
    finally:
        if connection is not None:
            connection.close()
    write_json({**payload, "literature": capture}, stdout)


def execute(
    args: argparse.Namespace,
    token: str,
    *,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    opener: Any = None,
    environ: Mapping[str, str] | None = None,
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
        payload = decode_json_response(response, "search")
        for kind, field, count_query in count_queries(args):
            counted = request_api(
                "GET",
                "/search/query",
                token,
                query=count_query,
                timeout=args.timeout,
                opener=opener,
            )
            merge_counts(payload, decode_json_response(counted, "search"), kind, field)
        if args.highlight and isinstance(payload, dict):
            payload["highlights"] = search_highlights(payload)
        write_search_result(
            payload,
            args,
            stdout,
            environ if environ is not None else os.environ,
            token,
        )
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
        write_search_result(
            decode_json_response(response, "big-query"),
            args,
            stdout,
            environ if environ is not None else os.environ,
            token,
        )
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
                raise CliError("SciX citation export response lacks an export field.")
            export_text = payload["export"]
        else:
            try:
                export_text = response.body.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CliError("SciX returned an invalid citation export.") from exc
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
    elif args.command == "reference":
        payloads = []
        for batch in reference_batches(args, stdin):
            response = request_api(
                "POST",
                "/reference/text",
                token,
                body=json_bytes({"reference": batch}),
                content_type="application/json",
                timeout=args.timeout,
                opener=opener,
                # The service answers in plain text unless JSON is the only type.
                accept="application/json",
            )
            payloads.append(decode_json_response(response, "reference service"))
        write_json(resolved_references(payloads), stdout)
    elif args.command == "objects":
        path, body = objects_request(args)
        response = request_api(
            "POST",
            path,
            token,
            body=body,
            content_type="application/json",
            timeout=args.timeout,
            opener=opener,
        )
        write_json(decode_json_response(response, "objects"), stdout)
    elif args.command == "journals":
        response = request_api(
            "GET",
            journals_path(args),
            token,
            timeout=args.timeout,
            opener=opener,
        )
        payload = decode_json_response(response, "journals")
        if args.summary:
            payload = trimmed_journal_summary(payload, args.completeness)
        write_json(payload, stdout)
    elif args.command == "network":
        path, body = network_request(args, stdin)
        response = request_api(
            "POST",
            path,
            token,
            body=body,
            content_type="application/json",
            timeout=args.timeout,
            opener=opener,
        )
        payload = decode_json_response(response, "network")
        if args.kind == "paper":
            payload = trimmed_paper_network(payload, args.full)
        write_json(payload, stdout)
    elif args.command == "wordcloud":
        response = request_api(
            "POST",
            "/vis/word-cloud",
            token,
            body=word_cloud_payload(args),
            content_type="application/json",
            timeout=args.timeout,
            opener=opener,
        )
        write_json(decode_json_response(response, "word cloud"), stdout)
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
    if args.timeout is None:
        args.timeout = COMMAND_TIMEOUTS.get(args.command, DEFAULT_TIMEOUT)
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
            environ=environ if environ is not None else os.environ,
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
