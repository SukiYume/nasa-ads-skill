#!/usr/bin/env python3
"""Discover, fetch, cache, and prepare lawful full text for NASA ADS records."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

import ads_api

VERSION = "1.12.0"
DEFAULT_MAX_BYTES = 100 * 1024 * 1024
DEFAULT_TIMEOUT = 45.0
UNPAYWALL_URL = "https://api.unpaywall.org/v2"
USER_AGENT = f"nasa-ads-skill/{VERSION} (+https://github.com/SukiYume/nasa-ads-skill)"
ARXIV_NEW_RE = re.compile(r"^(\d{4}\.\d{4,5}(?:v\d+)?)$", re.IGNORECASE)
ARXIV_OLD_RE = re.compile(r"^([a-z][a-z0-9.-]*/\d{7}(?:v\d+)?)$", re.IGNORECASE)
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "caption",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "main",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "tr",
}
SKIP_TAGS = {
    "annotation",
    "button",
    "canvas",
    "form",
    "nav",
    "noscript",
    "script",
    "style",
}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
FOCUS_TAGS = {"article", "main"}
MEASUREMENT_ONLY_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*"
    r"(?:uJy|μJy|mJy|Jy|Hz|kHz|MHz|GHz|THz|μs|us|ms|s|min|h|d|yr|"
    r"eV|keV|MeV|GeV|TeV|K|pc|kpc|Mpc|Gpc|mm|cm|m|km|"
    r"deg|arcsec|mas|rad|mag|%)$",
    re.IGNORECASE,
)
DATE_ONLY_RE = re.compile(
    r"^\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4}$",
    re.IGNORECASE,
)


class FullTextError(Exception):
    """A concise, user-facing full-text workflow error."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class Candidate:
    source: str
    version: str
    format: str
    url: str
    priority: int
    link_type: str | None = None
    license: str | None = None
    access: str = "unknown"


@dataclass(frozen=True)
class Downloaded:
    body: bytes
    final_url: str
    content_type: str
    headers: Mapping[str, str]


