#!/usr/bin/env python3
"""Discover, fetch, cache, and prepare lawful full text for SciX records."""

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
from urllib.parse import quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree

import ads_api

VERSION = "3.2.1"
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
# Prepared HTML text marks scripts and carries TeX for math; cached text from
# an earlier extraction is prepared again from its cached artifact.
HTML_TEXT_MODE = "math-markup"
TEX_SCRIPT_TYPES = {"math/tex", "math/latex"}
# MathML children after the base become scripts, fraction parts, or root indices.
MATH_CHILD_AFFIXES: dict[str, dict[int, tuple[str, str]]] = {
    "msup": {1: ("^{", "}")},
    "msub": {1: ("_{", "}")},
    "msubsup": {1: ("_{", "}"), 2: ("^{", "}")},
    "munder": {1: ("_{", "}")},
    "mover": {1: ("^{", "}")},
    "munderover": {1: ("_{", "}"), 2: ("^{", "}")},
    "mfrac": {0: ("(", ")"), 1: ("/(", ")")},
    "mroot": {0: ("root(", ""), 1: (", ", ")")},
}
# Math and script markup, which prose detection reads past.
MARKUP_SPAN_RE = re.compile(r"\$\$.+?\$\$|\$[^$\n]+\$|[\^_]\{[^{}\n]*\}", re.DOTALL)
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
    """Extract readable blocks while preferring article/main content.

    Superscripts and subscripts become ``^{...}`` and ``_{...}`` so that
    ``10^{16}`` stays distinct from ``1016``. MathML contributes its TeX source,
    from the ``alttext`` attribute or a TeX annotation, as ``$...$``, or as
    ``$$...$$`` on its own line for a displayed equation; MathML without TeX
    keeps its scripts and fractions. ``<script type="math/tex">`` contributes
    its TeX the same way.
    """

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
        self.scripts: list[tuple[str, list[str]]] = []
        self.tex_script: list[str] | None = None
        self.tex_script_display = False
        self.math: dict[str, Any] | None = None

    def append(self, value: str) -> None:
        if self.skip_depth:
            return
        if self.scripts:
            self.scripts[-1][1].append(value)
            return
        self.all_parts.append(value)
        if self.focus_depth:
            self.focus_parts.append(value)
        if self.heading_depth:
            self.heading_parts.append(value)

    def append_tex(self, tex: str, display: bool) -> None:
        tex = " ".join(tex.split())
        if tex:
            self.append(f"\n$${tex}$$\n" if display else f"${tex}$")

    def close_script(self) -> None:
        kind, parts = self.scripts.pop()
        content = " ".join("".join(parts).split())
        if content:
            self.append(("^{" if kind == "sup" else "_{") + content + "}")

    def start_math(self, attributes: Mapping[str, str]) -> None:
        self.math = {
            "alttext": attributes.get("alttext", ""),
            "display": attributes.get("display", "").lower() == "block",
            "parts": [],
            "tex": [],
            "stack": [],
            "annotation": False,
            "ignore": 0,
        }

    def finish_math(self) -> None:
        math, self.math = self.math, None
        if math is None:
            return
        tex = math["alttext"] or "".join(math["tex"])
        if tex.strip():
            self.append_tex(tex, math["display"])
            return
        text = " ".join("".join(math["parts"]).split())
        if text:
            self.append(f"\n{text}\n" if math["display"] else text)

    def math_starttag(self, tag: str, attributes: Mapping[str, str]) -> None:
        math = self.math
        assert math is not None
        if math["ignore"]:
            math["ignore"] += 1
            return
        if tag == "annotation" and "tex" in attributes.get("encoding", "").lower():
            math["annotation"] = True
            return
        if tag in {"annotation", "annotation-xml"}:
            math["ignore"] = 1
            return
        prefix = suffix = ""
        if math["stack"]:
            parent = math["stack"][-1]
            prefix, suffix = MATH_CHILD_AFFIXES.get(parent[0], {}).get(
                parent[1], ("", "")
            )
            parent[1] += 1
        if tag == "msqrt":
            prefix, suffix = prefix + "sqrt(", ")" + suffix
        math["parts"].append(prefix)
        math["stack"].append([tag, 0, suffix])

    def math_endtag(self, tag: str) -> None:
        math = self.math
        assert math is not None
        if math["ignore"]:
            math["ignore"] -= 1
            return
        if math["annotation"]:
            if tag == "annotation":
                math["annotation"] = False
            return
        if tag == "math":
            self.finish_math()
            return
        if not any(entry[0] == tag for entry in math["stack"]):
            return
        while math["stack"]:
            entry = math["stack"].pop()
            math["parts"].append(entry[2])
            if entry[0] == tag:
                break

    def flush(self) -> None:
        """Close math and scripts left open by malformed markup."""
        self.finish_math()
        while self.scripts:
            self.close_script()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {name.lower(): value or "" for name, value in attrs}
        if self.math is not None:
            if tag not in BLOCK_TAGS:
                self.math_starttag(tag, attributes)
                return
            self.finish_math()
        if self.tex_script is not None:
            return
        if tag == "script" and not self.skip_depth:
            kind = attributes.get("type", "").lower().replace(" ", "")
            if kind.split(";")[0] in TEX_SCRIPT_TYPES:
                self.tex_script = []
                self.tex_script_display = "mode=display" in kind
                return
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "math":
            self.start_math(attributes)
            return
        if tag in {"sup", "sub"}:
            self.scripts.append((tag, []))
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
        if self.math is not None:
            if tag not in BLOCK_TAGS:
                self.math_endtag(tag)
                return
            self.finish_math()
        if self.tex_script is not None:
            if tag == "script":
                tex, self.tex_script = "".join(self.tex_script), None
                self.append_tex(tex, self.tex_script_display)
            return
        if tag in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"sup", "sub"}:
            if self.scripts and self.scripts[-1][0] == tag:
                self.close_script()
            return
        if tag in BLOCK_TAGS:
            # A superscript or subscript never spans a block boundary.
            while self.scripts:
                self.close_script()
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
        if self.math is not None:
            math = self.math
            if not math["ignore"]:
                (math["tex"] if math["annotation"] else math["parts"]).append(data)
            return
        if self.tex_script is not None:
            self.tex_script.append(data)
            return
        if self.skip_depth:
            return
        self.append(data)
        if self.title_depth:
            self.title_parts.append(data)

    def readable_text(self) -> tuple[str, bool]:
        self.flush()
        focused = normalize_text("".join(self.focus_parts))
        if count_words(focused) >= 250:
            return focused, True
        return normalize_text("".join(self.all_parts)), False

    def full_text(self) -> str:
        self.flush()
        return normalize_text("".join(self.all_parts))

    def document_title(self) -> str:
        return normalize_text("".join(self.title_parts))


class SafeRedirectHandler(HTTPRedirectHandler):
    """Follow bounded HTTPS redirects without carrying SciX credentials."""

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
        help="bibcode, DOI, arXiv ID, or arXiv URL",
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
        "--library-dir", help="personal library used for metadata capture"
    )
    fetch.add_argument(
        "--no-store",
        action="store_true",
        help="prepare article files without capturing metadata in the personal library",
    )
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

    local = subparsers.add_parser(
        "import",
        help="prepare a user-supplied PDF or HTML copy of an article for reading",
    )
    local.add_argument("file", help="local PDF or HTML file holding the article")
    local.add_argument(
        "--identifier",
        required=True,
        help="bibcode, DOI, or arXiv ID of the article in the file",
    )
    local.add_argument(
        "--version",
        required=True,
        choices=("published", "accepted", "preprint", "scan"),
        help="article version the file holds",
    )
    local.add_argument(
        "--source-url", help="HTTPS address the file came from, recorded as provenance"
    )
    local.add_argument("--cache-dir", help="cache root; overrides the default")
    local.add_argument(
        "--library-dir", help="personal library used for metadata capture"
    )
    local.add_argument(
        "--no-store",
        action="store_true",
        help="prepare the file without capturing metadata in the personal library",
    )
    local.add_argument(
        "--timeout",
        type=ads_api.bounded_timeout,
        default=DEFAULT_TIMEOUT,
        help="metadata request timeout in seconds (default: 45)",
    )
    local.add_argument(
        "--max-mib",
        type=bounded_megabytes,
        default=DEFAULT_MAX_BYTES,
        metavar="MIB",
        help="maximum file size (default: 100 MiB)",
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
        "outline",
        help="extract a reviewable section outline from prepared article text",
    )
    outline.add_argument(
        "text",
        help="prepared article text path, or a fetch manifest to also use its HTML headings",
    )
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


APPENDIX_HEADING_RE = re.compile(
    r"^(?:Appendix|Supplement)\s+[A-Z0-9]+[:.)]?\s+", re.IGNORECASE
)
HEADING_WORD_RE = re.compile(r"[^\W\d_]{2,}")
REFERENCE_HEADINGS = {"references", "bibliography"}


def infer_text_outline(value: str, *, limit: int = 200) -> list[str]:
    """Infer section headings from prepared text, in reading order.

    Publisher pages often repeat the heading list as a table of contents before
    the article, so a repeated heading keeps its last occurrence, an unnumbered
    entry gives way to the numbered heading of the same title, and the
    reference list starts at the last ``References`` heading.
    """
    # Section numbers have at most two digits per level, so years and
    # measurements at the start of a wrapped text line are not headings.
    numbered = re.compile(
        r"^(?:§\s*\d{1,2}(?:\.\d{1,2}){0,3}\s+|"
        r"(?:\d{1,2}(?:\.\d{1,2}){0,3}|[A-Z]\.\d{1,2}(?:\.\d{1,2}){0,2}|"
        r"(?-i:[IVXLC]+)(?:\.\d{1,2}){1,3})[.)]?\s+|"
        r"[IVXLC]+[.)]\s+|"
        r"(?-i:[IVXLC]+)\s+(?=(?-i:[A-Z]))|"
        r"(?:Appendix|Supplement)\s+[A-Z0-9]+[:.)]?\s+)(\S.*)$",
        re.IGNORECASE,
    )
    named = re.compile(
        r"^(?:abstract|introduction|background|observations?|data|methods?|"
        r"analysis|results?|discussion|conclusions?|summary|limitations?|"
        r"acknowledg(?:e)?ments?|references|bibliography)$",
        re.IGNORECASE,
    )
    candidates: list[tuple[str, str, str | None]] = []
    for raw_line in value.splitlines():
        line = " ".join(raw_line.split())
        if not line or len(line) > 180:
            continue
        if MEASUREMENT_ONLY_RE.fullmatch(line) or DATE_ONLY_RE.fullmatch(line):
            continue
        if re.match(r"^(?:Figure|Table)\s+\d", line, re.IGNORECASE):
            continue
        match = numbered.match(line)
        if match:
            heading_text = match.group(1)
            # A title opens with a letter or digit and holds a word; equation and
            # table fragments such as "2 = 3.529) is" or "10 3 p = 10 4" do neither.
            if not heading_text[0].isalnum() or not HEADING_WORD_RE.search(heading_text):
                continue
            if ". " in heading_text or heading_text[0].islower():
                continue
            candidates.append((line, line.casefold(), heading_text.casefold()))
        elif named.match(line) and line[0].isupper():
            # Lowercase single words are usually figure labels in PDF text.
            candidates.append((line, line.casefold(), None))
    reference_starts = [
        index for index, (_line, key, _title) in enumerate(candidates) if key in REFERENCE_HEADINGS
    ]
    references_at = reference_starts[-1] if reference_starts else len(candidates)
    numbered_titles = {title for _line, _key, title in candidates if title}
    last_index = {key: index for index, (_line, key, _title) in enumerate(candidates)}
    headings: list[str] = []
    in_references = False
    for index, (line, key, title) in enumerate(candidates):
        if index == references_at:
            in_references = True
        elif in_references:
            if not APPENDIX_HEADING_RE.match(line):
                continue
            in_references = False
        if last_index[key] != index or (title is None and key in numbered_titles):
            continue
        headings.append(line)
        if len(headings) >= limit:
            break
    return headings