class ReadableHTMLParser(HTMLParser):
    """Extract readable blocks while preferring article/main content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.all_parts: list[str] = []
        self.focus_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.headings: list[str] = []
        self.skip_depth = 0
        self.focus_depth = 0
        self.heading_depth = 0
        self.title_depth = 0
        self.title_parts: list[str] = []

    def append(self, value: str) -> None:
        if self.skip_depth:
            return
        self.all_parts.append(value)
        if self.focus_depth:
            self.focus_parts.append(value)
        if self.heading_depth:
            self.heading_parts.append(value)

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in FOCUS_TAGS:
            self.focus_depth += 1
        if tag in HEADING_TAGS:
            self.heading_depth += 1
            self.heading_parts = []
        if tag == "title":
            self.title_depth += 1
        if tag in BLOCK_TAGS:
            self.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in BLOCK_TAGS:
            self.append("\n")
        if tag in HEADING_TAGS and self.heading_depth:
            heading = normalize_text("".join(self.heading_parts))
            if heading:
                self.headings.append(heading)
            self.heading_depth -= 1
            self.heading_parts = []
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        if tag in FOCUS_TAGS and self.focus_depth:
            self.focus_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.append(data)
        if self.title_depth:
            self.title_parts.append(data)

    def readable_text(self) -> tuple[str, bool]:
        focused = normalize_text("".join(self.focus_parts))
        if count_words(focused) >= 250:
            return focused, True
        return normalize_text("".join(self.all_parts)), False

    def full_text(self) -> str:
        return normalize_text("".join(self.all_parts))

    def document_title(self) -> str:
        return normalize_text("".join(self.title_parts))


class SafeRedirectHandler(HTTPRedirectHandler):
    """Follow bounded HTTPS redirects without carrying ADS credentials."""

    def __init__(self, max_redirects: int = 5) -> None:
        super().__init__()
        self.max_redirects = max_redirects
        self.redirects = 0

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Mapping[str, str],
        new_url: str,
    ) -> Request | None:
        self.redirects += 1
        if self.redirects > self.max_redirects:
            raise FullTextError("External source exceeded five redirects.")
        validate_external_url(new_url)
        return super().redirect_request(
            request, file_pointer, code, message, headers, new_url
        )


def bounded_megabytes(value: str) -> int:
    number = ads_api.positive_int(value)
    if number > 500:
        raise argparse.ArgumentTypeError("must be at most 500 MiB")
    return number * 1024 * 1024


def bounded_dpi(value: str) -> int:
    number = int(value)
    if not 72 <= number <= 300:
        raise argparse.ArgumentTypeError("must be between 72 and 300")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover, fetch, cache, and prepare lawful article full text. "
            "Scientific reading and visual interpretation remain in the "
            "nasa-ads skill instructions."
        )
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="fetch one or more article records")
    fetch.add_argument(
        "identifiers",
        nargs="+",
        help="ADS bibcode, DOI, arXiv ID, or arXiv URL",
    )
    fetch.add_argument(
        "--source",
        choices=("auto", "publisher", "author", "arxiv", "ads"),
        default="auto",
        help="limit candidate sources (default: auto)",
    )
    fetch.add_argument(
        "--format",
        dest="output_format",
        choices=("auto", "html", "pdf"),
        default="auto",
        help="limit candidate formats (default: auto, preferring readable HTML)",
    )
    fetch.add_argument("--cache-dir", help="cache root; overrides the default")
    fetch.add_argument(
        "--refresh", action="store_true", help="ignore a valid cached manifest"
    )
    fetch.add_argument(
        "--use-unpaywall",
        action="store_true",
        help="use UNPAYWALL_EMAIL to discover additional DOI locations",
    )
    fetch.add_argument(
        "--timeout",
        type=ads_api.bounded_timeout,
        default=DEFAULT_TIMEOUT,
        help="per-request timeout in seconds (default: 45)",
    )
    fetch.add_argument(
        "--max-mib",
        type=bounded_megabytes,
        default=DEFAULT_MAX_BYTES,
        metavar="MIB",
        help="maximum downloaded size per candidate (default: 100 MiB)",
    )

    render = subparsers.add_parser(
        "render", help="render at most twenty PDF pages for visual reading"
    )
    render.add_argument("pdf", help="local PDF path")
    render.add_argument(
        "--pages",
        required=True,
        help="one-based page or inclusive range, for example 1-10",
    )
    render.add_argument("--output-dir", help="directory for PNG pages")
    render.add_argument("--dpi", type=bounded_dpi, default=150)
    render.add_argument(
        "--refresh", action="store_true", help="rerender existing page images"
    )
    render.add_argument(
        "--timeout",
        type=ads_api.bounded_timeout,
        default=300.0,
        help="render timeout in seconds (default: 300)",
    )
    outline = subparsers.add_parser(
        "outline", help="extract a reviewable section outline from prepared article text"
    )
    outline.add_argument("text", help="prepared article text path")
    outline.add_argument(
        "--limit",
        type=ads_api.positive_int,
        default=200,
        help="maximum headings to return (default: 200)",
    )
    return parser


def normalize_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\r", "\n")
    lines: list[str] = []
    for raw_line in value.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", raw_line).strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def count_words(value: str) -> int:
    return len(re.findall(r"\b[^\W_][\w'-]*\b", value, flags=re.UNICODE))


def infer_text_outline(value: str, *, limit: int = 200) -> list[str]:
    headings: list[str] = []
    seen: set[str] = set()
    in_references = False
    numbered = re.compile(
        r"^(?:§\s*\d+(?:\.\d+){0,3}\s+|"
        r"(?:\d+(?:\.\d+){0,3}|[A-Z]\.\d+(?:\.\d+){0,2})[.)]?\s+|"
        r"[IVXLC]+[.)]\s+|"
        r"(?:Appendix|Supplement)\s+[A-Z0-9]+[:.)]?\s+)(\S.*)$",
        re.IGNORECASE,
    )
    named = re.compile(
        r"^(?:abstract|introduction|background|observations?|data|methods?|"
        r"analysis|results?|discussion|conclusions?|summary|limitations?|"
        r"acknowledg(?:e)?ments?|references|bibliography)$",
        re.IGNORECASE,
    )
    for raw_line in value.splitlines():
        line = " ".join(raw_line.split())
        if not line or len(line) > 180:
            continue
        if MEASUREMENT_ONLY_RE.fullmatch(line) or DATE_ONLY_RE.fullmatch(line):
            continue
        match = numbered.match(line)
        if in_references:
            if not re.match(
                r"^(?:Appendix|Supplement)\s+[A-Z0-9]+[:.)]?\s+",
                line,
                re.IGNORECASE,
            ):
                continue
            in_references = False
        if not match and not named.match(line):
            continue
        if match:
            heading_text = match.group(1)
            if not any(character.isalpha() for character in heading_text):
                continue
            if ". " in heading_text:
                continue
        if re.match(r"^(?:Figure|Table)\s+\d", line, re.IGNORECASE):
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        headings.append(line)
        if key in {"references", "bibliography"}:
            in_references = True
        if len(headings) >= limit:
            break
    return headings


def list_value(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def first_value(value: Any) -> str | None:
    values = list_value(value)
    return values[0] if values else None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_text_sha256(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return sha256_bytes(normalized.encode("utf-8"))


def atomic_write_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(body)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def write_json_file(path: Path, value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(path, serialized)


def default_cache_dir(environ: Mapping[str, str]) -> Path:
    configured = environ.get("NASA_ADS_CACHE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = environ.get("LOCALAPPDATA", "").strip()
    if os.name == "nt" and local_app_data:
        return (Path(local_app_data) / "nasa-ads" / "fulltext").resolve()
    xdg_cache = environ.get("XDG_CACHE_HOME", "").strip()
    if xdg_cache:
        return (Path(xdg_cache).expanduser() / "nasa-ads" / "fulltext").resolve()
    return (Path.home() / ".cache" / "nasa-ads" / "fulltext").resolve()


def cache_key(identifier: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9._-]+", "_", identifier).strip("._-")
    if not readable:
        readable = "record"
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:10]
    return f"{readable[:80]}-{digest}"


def arxiv_id_from_value(value: str) -> str | None:
    candidate = value.strip()
    candidate = re.sub(r"^arxiv:\s*", "", candidate, flags=re.IGNORECASE)
    parsed = urlsplit(candidate)
    if parsed.scheme and parsed.netloc.lower().endswith("arxiv.org"):
        match = re.match(r"^/(?:abs|html|pdf|src)/(.+?)(?:\.pdf)?$", parsed.path)
        if not match:
            return None
        candidate = match.group(1)
    candidate = candidate.strip().rstrip("/")
    if ARXIV_NEW_RE.fullmatch(candidate) or ARXIV_OLD_RE.fullmatch(candidate):
        return candidate
    return None


def doi_from_value(value: str) -> str | None:
    candidate = value.strip()
    candidate = re.sub(r"^doi:\s*", "", candidate, flags=re.IGNORECASE)
    parsed = urlsplit(candidate)
    if parsed.scheme and parsed.netloc.lower() in {"doi.org", "dx.doi.org"}:
        candidate = parsed.path.lstrip("/")
    candidate = candidate.strip().rstrip(".")
    return candidate if DOI_RE.fullmatch(candidate) else None


def classify_identifier(identifier: str) -> tuple[str, str]:
    arxiv_id = arxiv_id_from_value(identifier)
    if arxiv_id:
        return "arxiv", arxiv_id
    doi = doi_from_value(identifier)
    if doi:
        return "doi", doi
    stripped = identifier.strip()
    if not stripped or any(character.isspace() for character in stripped):
        raise FullTextError(f"Unsupported identifier: {identifier!r}", exit_code=2)
    return "bibcode", stripped


def validate_external_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise FullTextError(f"External full-text URL must use HTTPS: {url}")
    if not parsed.hostname or parsed.username or parsed.password:
        raise FullTextError(f"Invalid external full-text URL: {url}")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise FullTextError(f"Local external target is not allowed: {url}")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise FullTextError(f"Non-public external target is not allowed: {url}")


def normalize_candidate_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    if scheme == "http":
        scheme = "https"
    normalized = urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, ""))
    validate_external_url(normalized)
    return normalized


def fetch_external(
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    opener: Any = None,
) -> Downloaded:
    validate_external_url(url)
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.2",
            "Accept-Encoding": "identity",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    open_request = opener or build_opener(SafeRedirectHandler()).open
    try:
        with open_request(request, timeout=timeout) as response:
            body_parts: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise FullTextError(
                        "External source exceeds the "
                        f"{max_bytes // (1024 * 1024)} MiB limit."
                    )
                body_parts.append(chunk)
            headers = dict(response.headers.items())
            normalized_headers = {
                str(name).lower(): str(value) for name, value in headers.items()
            }
            final_url_getter = getattr(response, "geturl", None)
            final_url = final_url_getter() if callable(final_url_getter) else url
            validate_external_url(final_url)
            content_type = (
                normalized_headers.get("content-type", "").split(";", 1)[0].lower()
            )
            return Downloaded(
                body=b"".join(body_parts),
                final_url=final_url,
                content_type=content_type,
                headers=headers,
            )
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            raise FullTextError(
                f"External source returned HTTP {exc.code}; redirect was rejected."
            ) from exc
        raise FullTextError(
            f"External source returned HTTP {exc.code} {exc.reason}."
        ) from exc
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise FullTextError(
            f"Unable to reach external full-text source: {reason}"
        ) from exc


def extract_html(body: bytes, expected_title: str | None) -> tuple[str, dict[str, Any]]:
    try:
        html = body.decode("utf-8")
    except UnicodeDecodeError:
        html = body.decode("utf-8", errors="replace")
    parser = ReadableHTMLParser()
    parser.feed(html)
    text, used_focus = parser.readable_text()
    word_count = count_words(text)
    full_text_lower = parser.full_text().lower()
    suspicious = (
        "access denied",
        "enable javascript and cookies to continue",
        "verify you are human",
        "captcha",
        "purchase access",
        "institutional sign in",
    )
    if (
        any(marker in full_text_lower[:10000] for marker in suspicious)
        and word_count < 2000
    ):
        raise FullTextError("HTML candidate is an access, login, or challenge page.")
    if word_count < 300:
        raise FullTextError(
            f"HTML candidate contains too little article text ({word_count} words)."
        )
    if not used_focus and len(parser.headings) < 3 and word_count < 2500:
        raise FullTextError("HTML candidate does not expose a full article structure.")
    title_overlap = None
    if expected_title:
        expected_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", expected_title.lower())
            if len(token) >= 4
        }
        if expected_tokens:
            candidate_tokens = set(re.findall(r"[a-z0-9]+", full_text_lower[:20000]))
            title_overlap = len(expected_tokens & candidate_tokens) / len(
                expected_tokens
            )
            if title_overlap < 0.35:
                raise FullTextError("HTML title does not match the target record.")
    outline: list[str] = []
    in_references = False
    for raw_heading in parser.headings:
        heading = normalize_text(raw_heading)
        if not heading:
            continue
        if in_references:
            if not re.match(
                r"^(?:Appendix|Supplement)\s+[A-Z0-9]+[:.)]?\s+",
                heading,
                re.IGNORECASE,
            ):
                continue
            in_references = False
        outline.append(heading)
        if heading.casefold() in {"references", "bibliography"}:
            in_references = True
        if len(outline) >= 200:
            break
    return text, {
        "characters": len(text),
        "words": word_count,
        "headings": len(outline),
        "outline": outline,
        "focused_article": used_focus,
        "document_title": parser.document_title() or None,
        "title_token_overlap": title_overlap,
    }


def find_executable(environ: Mapping[str, str], variable: str, name: str) -> str | None:
    configured = environ.get(variable, "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise FullTextError(f"{variable} does not point to a file: {configured}")
    return shutil.which(name)


def pdf_page_count(
    pdf_path: Path, environ: Mapping[str, str]
) -> tuple[int | None, str | None]:
    pdfinfo = find_executable(environ, "NASA_ADS_PDFINFO", "pdfinfo")
    if pdfinfo:
        try:
            completed = subprocess.run(
                [pdfinfo, str(pdf_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed and completed.returncode == 0:
            match = re.search(r"^Pages:\s+(\d+)\s*$", completed.stdout, re.MULTILINE)
            if match:
                return int(match.group(1)), "pdfinfo"
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        return len(PdfReader(str(pdf_path)).pages), "pypdf"
    except (ImportError, OSError, ValueError):
        pass
    try:
        approximate = len(re.findall(rb"/Type\s*/Page\b", pdf_path.read_bytes()))
    except OSError:
        approximate = 0
    return (approximate or None), ("pdf-marker-count" if approximate else None)


def extract_pdf_text(
    pdf_path: Path,
    text_path: Path,
    environ: Mapping[str, str],
) -> tuple[str | None, str | None, str | None]:
    pdftotext = find_executable(environ, "NASA_ADS_PDFTOTEXT", "pdftotext")
    if pdftotext:
        try:
            completed = subprocess.run(
                [
                    pdftotext,
                    "-layout",
                    "-enc",
                    "UTF-8",
                    str(pdf_path),
                    str(text_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, "pdftotext", f"pdftotext failed: {exc}"[:300]
        if completed.returncode == 0 and text_path.exists():
            text = text_path.read_text(encoding="utf-8", errors="replace")
            return normalize_text(text), "pdftotext", None
        detail = " ".join((completed.stderr or completed.stdout).split())[:300]
        return None, "pdftotext", detail or "pdftotext failed"
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return None, None, "No PDF text extractor is installed."
    try:
        pages = PdfReader(str(pdf_path)).pages
        text = "\n\n".join((page.extract_text() or "") for page in pages)
        return normalize_text(text), "pypdf", None
    except (OSError, ValueError) as exc:
        return None, "pypdf", str(exc)[:300]


def assess_pdf_text(
    text: str | None,
    page_count: int | None,
    extractor: str | None,
) -> tuple[str, dict[str, Any], list[str]]:
    page_denominator = max(page_count or 1, 1)
    characters = len(text or "")
    words = count_words(text or "")
    characters_per_page = characters / page_denominator
    minimum_words = max(100, min(1000, page_denominator * 25))
    warnings: list[str] = []
    if extractor is None:
        warnings.append("pdf_text_extractor_unavailable")
        status = "needs_visual_reading"
    elif words < minimum_words or characters_per_page < 100:
        warnings.append("pdf_text_layer_sparse_or_missing")
        status = "needs_visual_reading"
    else:
        status = "fulltext"
    return (
        status,
        {
            "characters": characters,
            "words": words,
            "pages": page_count,
            "characters_per_page": round(characters_per_page, 1),
            "extractor": extractor,
            "outline": infer_text_outline(text or ""),
        },
        warnings,
    )


def actual_format(downloaded: Downloaded) -> str:
    stripped = downloaded.body.lstrip()
    if stripped.startswith(b"%PDF-"):
        return "pdf"
    if stripped[:200].lower().startswith((b"<!doctype html", b"<html", b"<?xml")):
        return "html"
    if downloaded.content_type == "application/pdf":
        return "pdf"
    if downloaded.content_type in {"text/html", "application/xhtml+xml"}:
        return "html"
    raise FullTextError(
        f"Unsupported full-text content type: {downloaded.content_type or 'unknown'}"
    )


def candidate_stem(candidate: Candidate, selected_format: str) -> str:
    raw = f"{candidate.source}-{candidate.version}-{selected_format}"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")


def materialize_candidate(
    candidate: Candidate,
    record_dir: Path,
    expected_title: str | None,
    *,
    required_format: str | None = None,
    timeout: float,
    max_bytes: int,
    environ: Mapping[str, str],
    opener: Any = None,
) -> dict[str, Any]:
    downloaded = fetch_external(
        candidate.url,
        timeout=timeout,
        max_bytes=max_bytes,
        opener=opener,
    )
    selected_format = actual_format(downloaded)
    if required_format is not None and selected_format != required_format:
        raise FullTextError(
            f"Candidate advertised {candidate.format} but returned "
            f"{selected_format}; {required_format} was required."
        )
    stem = candidate_stem(candidate, selected_format)
    artifact_hash = sha256_bytes(downloaded.body)
    artifact_path = (
        record_dir
        / "artifacts"
        / f"{stem}-{artifact_hash[:16]}.{selected_format}"
    ).resolve()
    common: dict[str, Any] = {
        "candidate": asdict(candidate),
        "actual_format": selected_format,
        "final_url": downloaded.final_url,
        "artifact_path": str(artifact_path),
        "sha256": artifact_hash,
        "content_sha256": artifact_hash,
        "bytes": len(downloaded.body),
        "content_type": downloaded.content_type or None,
        "retrieved_at": utc_now(),
    }
    if selected_format == "html":
        text, statistics = extract_html(downloaded.body, expected_title)
        atomic_write_bytes(artifact_path, downloaded.body)
        text_path = artifact_path.with_suffix(".txt")
        atomic_write_text(text_path, text + "\n")
        common.update(
            {
                "status": "fulltext",
                "text_path": str(text_path),
                "text_sha256": sha256_bytes((text + "\n").encode("utf-8")),
                "content_sha256": canonical_text_sha256(text),
                "statistics": statistics,
                "warnings": [],
            }
        )
        return common

    atomic_write_bytes(artifact_path, downloaded.body)
    page_count, page_counter = pdf_page_count(artifact_path, environ)
    text_path = artifact_path.with_suffix(".txt")
    text, extractor, extraction_error = extract_pdf_text(
        artifact_path, text_path, environ
    )
    status, statistics, warnings = assess_pdf_text(text, page_count, extractor)
    statistics["page_counter"] = page_counter
    if extraction_error:
        warnings.append(f"pdf_extraction_error: {extraction_error}")
    if text:
        atomic_write_text(text_path, text + "\n")
        common["text_path"] = str(text_path)
        common["text_sha256"] = sha256_bytes((text + "\n").encode("utf-8"))
        if status == "fulltext":
            common["content_sha256"] = canonical_text_sha256(text)
    else:
        text_path.unlink(missing_ok=True)
        common["text_path"] = None
        common["text_sha256"] = None
    common.update(
        {
            "status": status,
            "statistics": statistics,
            "warnings": warnings,
        }
    )
    return common


def ads_token_if_available(environ: Mapping[str, str]) -> str | None:
    token = environ.get("ADS_API_TOKEN", "").strip()
    return token or environ.get("ADS_DEV_KEY", "").strip() or None


def ads_search_record(query: str, token: str, timeout: float) -> dict[str, Any] | None:
    response = ads_api.request_api(
        "GET",
        "/search/query",
        token,
        query=[
            ("q", query),
            (
                "fl",
                "bibcode,title,author,abstract,doi,identifier,property,esources,"
                "doctype,year,pub,citation_count,read_count",
            ),
            ("rows", 1),
        ],
        timeout=timeout,
    )
    payload = ads_api.decode_json_response(response, "full-text metadata")
    docs = (
        payload.get("response", {}).get("docs", []) if isinstance(payload, dict) else []
    )
    return docs[0] if docs and isinstance(docs[0], dict) else None


def arxiv_metadata_record(
    arxiv_id: str, *, timeout: float, max_bytes: int
) -> dict[str, Any] | None:
    base_id = re.sub(r"v\d+$", "", arxiv_id, flags=re.IGNORECASE)
    downloaded = fetch_external(
        "https://export.arxiv.org/api/query?" + urlencode({"id_list": base_id}),
        timeout=timeout,
        max_bytes=min(max_bytes, 5 * 1024 * 1024),
    )
    try:
        root = ElementTree.fromstring(downloaded.body)
    except ElementTree.ParseError as exc:
        raise FullTextError(f"Unable to parse arXiv metadata: {exc}") from exc
    atom = "{http://www.w3.org/2005/Atom}"
    arxiv = "{http://arxiv.org/schemas/atom}"
    entry = root.find(f"{atom}entry")
    if entry is None:
        return None

    def text_of(name: str) -> str | None:
        node = entry.find(name)
        if node is None or not node.text:
            return None
        return " ".join(node.text.split())

    entry_id = text_of(f"{atom}id") or ""
    returned_id = arxiv_id_from_value(entry_id)
    if not returned_id or re.sub(
        r"v\d+$", "", returned_id, flags=re.IGNORECASE
    ) != base_id:
        return None
    title = text_of(f"{atom}title")
    abstract = text_of(f"{atom}summary")
    published = text_of(f"{atom}published")
    authors = [
        " ".join((node.findtext(f"{atom}name") or "").split())
        for node in entry.findall(f"{atom}author")
    ]
    authors = [author for author in authors if author]
    doi = text_of(f"{arxiv}doi")
    return {
        "title": [title] if title else [],
        "author": authors,
        "abstract": abstract,
        "doi": [doi] if doi else [],
        "identifier": [f"arXiv:{base_id}"],
        "property": ["ARTICLE", "EPRINT_OPENACCESS", "OPENACCESS"],
        "doctype": "eprint",
        "year": published[:4] if published and len(published) >= 4 else None,
        "pub": "arXiv e-prints",
    }


def ads_resolver_records(
    bibcode: str, token: str, timeout: float
) -> list[dict[str, Any]]:
    response = ads_api.request_api(
        "GET",
        f"/resolver/{quote(bibcode, safe='')}/esource",
        token,
        timeout=timeout,
    )
    payload = ads_api.decode_json_response(response, "full-text resolver")
    if not isinstance(payload, dict):
        return []
    records = payload.get("links", {}).get("records", [])
    return [record for record in records if isinstance(record, dict)]


def ordered_unique_strings(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(stripped)
    return result


def arxiv_candidates(arxiv_id: str) -> list[Candidate]:
    encoded = quote(arxiv_id, safe="/.")
    return [
        Candidate(
            source="arxiv",
            version="preprint",
            format="html",
            url=f"https://arxiv.org/html/{encoded}",
            priority=50,
            link_type="DIRECT|ARXIV_HTML",
            access="open",
        ),
        Candidate(
            source="arxiv",
            version="preprint",
            format="pdf",
            url=f"https://arxiv.org/pdf/{encoded}",
            priority=55,
            link_type="DIRECT|ARXIV_PDF",
            access="open",
        ),
    ]


def resolver_candidate(
    record: Mapping[str, Any], properties: set[str]
) -> Candidate | None:
    url = str(record.get("url") or "").strip()
    link_type = str(record.get("link_type") or "").upper()
    if not url or "|" not in link_type:
        return None
    subtype = link_type.rsplit("|", 1)[-1]
    mapping: dict[str, tuple[str, str, str, int]] = {
        "PUB_HTML": ("publisher", "published", "html", 10),
        "PUB_PDF": ("publisher", "published", "pdf", 15),
        "AUTHOR_HTML": ("author", "accepted", "html", 30),
        "AUTHOR_PDF": ("author", "accepted", "pdf", 35),
        "EPRINT_HTML": ("repository", "preprint", "html", 50),
        "EPRINT_PDF": ("repository", "preprint", "pdf", 55),
        "ADS_PDF": ("ads", "scan", "pdf", 70),
    }
    if subtype not in mapping:
        return None
    source, version, output_format, priority = mapping[subtype]
    if "arxiv.org/abs/" in url.lower():
        return None
    if "arxiv.org/" in url.lower():
        arxiv_id = arxiv_id_from_value(url)
        if arxiv_id:
            return None
    access = (
        "open"
        if subtype.startswith(("ADS_", "EPRINT_", "AUTHOR_"))
        or "PUB_OPENACCESS" in properties
        else "unknown"
    )
    if source == "publisher" and access != "open":
        priority += 20
    try:
        normalized_url = normalize_candidate_url(url)
    except FullTextError:
        return None
    return Candidate(
        source=source,
        version=version,
        format=output_format,
        url=normalized_url,
        priority=priority,
        link_type=link_type,
        access=access,
    )


def unpaywall_candidates(
    doi: str,
    email: str,
    *,
    timeout: float,
    max_bytes: int,
) -> list[Candidate]:
    endpoint = f"{UNPAYWALL_URL}/{quote(doi, safe='')}?{urlencode({'email': email})}"
    downloaded = fetch_external(
        endpoint, timeout=timeout, max_bytes=min(max_bytes, 5 * 1024 * 1024)
    )
    try:
        payload = json.loads(downloaded.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FullTextError("Unpaywall returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        return []
    locations: list[Mapping[str, Any]] = []
    best = payload.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    for location in payload.get("oa_locations", []):
        if isinstance(location, dict) and location not in locations:
            locations.append(location)
    version_map = {
        "publishedVersion": "published",
        "acceptedVersion": "accepted",
        "submittedVersion": "preprint",
    }
    base_map = {"published": 10, "accepted": 30, "preprint": 50, "unknown": 80}
    candidates: list[Candidate] = []
    for index, location in enumerate(locations):
        version = version_map.get(str(location.get("version")), "unknown")
        source = "publisher" if location.get("host_type") == "publisher" else "author"
        license_value = str(location.get("license") or "").strip() or None
        for output_format, key, offset in (
            ("html", "url_for_landing_page", 0),
            ("pdf", "url_for_pdf", 5),
        ):
            url = str(location.get(key) or "").strip()
            if not url:
                continue
            try:
                normalized_url = normalize_candidate_url(url)
            except FullTextError:
                continue
            candidates.append(
                Candidate(
                    source=source,
                    version=version,
                    format=output_format,
                    url=normalized_url,
                    priority=base_map[version] + offset + min(index, 9),
                    link_type="UNPAYWALL",
                    license=license_value,
                    access="open",
                )
            )
    return candidates


def deduplicate_candidates(candidates: Iterable[Candidate]) -> list[Candidate]:
    result: list[Candidate] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: item.priority):
        key = candidate.url.lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def discover(
    identifier: str,
    *,
    source: str,
    use_unpaywall: bool,
    timeout: float,
    max_bytes: int,
    environ: Mapping[str, str],
    output_format: str = "auto",
) -> dict[str, Any]:
    identifier_type, normalized_identifier = classify_identifier(identifier)
    token = ads_token_if_available(environ)
    record: dict[str, Any] | None = None
    warnings: list[str] = []
    if identifier_type == "bibcode":
        if not token:
            raise FullTextError(
                "Set ADS_API_TOKEN or ADS_DEV_KEY to resolve an ADS bibcode. "
                f"Create a token at {ads_api.TOKEN_URL}",
                exit_code=2,
            )
        record = ads_search_record(f"bibcode:{normalized_identifier}", token, timeout)
        if record is None:
            raise FullTextError(f"ADS did not return bibcode {normalized_identifier}.")
    elif token:
        query_name = "arxiv" if identifier_type == "arxiv" else "doi"
        try:
            record = ads_search_record(
                f'{query_name}:"{normalized_identifier}"', token, timeout
            )
        except ads_api.CliError as exc:
            warnings.append(f"ads_metadata_lookup_failed: {exc}")
    if record is None and identifier_type == "arxiv":
        try:
            record = arxiv_metadata_record(
                normalized_identifier, timeout=timeout, max_bytes=max_bytes
            )
            if record:
                warnings.append("metadata_source: arxiv")
        except FullTextError as exc:
            warnings.append(f"arxiv_metadata_lookup_failed: {exc}")

    title = first_value(record.get("title")) if record else None
    abstract = record.get("abstract") if record else None
    bibcode = str(record.get("bibcode")) if record and record.get("bibcode") else None
    properties = set(list_value(record.get("property"))) if record else set()
    identifiers = list_value(record.get("identifier")) if record else []
    doi_values = (
        [value for value in list_value(record.get("doi")) if doi_from_value(value)]
        if record
        else []
    )
    if identifier_type == "doi":
        doi_values.insert(0, normalized_identifier)
    doi_values = ordered_unique_strings(doi_values)
    arxiv_ids = ordered_unique_strings(
        candidate
        for candidate in ([normalized_identifier] if identifier_type == "arxiv" else [])
        + [
            value
            for value in (arxiv_id_from_value(item) for item in identifiers)
            if value
        ]
    )

    resolver_records: list[dict[str, Any]] = []
    if bibcode and token:
        try:
            resolver_records = ads_resolver_records(bibcode, token, timeout)
        except ads_api.CliError as exc:
            warnings.append(f"ads_resolver_failed: {exc}")
    for resolver_record in resolver_records:
        possible_id = arxiv_id_from_value(str(resolver_record.get("url") or ""))
        if possible_id and possible_id not in arxiv_ids:
            arxiv_ids.append(possible_id)

    candidates: list[Candidate] = []
    for arxiv_id in arxiv_ids:
        candidates.extend(arxiv_candidates(arxiv_id))
    for resolver_record in resolver_records:
        candidate = resolver_candidate(resolver_record, properties)
        if candidate:
            candidates.append(candidate)

    if use_unpaywall and doi_values:
        email = environ.get("UNPAYWALL_EMAIL", "").strip()
        if not email:
            warnings.append("unpaywall_skipped: set UNPAYWALL_EMAIL")
        else:
            try:
                candidates.extend(
                    unpaywall_candidates(
                        doi_values[0],
                        email,
                        timeout=timeout,
                        max_bytes=max_bytes,
                    )
                )
            except FullTextError as exc:
                warnings.append(f"unpaywall_failed: {exc}")

    if source != "auto":
        candidates = [
            candidate for candidate in candidates if candidate.source == source
        ]
    if output_format != "auto":
        candidates = [
            candidate
            for candidate in candidates
            if candidate.format == output_format
        ]
    candidates = deduplicate_candidates(candidates)
    return {
        "input": identifier,
        "input_type": identifier_type,
        "normalized_identifier": normalized_identifier,
        "bibcode": bibcode,
        "title": title,
        "author": list_value(record.get("author")) if record else [],
        "abstract": abstract,
        "doi": doi_values,
        "arxiv_ids": arxiv_ids,
        "property": sorted(properties),
        "doctype": record.get("doctype") if record else None,
        "year": record.get("year") if record else None,
        "pub": record.get("pub") if record else None,
        "citation_count": record.get("citation_count") if record else None,
        "read_count": record.get("read_count") if record else None,
        "requested_format": output_format,
        "candidates": candidates,
        "warnings": warnings,
    }


def cached_result(manifest_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    selected = payload.get("selected")
    if not isinstance(selected, dict):
        return None
    artifact = selected.get("artifact_path")
    artifact_hash = selected.get("sha256")
    if (
        not artifact
        or not isinstance(artifact_hash, str)
        or not re.fullmatch(r"[0-9a-fA-F]{64}", artifact_hash)
    ):
        return None
    artifact_path = Path(str(artifact))
    if (
        not artifact_path.is_file()
        or sha256_file(artifact_path) != artifact_hash.lower()
    ):
        return None
    text_path = selected.get("text_path")
    if text_path:
        text_hash = selected.get("text_sha256")
        if not isinstance(text_hash, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", text_hash
        ):
            return None
        local_text_path = Path(str(text_path))
        if (
            not local_text_path.is_file()
            or sha256_file(local_text_path) != text_hash.lower()
        ):
            return None
        content_hash = selected.get("content_sha256")
        if content_hash:
            if not isinstance(content_hash, str) or not re.fullmatch(
                r"[0-9a-fA-F]{64}", content_hash
            ):
                return None
            try:
                text = local_text_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
            if canonical_text_sha256(text) != content_hash.lower():
                return None
    payload["cache_hit"] = True
    return payload


def manifest_selection_rank(manifest: Mapping[str, Any]) -> tuple[int, int]:
    selected = manifest.get("selected")
    if not isinstance(selected, Mapping):
        return (99, 99)
    candidate = selected.get("candidate")
    version = candidate.get("version") if isinstance(candidate, Mapping) else None
    version_rank = {
        "published": 0,
        "accepted": 1,
        "preprint": 2,
        "scan": 3,
        "unknown": 4,
    }.get(str(version), 4)
    status_rank = {
        "fulltext": 0,
        "needs_visual_reading": 1,
        "abstract_only": 2,
    }.get(str(manifest.get("status")), 3)
    return (version_rank, status_rank)


def fetch_one(
    identifier: str,
    *,
    source: str,
    cache_root: Path,
    refresh: bool,
    use_unpaywall: bool,
    timeout: float,
    max_bytes: int,
    environ: Mapping[str, str],
    output_format: str = "auto",
) -> dict[str, Any]:
    record_dir = (cache_root / cache_key(identifier)).resolve()
    format_variant = "" if output_format == "auto" else f"-{output_format}"
    request_variant = (
        f"{source}{format_variant}-"
        f"{'unpaywall' if use_unpaywall else 'resolver'}"
    )
    manifest_path = record_dir / f"manifest-{request_variant}.json"
    cached = cached_result(manifest_path)
    if not refresh and cached is not None:
        return cached
    record_dir.mkdir(parents=True, exist_ok=True)
    discovered = discover(
        identifier,
        source=source,
        use_unpaywall=use_unpaywall,
        timeout=timeout,
        max_bytes=max_bytes,
        environ=environ,
        output_format=output_format,
    )
    candidates: list[Candidate] = discovered.pop("candidates")
    attempts: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    visual_fallback: dict[str, Any] | None = None
    for candidate in candidates:
        try:
            result = materialize_candidate(
                candidate,
                record_dir,
                discovered.get("title"),
                required_format=(
                    None if output_format == "auto" else output_format
                ),
                timeout=timeout,
                max_bytes=max_bytes,
                environ=environ,
            )
        except FullTextError as exc:
            attempts.append(
                {"candidate": asdict(candidate), "status": "failed", "error": str(exc)}
            )
            continue
        attempts.append(
            {
                "candidate": asdict(candidate),
                "status": result["status"],
                "final_url": result["final_url"],
            }
        )
        if result["status"] == "fulltext":
            selected = result
            break
        if visual_fallback is None:
            visual_fallback = result
    selected = selected or visual_fallback
    status = selected["status"] if selected else "abstract_only"
    warnings = list(discovered.pop("warnings"))
    if selected and selected["candidate"]["version"] == "preprint":
        warnings.append("selected_fulltext_is_preprint")
    if selected:
        warnings.extend(selected.get("warnings", []))
    if not candidates:
        warnings.append("no_fulltext_candidates")
    elif selected is None:
        warnings.append("all_fulltext_candidates_failed")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "tool_version": VERSION,
        "status": status,
        "cache_hit": False,
        "cache_dir": str(record_dir),
        "manifest_path": str(manifest_path.resolve()),
        "created_at": utc_now(),
        **discovered,
        "candidates": [asdict(candidate) for candidate in candidates],
        "attempts": attempts,
        "selected": selected,
        "warnings": ordered_unique_strings(warnings),
    }
    if (
        refresh
        and cached is not None
        and manifest_selection_rank(cached) < manifest_selection_rank(manifest)
    ):
        fallback = dict(cached)
        fallback["refresh"] = {
            "attempted_at": manifest["created_at"],
            "status": manifest["status"],
            "attempts": manifest["attempts"],
            "warnings": manifest["warnings"],
            "kept_cached_authority": True,
        }
        return fallback
    write_json_file(manifest_path, manifest)
    return manifest


def parse_page_range(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", value)
    if not match:
        raise FullTextError(
            "--pages must be a page number or range such as 1-10.", exit_code=2
        )
    first = int(match.group(1))
    last = int(match.group(2) or first)
    if first < 1 or last < first:
        raise FullTextError("--pages must be a positive ascending range.", exit_code=2)
    if last - first + 1 > 20:
        raise FullTextError("Render at most twenty pages per call.", exit_code=2)
    return first, last


def render_pdf(
    pdf: Path,
    *,
    pages: str,
    output_dir: Path | None,
    dpi: int,
    refresh: bool,
    timeout: float,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    pdf = pdf.expanduser().resolve()
    if not pdf.is_file():
        raise FullTextError(f"PDF does not exist: {pdf}", exit_code=2)
    with pdf.open("rb") as handle:
        magic = handle.read(5)
    if magic != b"%PDF-":
        raise FullTextError(f"File is not a PDF: {pdf}", exit_code=2)
    first, last = parse_page_range(pages)
    pdftoppm = find_executable(environ, "NASA_ADS_PDFTOPPM", "pdftoppm")
    if not pdftoppm:
        raise FullTextError(
            "No PDF renderer is installed. Use the host's native PDF vision "
            "tool or install Poppler/pdftoppm.",
            exit_code=2,
        )
    destination = (
        output_dir.expanduser().resolve()
        if output_dir
        else (pdf.parent / f"{pdf.stem}-pages").resolve()
    )
    destination.mkdir(parents=True, exist_ok=True)
    prefix = destination / f"page-{first:04d}-{last:04d}"
    existing = sorted(destination.glob(f"{prefix.name}-*.png"))
    if existing and not refresh:
        return {
            "status": "cached",
            "pdf_path": str(pdf),
            "page_range": [first, last],
            "dpi": dpi,
            "images": [str(path.resolve()) for path in existing],
        }
    try:
        completed = subprocess.run(
            [
                pdftoppm,
                "-f",
                str(first),
                "-l",
                str(last),
                "-r",
                str(dpi),
                "-png",
                str(pdf),
                str(prefix),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FullTextError(f"PDF rendering failed: {exc}") from exc
    images = sorted(destination.glob(f"{prefix.name}-*.png"))
    if completed.returncode != 0 or not images:
        detail = " ".join((completed.stderr or completed.stdout).split())[:500]
        raise FullTextError(f"PDF rendering failed. {detail}".strip())
    return {
        "status": "rendered",
        "pdf_path": str(pdf),
        "page_range": [first, last],
        "dpi": dpi,
        "renderer": pdftoppm,
        "images": [str(path.resolve()) for path in images],
    }


def execute(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str],
    stdout: TextIO,
) -> int:
    if args.command == "fetch":
        cache_root = (
            Path(args.cache_dir).expanduser().resolve()
            if args.cache_dir
            else default_cache_dir(environ)
        )
        results: list[dict[str, Any]] = []
        failed = False
        for identifier in args.identifiers:
            try:
                result = fetch_one(
                    identifier,
                    source=args.source,
                    cache_root=cache_root,
                    refresh=args.refresh,
                    use_unpaywall=args.use_unpaywall,
                    timeout=args.timeout,
                    max_bytes=args.max_mib,
                    environ=environ,
                    output_format=args.output_format,
                )
            except (
                FullTextError,
                ads_api.CliError,
                OSError,
                subprocess.SubprocessError,
            ) as exc:
                failed = True
                result = {
                    "input": identifier,
                    "status": "error",
                    "error": str(exc),
                }
            results.append(result)
        json.dump({"results": results}, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
        return 1 if failed else 0
    if args.command == "render":
        result = render_pdf(
            Path(args.pdf),
            pages=args.pages,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            dpi=args.dpi,
            refresh=args.refresh,
            timeout=args.timeout,
            environ=environ,
        )
        json.dump(result, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
        return 0
    if args.command == "outline":
        text_path = Path(args.text).expanduser().resolve()
        if not text_path.is_file():
            raise FullTextError(f"Prepared article text does not exist: {text_path}", 2)
        article_text = text_path.read_text(encoding="utf-8", errors="replace")
        result = {
            "status": "outlined",
            "text_path": str(text_path),
            "words": count_words(article_text),
            "headings": infer_text_outline(article_text, limit=args.limit),
        }
        json.dump(result, stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
        return 0
    raise FullTextError(f"Unsupported command: {args.command}", exit_code=2)


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    try:
        return execute(
            args,
            environ=environ if environ is not None else os.environ,
            stdout=output_stream,
        )
    except (FullTextError, OSError, subprocess.SubprocessError) as exc:
        error_stream.write(f"error: {exc}\n")
        return exc.exit_code if isinstance(exc, FullTextError) else 1


def main() -> None:
    ads_api.configure_stdio()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