def article_outline(
    text: str,
    manifest: Mapping[str, Any] | None = None,
    *,
    limit: int = 400,
    reading_headings: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Section spans from the manifest's HTML headings or the inferred outline.

    The candidate that places more headings on lines of ``text`` wins. Headings
    a reader recorded in a digest then fill sections that the outline missed.
    A PDF manifest holds the outline its own preparation inferred, so the text
    is inferred again here.
    """
    candidates = [infer_text_outline(text, limit=limit)]
    selected = (manifest or {}).get("selected") or {}
    outline = (selected.get("statistics") or {}).get("outline")
    if (
        str(selected.get("actual_format") or "").lower() != "pdf"
        and isinstance(outline, list)
        and all(isinstance(item, str) for item in outline)
    ):
        candidates.insert(0, outline)
    best: list[dict[str, Any]] = []
    for headings in candidates:
        located = locate_headings(text, headings)
        if len(located) > len(best):
            best = located
    if reading_headings:
        best = add_reading_headings(text, best, reading_headings)
    return best


FRONT_MATTER_HEADING = "Front matter"
NUMBERED_HEADING_RE = re.compile(
    r"^(?:§\s*)?(?:\d{1,2}(?:\.\d{1,2}){0,3}[.):]?|[A-Z](?:\.\d{1,2}){1,3}[.):]?|"
    r"[A-Z][.)]|(?-i:[IVXLC]+)[.):]?|(?:appendix|supplement)\s+[A-Z0-9]+[.):]?)"
    r"\s+\S",
    re.IGNORECASE,
)


def heading_key(value: str) -> str:
    """Case-, spacing-, and punctuation-insensitive heading comparison key."""
    return " ".join(re.sub(r"[^\w\s]", " ", str(value).casefold()).split())


def line_starts(text: str) -> tuple[list[str], list[int]]:
    lines = text.split("\n")
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1
    return lines, starts


def locate_headings(text: str, headings: Sequence[str]) -> list[dict[str, Any]]:
    """Place outline headings on their own lines; a section runs to the next one.

    Returns sections with the heading, its one-based ``line``, character
    ``start`` and ``end`` offsets, and the number of ``lines`` it spans. Text
    before the first heading becomes a front-matter section.
    """
    lines, _starts = line_starts(text)
    normalized = [" ".join(line.split()).casefold() for line in lines]
    placed: list[tuple[str, int]] = []
    cursor = 0
    for heading in headings:
        key = " ".join(str(heading).split()).casefold()
        for index in range(cursor, len(lines)):
            if normalized[index] == key:
                placed.append((str(heading), index))
                cursor = index + 1
                break
    return sections_from_placements(text, placed)


def add_reading_headings(
    text: str,
    sections: Sequence[Mapping[str, Any]],
    headings: Sequence[str],
) -> list[dict[str, Any]]:
    """Place digest headings that no located section already covers.

    A heading matches a whole line, or for a numbered heading such as
    ``V. Searches`` the start of a line that continues with the section's first
    sentence, as PDF text extraction often joins them.
    """
    lines, _starts = line_starts(text)
    keys = [heading_key(line) for line in lines]
    placed = [
        (str(section["heading"]), int(section["line"]) - 1)
        for section in sections
        if section["heading"] != FRONT_MATTER_HEADING
    ]
    covered = {heading_key(heading): index for heading, index in placed}
    occupied = set(covered.values())
    cursor = 0
    for heading in headings:
        key = heading_key(heading)
        if not key:
            continue
        existing = next(
            (
                index
                for existing_key, index in covered.items()
                if existing_key == key or existing_key.startswith(key + " ")
            ),
            None,
        )
        if existing is not None:
            cursor = max(cursor, existing + 1)
            continue
        free = [index for index in range(cursor, len(lines)) if index not in occupied]
        found = next((index for index in free if keys[index] == key), None)
        if found is None and NUMBERED_HEADING_RE.match(str(heading).strip()):
            found = next(
                (index for index in free if keys[index].startswith(key + " ")), None
            )
        if found is not None:
            placed.append((str(heading), found))
            covered[key] = found
            occupied.add(found)
            cursor = found + 1
    placed.sort(key=lambda item: item[1])
    return sections_from_placements(text, placed)


def sections_from_placements(
    text: str, placed: Sequence[tuple[str, int]]
) -> list[dict[str, Any]]:
    lines, starts = line_starts(text)
    placed = list(placed)
    if not placed or (placed[0][1] > 0 and text[: starts[placed[0][1]]].strip()):
        placed.insert(0, (FRONT_MATTER_HEADING, 0))
    sections: list[dict[str, Any]] = []
    for position, (heading, index) in enumerate(placed):
        next_index = placed[position + 1][1] if position + 1 < len(placed) else len(lines)
        end = starts[next_index] if next_index < len(lines) else len(text)
        sections.append(
            {
                "heading": heading,
                "line": index + 1,
                "lines": next_index - index,
                "start": starts[index],
                "end": end,
            }
        )
    return sections


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
    if parsed.scheme and (parsed.hostname or "").lower() in {
        "arxiv.org",
        "www.arxiv.org",
        "export.arxiv.org",
    }:
        match = re.match(r"^/(?:abs|html|pdf|src)/(.+?)(?:\.pdf)?$", parsed.path)
        if not match:
            return None
        candidate = unquote(match.group(1))
    candidate = candidate.strip().rstrip("/")
    if ARXIV_NEW_RE.fullmatch(candidate) or ARXIV_OLD_RE.fullmatch(candidate):
        return candidate
    return None


def doi_from_value(value: str) -> str | None:
    candidate = value.strip()
    candidate = re.sub(r"^doi:\s*", "", candidate, flags=re.IGNORECASE)
    parsed = urlsplit(candidate)
    if parsed.scheme and parsed.netloc.lower() in {"doi.org", "dx.doi.org"}:
        candidate = unquote(parsed.path.lstrip("/"))
    candidate = candidate.strip().rstrip(".")
    return candidate if DOI_RE.fullmatch(candidate) else None


def classify_identifier(identifier: str) -> tuple[str, str]:
    arxiv_id = arxiv_id_from_value(identifier)
    if arxiv_id:
        return "arxiv", arxiv_id
    doi = doi_from_value(identifier)
    if doi:
        return "doi", doi
    stripped = re.sub(r"^bibcode:\s*", "", identifier.strip(), flags=re.IGNORECASE)
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
    if hostname == "localhost" or hostname.endswith((".local", ".localhost")):
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


SUBSCRIPTION_PREVIEW_MARKERS = (
    "this is a preview of subscription content",
    "access through your institution",
    "buy this article",
    "subscribe to this journal",
    "purchase on springerlink",
    "get full access to this article",
    "rent this article",
    "log in to view full text",
    "sign in to view full text",
)


REFERENCE_LIST_HEADING_RE = re.compile(
    r"^\s*(?:references|bibliography|reference list|literature cited|works cited)"
    r"(?:\s*\(\d+\))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# Landing pages carry an abstract, author and affiliation lists, and references.
# Real articles, including short research notes, carry far more body prose.
MIN_BODY_PROSE_WORDS = 300
ABSTRACT_SKIP_WORDS = 500


def text_before_references(value: str) -> str:
    """Text before the reference list, which starts at its last heading.

    Publisher pages often link ``References`` from a table of contents first.
    """
    matches = list(REFERENCE_LIST_HEADING_RE.finditer(value))
    return value[: matches[-1].start()] if matches else value


LOWERCASE_WORD_RE = re.compile(r"[a-z][a-z'-]*[.,;:)]?")
CJK_CHARACTER_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")


def is_prose(paragraph: str) -> bool:
    """Running text: twelve or more words, few commas, mostly lowercase words.

    Author and affiliation lists and reference entries consist of names,
    initials, places, and numbers, so few of their words are lowercase.
    Chinese, Japanese, and Korean text counts by its characters. Math and
    script markup are left out.
    """
    paragraph = MARKUP_SPAN_RE.sub(" ", paragraph)
    if len(CJK_CHARACTER_RE.findall(paragraph)) >= 24:
        return True
    tokens = paragraph.split()
    if len(tokens) < 12 or paragraph.count(",") > 0.2 * len(tokens):
        return False
    lowercase = sum(1 for token in tokens if LOWERCASE_WORD_RE.fullmatch(token))
    return lowercase >= 0.4 * len(tokens)


def prose_words(paragraph: str) -> int:
    """Word count without math markup, with two CJK characters taken as one word."""
    paragraph = MARKUP_SPAN_RE.sub(" ", paragraph)
    return count_words(CJK_CHARACTER_RE.sub(" ", paragraph)) + (
        len(CJK_CHARACTER_RE.findall(paragraph)) // 2
    )


def text_paragraphs(text: str) -> Iterable[tuple[str, bool]]:
    """Paragraphs joined across hard line wraps, each flagged when it opens an abstract."""
    lines: list[str] = []
    opens_abstract = False
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if line.casefold().rstrip(":. ") == "abstract":
            if lines:
                yield " ".join(lines), opens_abstract
            lines, opens_abstract = [], True
        elif line:
            lines.append(line)
        elif lines:
            yield " ".join(lines), opens_abstract
            lines, opens_abstract = [], False
    if lines:
        yield " ".join(lines), opens_abstract


def body_prose(text: str) -> tuple[int, bool]:
    """Words of body prose before the reference list, and whether an abstract was seen.

    The prose paragraphs that follow an ``Abstract`` heading are excluded.
    """
    total = 0
    abstract_seen = False
    abstract_budget = 0
    for paragraph, opens_abstract in text_paragraphs(text_before_references(text)):
        if opens_abstract:
            abstract_seen = True
            abstract_budget = ABSTRACT_SKIP_WORDS
        words = prose_words(paragraph)
        if not is_prose(paragraph):
            if abstract_budget and len(paragraph.split()) <= 12:
                abstract_budget = 0  # A heading or label ends the abstract.
            continue
        skipped = min(words, abstract_budget)
        abstract_budget -= skipped
        total += words - skipped
    return total, abstract_seen


def is_landing_page(prose_words: int, abstract_seen: bool) -> bool:
    """An abstract followed by almost no body prose marks an abstract landing page.

    Short documents without an abstract, such as telegrams, notices, and
    software records, are complete as served.
    """
    return abstract_seen and prose_words < MIN_BODY_PROSE_WORDS


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
    if any(marker in full_text_lower for marker in SUBSCRIPTION_PREVIEW_MARKERS):
        body_words = count_words(text_before_references(text))
        if body_words < 1500:
            raise FullTextError(
                "HTML candidate is a subscription preview "
                f"({body_words} words before the references)."
            )
    if word_count < 300:
        raise FullTextError(
            f"HTML candidate contains too little article text ({word_count} words)."
        )
    if not used_focus and len(parser.headings) < 3 and word_count < 2500:
        raise FullTextError("HTML candidate does not expose a full article structure.")
    prose_words, abstract_seen = body_prose(text)
    if is_landing_page(prose_words, abstract_seen):
        raise FullTextError(
            "HTML candidate is a landing page without the article body "
            f"({prose_words} words of body prose after the abstract)."
        )
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
        "text_mode": HTML_TEXT_MODE,
        "body_prose_words": prose_words,
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
        from pypdf.errors import PyPdfError  # type: ignore[import-not-found]
    except ImportError:
        pass
    else:
        try:
            return len(PdfReader(str(pdf_path)).pages), "pypdf"
        except (OSError, ValueError, PyPdfError):
            pass
    try:
        approximate = len(re.findall(rb"/Type\s*/Page\b", pdf_path.read_bytes()))
    except OSError:
        approximate = 0
    return (approximate or None), ("pdf-marker-count" if approximate else None)


PDF_TEXT_MODE = "reading-order"


def extract_pdf_text(
    pdf_path: Path,
    text_path: Path,
    environ: Mapping[str, str],
) -> tuple[str | None, str | None, str | None]:
    """Extract PDF text in reading order.

    Physical-layout extraction places both columns of a two-column page on one
    line, and whitespace normalization would then interleave them.
    """
    pdftotext = find_executable(environ, "NASA_ADS_PDFTOTEXT", "pdftotext")
    if pdftotext:
        try:
            completed = subprocess.run(
                [
                    pdftotext,
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
        from pypdf.errors import PyPdfError  # type: ignore[import-not-found]
    except ImportError:
        return None, None, "No PDF text extractor is installed."
    try:
        pages = PdfReader(str(pdf_path)).pages
        text = "\n\n".join((page.extract_text() or "") for page in pages)
        return normalize_text(text), "pypdf", None
    except (OSError, ValueError, PyPdfError) as exc:
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
            "text_mode": PDF_TEXT_MODE if extractor else None,
            "outline": infer_text_outline(text or ""),
        },
        warnings,
    )


def artifact_format(body: bytes, content_type: str | None) -> str:
    stripped = body.lstrip()
    if stripped.startswith(b"\xef\xbb\xbf"):
        stripped = stripped[3:].lstrip()
    if stripped.startswith(b"%PDF-"):
        return "pdf"
    if stripped[:200].lower().startswith((b"<!doctype html", b"<html", b"<?xml")):
        return "html"
    if content_type == "application/pdf":
        raise FullTextError("PDF response lacks the PDF file signature.")
    if content_type in {"text/html", "application/xhtml+xml"}:
        return "html"
    raise FullTextError(
        f"Unsupported full-text content type: {content_type or 'unknown'}"
    )


def actual_format(downloaded: Downloaded) -> str:
    return artifact_format(downloaded.body, downloaded.content_type)


def candidate_stem(candidate: Candidate, selected_format: str) -> str:
    raw = f"{candidate.source}-{candidate.version}-{selected_format}"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")


def text_file_path(artifact_path: Path, text_mode: str) -> Path:
    """Prepared text named by extraction mode, so earlier text is preserved."""
    return artifact_path.with_name(f"{artifact_path.stem}.{text_mode}.txt")


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
    pinned_arxiv = arxiv_id_from_value(candidate.url)
    if pinned_arxiv and re.search(r"v\d+$", pinned_arxiv):
        if arxiv_id_from_value(downloaded.final_url) != pinned_arxiv:
            raise FullTextError(
                "Downloaded arXiv URL does not preserve the requested version."
            )
    return prepare_artifact(
        downloaded.body,
        candidate,
        record_dir,
        expected_title,
        final_url=downloaded.final_url,
        content_type=downloaded.content_type,
        required_format=required_format,
        environ=environ,
    )


def prepare_artifact(
    body: bytes,
    candidate: Candidate,
    record_dir: Path,
    expected_title: str | None,
    *,
    final_url: str | None,
    content_type: str | None,
    environ: Mapping[str, str],
    required_format: str | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Validate an article artifact, store it, and prepare its text."""
    selected_format = artifact_format(body, content_type)
    if required_format is not None and selected_format != required_format:
        raise FullTextError(
            f"Candidate advertised {candidate.format} but returned "
            f"{selected_format}; {required_format} was required."
        )
    stem = candidate_stem(candidate, selected_format)
    artifact_hash = sha256_bytes(body)
    artifact_path = (
        record_dir / "artifacts" / f"{stem}-{artifact_hash[:16]}.{selected_format}"
    ).resolve()
    common: dict[str, Any] = {
        "candidate": asdict(candidate),
        "actual_format": selected_format,
        "final_url": final_url,
        "artifact_path": str(artifact_path),
        "sha256": artifact_hash,
        "content_sha256": artifact_hash,
        "bytes": len(body),
        "content_type": content_type or None,
        "retrieved_at": retrieved_at or utc_now(),
    }
    if selected_format == "html":
        text, statistics = extract_html(body, expected_title)
        atomic_write_bytes(artifact_path, body)
        text_path = text_file_path(artifact_path, HTML_TEXT_MODE)
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

    atomic_write_bytes(artifact_path, body)
    page_count, page_counter = pdf_page_count(artifact_path, environ)
    text_path = text_file_path(artifact_path, PDF_TEXT_MODE)
    text, extractor, extraction_error = extract_pdf_text(
        artifact_path, text_path, environ
    )
    status, statistics, warnings = assess_pdf_text(text, page_count, extractor)
    if status == "fulltext" and expected_title:
        expected = {
            part
            for part in re.findall(r"[a-z0-9]+", expected_title.casefold())
            if len(part) >= 4
        }
        found = set(re.findall(r"[a-z0-9]+", (text or "")[:20000].casefold()))
        if expected and len(expected & found) / len(expected) < 0.35:
            raise FullTextError(
                "PDF text does not match the target title; verify the article identity."
            )
    if status == "needs_visual_reading":
        warnings.append("pdf_identity_requires_visual_check")
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


def ads_search_record(query: str, token: str, timeout: float) -> dict[str, Any] | None:
    response = ads_api.request_api(
        "GET",
        "/search/query",
        token,
        # The same fields as search capture, so both describe one source alike.
        query=[("q", query), ("fl", ads_api.DEFAULT_FIELDS), ("rows", 1)],
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
        "https://export.arxiv.org/api/query?" + urlencode({"id_list": arxiv_id}),
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
    if (
        not returned_id
        or re.sub(r"v\d+$", "", returned_id, flags=re.IGNORECASE) != base_id
    ):
        return None
    if re.search(r"v\d+$", arxiv_id) and returned_id.casefold() != arxiv_id.casefold():
        raise FullTextError(
            "arXiv metadata does not match the explicitly requested version."
        )
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
        "identifier": [f"arXiv:{returned_id}"],
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


VERSION_AUTHORITY = {"published": 0, "accepted": 1, "preprint": 2, "scan": 3}


def version_authority(kind: Any) -> int:
    """Rank of a version kind; a lower rank is the more authoritative text."""
    return VERSION_AUTHORITY.get(str(kind), len(VERSION_AUTHORITY))


def deduplicate_candidates(candidates: Iterable[Candidate]) -> list[Candidate]:
    result: list[Candidate] = []
    seen: set[str] = set()
    for candidate in sorted(
        candidates, key=lambda item: (version_authority(item.version), item.priority)
    ):
        key = candidate.url.rstrip("/")
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
    find_candidates: bool = True,
) -> dict[str, Any]:
    """Resolve an identifier's metadata and, unless disabled, its full-text candidates."""
    identifier_type, normalized_identifier = classify_identifier(identifier)
    token = ads_api.token_if_available(environ)
    record: dict[str, Any] | None = None
    warnings: list[str] = []
    if identifier_type == "bibcode":
        if not token:
            raise FullTextError(
                f"Set {ads_api.TOKEN_ENV} to resolve a bibcode. "
                f"Create a token at {ads_api.TOKEN_URL}",
                exit_code=2,
            )
        record = ads_search_record(f"bibcode:{normalized_identifier}", token, timeout)
        if record is None:
            raise FullTextError(f"SciX did not return bibcode {normalized_identifier}.")
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
    elif identifier_type == "arxiv" and re.search(r"v\d+$", normalized_identifier):
        publication_metadata = record
        record = {**record, "abstract": None}
        try:
            exact_metadata = arxiv_metadata_record(
                normalized_identifier, timeout=timeout, max_bytes=max_bytes
            )
            if exact_metadata:
                record = {
                    **publication_metadata,
                    **exact_metadata,
                    "bibcode": record.get("bibcode"),
                    "doi": ordered_unique_strings(
                        [
                            *list_value(record.get("doi")),
                            *list_value(exact_metadata.get("doi")),
                        ]
                    ),
                    # The requested preprint version has no journal locators.
                    **{
                        field: None
                        for field in ("volume", "issue", "page", "eid", "pubdate")
                    },
                }
            else:
                warnings.append("metadata_abstract_unverified_for_requested_version")
        except FullTextError as exc:
            warnings.append(f"arxiv_version_metadata_failed: {exc}")

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
    if find_candidates and bibcode and token:
        try:
            resolver_records = ads_resolver_records(bibcode, token, timeout)
        except ads_api.CliError as exc:
            warnings.append(f"ads_resolver_failed: {exc}")
    for resolver_record in resolver_records:
        possible_id = arxiv_id_from_value(str(resolver_record.get("url") or ""))
        if possible_id and possible_id not in arxiv_ids:
            arxiv_ids.append(possible_id)

    candidates: list[Candidate] = []
    for arxiv_id in arxiv_ids if find_candidates else []:
        candidates.extend(arxiv_candidates(arxiv_id))
    for resolver_record in resolver_records:
        candidate = resolver_candidate(resolver_record, properties)
        if candidate:
            candidates.append(candidate)

    if find_candidates and use_unpaywall and doi_values:
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
    if identifier_type == "arxiv" and re.search(r"v\d+$", normalized_identifier):
        candidates = [
            candidate
            for candidate in candidates
            if arxiv_id_from_value(candidate.url) == normalized_identifier
        ]
    if output_format != "auto":
        candidates = [
            candidate for candidate in candidates if candidate.format == output_format
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
        "uat": list_value(record.get("uat")) if record else [],
        "has": list_value(record.get("has")) if record else [],
        **{
            field: record.get(field) if record else None
            for field in ("volume", "issue", "page", "eid", "pubdate")
        },
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
    requested = arxiv_id_from_value(
        str(payload.get("normalized_identifier") or payload.get("input") or "")
    )
    if requested and re.search(r"v\d+$", requested):
        if arxiv_id_from_value(str(selected.get("final_url") or "")) != requested:
            return None
    text_path = selected.get("text_path")
    if payload.get("status") == "fulltext" and not text_path:
        return None
    if payload.get("status") not in {"fulltext", "needs_visual_reading"}:
        return None
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
            actual_content_hash = (
                canonical_text_sha256(text)
                if payload.get("status") == "fulltext"
                else artifact_hash.lower()
            )
            if actual_content_hash != content_hash.lower():
                return None
        if payload.get("status") == "fulltext" and not current_extraction(
            selected, local_text_path
        ):
            return None
    payload["cache_hit"] = True
    return payload


def current_extraction(selected: Mapping[str, Any], text_path: Path) -> bool:
    """Whether a cached full-text selection meets the current validation rules.

    Older caches can hold interleaved two-column PDF text, HTML text that
    dropped superscripts and math, or a publisher landing page accepted as an
    article. Their cached artifacts are prepared again, and a selection that no
    longer validates is retrieved again.
    """
    statistics = selected.get("statistics")
    statistics = statistics if isinstance(statistics, Mapping) else {}
    selected_format = selected.get("actual_format")
    if selected_format == "pdf":
        return statistics.get("text_mode") == PDF_TEXT_MODE
    if selected_format == "html":
        if statistics.get("text_mode") != HTML_TEXT_MODE:
            return False
        try:
            text = text_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return not is_landing_page(*body_prose(text))
    return True


def prepare_cached_again(
    manifest_path: Path, environ: Mapping[str, str]
) -> dict[str, Any] | None:
    """Prepare a cached full-text selection again from its verified artifact.

    Returns the updated manifest, or None when the artifact is missing or the
    selection no longer validates, so the caller retrieves it again.
    """
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("status") != "fulltext":
        return None
    selected = payload.get("selected")
    if not isinstance(selected, dict) or selected.get("actual_format") not in {
        "html",
        "pdf",
    }:
        return None
    artifact = Path(str(selected.get("artifact_path") or ""))
    artifact_hash = str(selected.get("sha256") or "").lower()
    candidate_fields = selected.get("candidate")
    if (
        not artifact.is_file()
        or sha256_file(artifact) != artifact_hash
        or not isinstance(candidate_fields, dict)
    ):
        return None
    requested = arxiv_id_from_value(
        str(payload.get("normalized_identifier") or payload.get("input") or "")
    )
    if requested and re.search(r"v\d+$", requested):
        if arxiv_id_from_value(str(selected.get("final_url") or "")) != requested:
            return None
    try:
        candidate = Candidate(
            **{
                name: candidate_fields[name]
                for name in Candidate.__dataclass_fields__
                if name in candidate_fields
            }
        )
        prepared = prepare_artifact(
            artifact.read_bytes(),
            candidate,
            manifest_path.parent,
            payload.get("title"),
            final_url=selected.get("final_url"),
            content_type=selected.get("content_type"),
            environ=environ,
            retrieved_at=selected.get("retrieved_at"),
        )
    except (FullTextError, TypeError, OSError, subprocess.SubprocessError):
        return None
    manifest = dict(payload)
    manifest["status"] = prepared["status"]
    manifest["selected"] = prepared
    manifest["cache_hit"] = True
    manifest["warnings"] = ordered_unique_strings(
        [
            *list_value(payload.get("warnings")),
            *prepared.get("warnings", []),
            "text_prepared_again_from_cached_artifact",
        ]
    )
    write_json_file(manifest_path, manifest)
    return manifest


def arxiv_version_labels(manifest: Mapping[str, Any]) -> list[str]:
    """Explicit arXiv versions, such as ``2304.14665v2``, that the selected article names."""
    selected = manifest.get("selected")
    if not isinstance(selected, Mapping):
        return []
    candidate = selected.get("candidate")
    labels: list[str] = []
    for value in (
        selected.get("final_url"),
        candidate.get("url") if isinstance(candidate, Mapping) else None,
    ):
        arxiv_id = arxiv_id_from_value(str(value or ""))
        if arxiv_id and re.search(r"v\d+$", arxiv_id):
            labels.append(arxiv_id.casefold())
    return ordered_unique_strings(labels)


def prepared_article(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """What a fetch or import run records about the article version it prepared."""
    record: dict[str, Any] = {
        "article_status": manifest.get("status"),
        "manifest_path": manifest.get("manifest_path"),
    }
    selected = manifest.get("selected")
    if isinstance(selected, Mapping):
        candidate = selected.get("candidate")
        record.update(
            version_kind=str(
                (candidate.get("version") if isinstance(candidate, Mapping) else None)
                or "unknown"
            ),
            artifact_sha256=selected.get("sha256"),
            content_sha256=selected.get("content_sha256"),
            arxiv_versions=arxiv_version_labels(manifest),
        )
    return record


def manifest_selection_rank(manifest: Mapping[str, Any]) -> tuple[int, int]:
    selected = manifest.get("selected")
    if not isinstance(selected, Mapping):
        return (99, 99)
    candidate = selected.get("candidate")
    version = candidate.get("version") if isinstance(candidate, Mapping) else None
    version_rank = version_authority(version)
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
        f"{source}{format_variant}-{'unpaywall' if use_unpaywall else 'resolver'}"
    )
    manifest_path = record_dir / f"manifest-{request_variant}.json"
    cached = cached_result(manifest_path)
    if not refresh and cached is not None:
        return cached
    if not refresh:
        prepared_again = prepare_cached_again(manifest_path, environ)
        if prepared_again is not None:
            return prepared_again
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
                required_format=(None if output_format == "auto" else output_format),
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
            if visual_fallback is not None and manifest_selection_rank(
                {"selected": visual_fallback, "status": visual_fallback["status"]}
            ) < manifest_selection_rank(
                {"selected": result, "status": result["status"]}
            ):
                selected = visual_fallback
                break
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


LOCAL_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".xhtml": "application/xhtml+xml",
}


def provenance_url(value: str | None) -> str | None:
    """An HTTPS address recorded as where a user-supplied file came from."""
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise FullTextError("--source-url must be an HTTPS address.", exit_code=2)
    if parsed.username or parsed.password:
        raise FullTextError("--source-url must not contain credentials.", exit_code=2)
    return urlunsplit(parsed)


def import_local(
    file_path: Path,
    identifier: str,
    *,
    version: str,
    source_url: str | None,
    cache_root: Path,
    timeout: float,
    max_bytes: int,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    """Prepare a user-supplied PDF or HTML copy of an article as a full-text manifest.

    The file passes the same format, extraction, and title-identity checks as a
    downloaded candidate, and its stated version becomes the version authority.
    """
    path = file_path.expanduser().resolve()
    if not path.is_file():
        raise FullTextError(f"Local article file does not exist: {path}", exit_code=2)
    if path.stat().st_size > max_bytes:
        raise FullTextError(
            f"Local article file exceeds {max_bytes // (1024 * 1024)} MiB: {path}",
            exit_code=2,
        )
    body = path.read_bytes()
    url = provenance_url(source_url)
    discovered = discover(
        identifier,
        source="auto",
        use_unpaywall=False,
        timeout=timeout,
        max_bytes=max_bytes,
        environ=environ,
        find_candidates=False,
    )
    discovered.pop("candidates")
    content_type = LOCAL_CONTENT_TYPES.get(path.suffix.casefold())
    selected_format = artifact_format(body, content_type)
    candidate = Candidate(
        source="user",
        version=version,
        format=selected_format,
        url=url or "",
        priority=0,
        link_type="user-supplied",
        access="user",
    )
    record_dir = (cache_root / cache_key(identifier)).resolve()
    selected = prepare_artifact(
        body,
        candidate,
        record_dir,
        discovered.get("title"),
        final_url=url,
        content_type=content_type,
        environ=environ,
    )
    warnings = list(discovered.pop("warnings"))
    warnings.append("user_supplied_artifact")
    if version == "preprint":
        warnings.append("selected_fulltext_is_preprint")
    warnings.extend(selected.get("warnings", []))
    manifest_path = record_dir / f"manifest-import-{selected['sha256'][:16]}.json"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "tool_version": VERSION,
        "status": selected["status"],
        "cache_hit": False,
        "cache_dir": str(record_dir),
        "manifest_path": str(manifest_path.resolve()),
        "created_at": utc_now(),
        **discovered,
        "candidates": [asdict(candidate)],
        "attempts": [
            {
                "candidate": asdict(candidate),
                "status": selected["status"],
                "final_url": url,
            }
        ],
        "selected": selected,
        "warnings": ordered_unique_strings(warnings),
    }
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
    page_count, _counter = pdf_page_count(pdf, environ)
    if page_count is not None and last > page_count:
        raise FullTextError("Requested page range exceeds the PDF page count.", 2)
    prefix = (
        destination / f"{sha256_file(pdf)[:16]}-{dpi}dpi-page-{first:04d}-{last:04d}"
    )
    existing = sorted(destination.glob(f"{prefix.name}-*.png"))
    if (
        len(existing) == last - first + 1
        and all(path.stat().st_size > 0 for path in existing)
        and not refresh
    ):
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
    if completed.returncode != 0 or len(images) != last - first + 1:
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


def prepared_text(source: str) -> tuple[Path, str, dict[str, Any] | None]:
    """Prepared article text from its own path, or from a fetch manifest.

    Returns the text path, the text, and the manifest when one was given, whose
    HTML headings then inform the outline.
    """
    path = Path(source).expanduser().resolve()
    manifest: dict[str, Any] | None = None
    text_path = path
    if path.suffix.casefold() == ".json" and path.is_file():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FullTextError(f"Unable to read manifest {path}: {exc}", 2) from exc
        selected = manifest.get("selected") if isinstance(manifest, dict) else None
        text_path = Path(str((selected or {}).get("text_path") or ""))
    if not text_path.is_file():
        raise FullTextError(f"Prepared article text does not exist: {text_path}", 2)
    return text_path, text_path.read_text(encoding="utf-8", errors="replace"), manifest


def capture_manifest(
    result: dict[str, Any],
    query: str,
    parameters: dict[str, Any],
    library_dir_value: str | None,
    environ: Mapping[str, str],
) -> bool:
    """Capture a manifest's metadata and abstract; returns whether capture failed."""
    import literature_db
    import library_catalog
    import sqlite3

    library_dir = (
        Path(library_dir_value).expanduser().resolve()
        if library_dir_value
        else literature_db.default_library_dir(environ)
    )
    connection = None
    try:
        connection, fts5 = literature_db.connect_library(library_dir)
        result["literature"] = library_catalog.capture_search(
            connection,
            fts5,
            {"response": {"numFound": 1, "docs": [result]}},
            query=query,
            parameters=parameters,
            refresh_metadata=False,
        )
    except (literature_db.LiteratureError, sqlite3.Error, OSError, ValueError) as exc:
        result["literature"] = {"status": "failed", "error": str(exc)}
        return True
    finally:
        if connection is not None:
            connection.close()
    return False


def execute(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str],
    stdout: TextIO,
) -> int:
    if args.command in {"fetch", "import"}:
        cache_root = (
            Path(args.cache_dir).expanduser().resolve()
            if args.cache_dir
            else default_cache_dir(environ)
        )
        results: list[dict[str, Any]] = []
        failed = False
        identifiers = args.identifiers if args.command == "fetch" else [args.identifier]
        for identifier in identifiers:
            try:
                if args.command == "fetch":
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
                    parameters = {
                        "command": "fulltext",
                        "source": args.source,
                        "format": args.output_format,
                    }
                else:
                    result = import_local(
                        Path(args.file),
                        identifier,
                        version=args.version,
                        source_url=args.source_url,
                        cache_root=cache_root,
                        timeout=args.timeout,
                        max_bytes=args.max_mib,
                        environ=environ,
                    )
                    parameters = {
                        "command": "import",
                        "version": args.version,
                        "format": result["selected"]["actual_format"],
                    }
                parameters.update(prepared_article(result))
                if not args.no_store and capture_manifest(
                    result, identifier, parameters, args.library_dir, environ
                ):
                    failed = True
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
        text_path, article_text, manifest = prepared_text(args.text)
        sections = article_outline(article_text, manifest, limit=args.limit)
        result = {
            "status": "outlined",
            "text_path": str(text_path),
            "words": count_words(article_text),
            "lines": article_text.count("\n") + 1,
            "sections": [
                {
                    "heading": section["heading"],
                    "line": section["line"],
                    "lines": section["lines"],
                    "words": count_words(
                        article_text[section["start"] : section["end"]]
                    ),
                }
                for section in sections
            ],
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
