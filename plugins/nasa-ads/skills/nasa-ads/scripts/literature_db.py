#!/usr/bin/env python3
"""Persistent, searchable, evidence-aware literature memory for NASA ADS."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

import ads_api
import fulltext

VERSION = "1.8.0"
DATABASE_SCHEMA_VERSION = 1
DIGEST_SCHEMA_VERSION = 1
READING_STATUSES = {"full", "targeted", "visual"}
READING_STATUS_RANK = {"targeted": 1, "visual": 2, "full": 3}
FINDING_KINDS = {
    "measurement",
    "constraint",
    "interpretation",
    "nondetection",
    "method",
    "comparison",
    "limitation",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
DATA_PRODUCT_TYPES = {"data", "code", "catalog", "table", "software", "other"}
SCOPE_COLUMNS = {
    "all": (),
    "metadata": ("title", "authors", "abstract", "identifiers", "entities"),
    "summary": (
        "topics",
        "overview",
        "facets",
        "findings",
        "methods",
        "limitations",
    ),
    "fulltext": ("full_text",),
}
SEARCH_COLUMNS = (
    "paper_id",
    "version_id",
    "digest_id",
    "title",
    "authors",
    "abstract",
    "identifiers",
    "entities",
    "topics",
    "overview",
    "facets",
    "findings",
    "methods",
    "limitations",
    "full_text",
)


class LiteratureError(Exception):
    """Concise, user-facing literature database error."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def stable_digest(value: Any) -> str:
    return fulltext.sha256_bytes(json_text(value).encode("utf-8"))


def default_library_dir(environ: Mapping[str, str]) -> Path:
    configured = environ.get("NASA_ADS_LITERATURE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = environ.get("LOCALAPPDATA", "").strip()
    if os.name == "nt" and local_app_data:
        return (Path(local_app_data) / "nasa-ads" / "literature").resolve()
    xdg_data = environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data:
        return (Path(xdg_data).expanduser() / "nasa-ads" / "literature").resolve()
    return (Path.home() / ".local" / "share" / "nasa-ads" / "literature").resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Store, reuse, and search evidence-aware literature digests and "
            "their verified full text."
        )
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--library-dir",
        help=(
            "literature library root; overrides NASA_ADS_LITERATURE_DIR and "
            "the platform default"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="initialize the database and object store")
    subparsers.add_parser("template", help="print the structured digest template")

    validate = subparsers.add_parser(
        "validate-digest", help="validate a structured digest JSON file"
    )
    validate.add_argument("digest", help="digest JSON path or - for stdin")

    ingest = subparsers.add_parser(
        "ingest", help="ingest one full-text manifest and structured digest"
    )
    ingest.add_argument("--manifest", required=True, help="fulltext.py manifest JSON")
    ingest.add_argument(
        "--digest", required=True, help="digest JSON path or - for stdin"
    )
    ingest.add_argument(
        "--identifier",
        help="select one input when --manifest contains a multi-result wrapper",
    )
    ingest.add_argument(
        "--merge",
        action="store_true",
        help="merge the incoming facets into the current digest as a new revision",
    )

    lookup = subparsers.add_parser(
        "lookup", help="check whether papers and requested topics can be reused"
    )
    lookup.add_argument("identifiers", nargs="+")
    lookup.add_argument("--topic", action="append", default=[])
    lookup.add_argument(
        "--sha256",
        help="compare against a known artifact, extracted-text, or content SHA256",
    )
    lookup.add_argument("--include-digest", action="store_true")

    show = subparsers.add_parser("show", help="show a stored paper and its evidence")
    show.add_argument("identifier")
    show.add_argument("--history", action="store_true")
    show.add_argument("--include-fulltext", action="store_true")

    search = subparsers.add_parser(
        "search", help="search metadata, layered digests, evidence, or full text"
    )
    search.add_argument("query")
    search.add_argument("--scope", choices=tuple(SCOPE_COLUMNS), default="all")
    search.add_argument("--mode", choices=("terms", "phrase", "fts"), default="terms")
    search.add_argument("--topic", action="append", default=[])
    search.add_argument("--year-from", type=int)
    search.add_argument("--year-to", type=int)
    search.add_argument("--limit", type=ads_api.positive_int, default=20)

    list_command = subparsers.add_parser(
        "list", help="list stored papers and their current digest coverage"
    )
    list_command.add_argument("--topic", action="append", default=[])
    list_command.add_argument("--year-from", type=int)
    list_command.add_argument("--year-to", type=int)
    list_command.add_argument("--limit", type=ads_api.positive_int, default=50)

    subparsers.add_parser("stats", help="show library and evidence coverage counts")
    subparsers.add_parser("reindex", help="rebuild the local search index")
    return parser


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY,
    canonical_key TEXT NOT NULL UNIQUE,
    bibcode TEXT UNIQUE,
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL DEFAULT '[]',
    abstract TEXT,
    year INTEGER,
    pub TEXT,
    doctype TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identifiers (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    UNIQUE(kind, normalized_value)
);
CREATE INDEX IF NOT EXISTS identifiers_paper_idx ON identifiers(paper_id);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL,
    text_sha256 TEXT,
    content_sha256 TEXT NOT NULL,
    source TEXT NOT NULL,
    version_kind TEXT NOT NULL,
    format TEXT NOT NULL,
    final_url TEXT,
    artifact_path TEXT NOT NULL,
    text_path TEXT,
    manifest_path TEXT NOT NULL,
    retrieved_at TEXT,
    word_count INTEGER,
    page_count INTEGER,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(paper_id, version_kind, content_sha256)
);
CREATE INDEX IF NOT EXISTS versions_paper_idx ON versions(paper_id);
CREATE INDEX IF NOT EXISTS versions_artifact_hash_idx ON versions(sha256);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL,
    text_sha256 TEXT,
    source TEXT NOT NULL,
    format TEXT NOT NULL,
    final_url TEXT,
    artifact_path TEXT NOT NULL,
    text_path TEXT,
    manifest_path TEXT NOT NULL,
    retrieved_at TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(version_id, sha256)
);
CREATE INDEX IF NOT EXISTS artifacts_version_idx ON artifacts(version_id);

CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    language TEXT NOT NULL,
    overview TEXT NOT NULL,
    significance TEXT NOT NULL,
    reading_status TEXT NOT NULL,
    digest_hash TEXT NOT NULL,
    digest_json TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE(version_id, revision)
);
CREATE UNIQUE INDEX IF NOT EXISTS digests_one_current_idx
    ON digests(version_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS facets (
    id INTEGER PRIMARY KEY,
    digest_id INTEGER NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    key TEXT NOT NULL,
    label TEXT NOT NULL,
    summary TEXT NOT NULL,
    aliases_json TEXT NOT NULL,
    keywords_json TEXT NOT NULL,
    methods_json TEXT NOT NULL,
    limitations_json TEXT NOT NULL,
    UNIQUE(digest_id, key)
);
CREATE INDEX IF NOT EXISTS facets_digest_idx ON facets(digest_id);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY,
    facet_id INTEGER NOT NULL REFERENCES facets(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    kind TEXT NOT NULL,
    statement TEXT NOT NULL,
    confidence TEXT NOT NULL,
    locator_json TEXT NOT NULL,
    values_json TEXT NOT NULL,
    keywords_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS findings_facet_idx ON findings(facet_id);

CREATE TABLE IF NOT EXISTS search_documents (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER NOT NULL,
    version_id INTEGER NOT NULL UNIQUE,
    digest_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    abstract TEXT NOT NULL,
    identifiers TEXT NOT NULL,
    entities TEXT NOT NULL,
    topics TEXT NOT NULL,
    overview TEXT NOT NULL,
    facets TEXT NOT NULL,
    findings TEXT NOT NULL,
    methods TEXT NOT NULL,
    limitations TEXT NOT NULL,
    full_text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS search_documents_paper_idx
    ON search_documents(paper_id);
"""


FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
    paper_id UNINDEXED,
    version_id UNINDEXED,
    digest_id UNINDEXED,
    title,
    authors,
    abstract,
    identifiers,
    entities,
    topics,
    overview,
    facets,
    findings,
    methods,
    limitations,
    full_text,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def initialize_schema(connection: sqlite3.Connection) -> bool:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > DATABASE_SCHEMA_VERSION:
        raise LiteratureError(
            f"Database schema {version} is newer than supported schema "
            f"{DATABASE_SCHEMA_VERSION}."
        )
    connection.executescript(SCHEMA_SQL)
    if version == 0:
        connection.execute(f"PRAGMA user_version = {DATABASE_SCHEMA_VERSION}")
    fts5 = True
    try:
        connection.executescript(FTS_SQL)
    except sqlite3.OperationalError as exc:
        if "fts5" not in str(exc).lower():
            raise
        fts5 = False
    connection.execute(
        "INSERT INTO settings(key, value) VALUES('fts5', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("1" if fts5 else "0",),
    )
    connection.commit()
    return fts5


def connect_library(library_dir: Path) -> tuple[sqlite3.Connection, bool]:
    library_dir.mkdir(parents=True, exist_ok=True)
    (library_dir / "objects").mkdir(parents=True, exist_ok=True)
    database_path = library_dir / "literature.sqlite3"
    connection = sqlite3.connect(database_path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection, initialize_schema(connection)


def load_json(path_value: str, stdin: TextIO) -> Any:
    try:
        if path_value == "-":
            return json.load(stdin)
        return json.loads(Path(path_value).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiteratureError(
            f"Unable to read JSON from {path_value}: {exc}", 2
        ) from exc


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiteratureError(f"{name} must be an object.", 2)
    return dict(value)


def require_string(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise LiteratureError(f"{name} must be a string.", 2)
    result = value.strip()
    if not result and not allow_empty:
        raise LiteratureError(f"{name} cannot be empty.", 2)
    return result


def string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise LiteratureError(f"{name} must be an array of strings.", 2)
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(require_string(item, f"{name}[{index}]"))
    return ordered_unique_casefolded_strings(result)


def ordered_unique_casefolded_strings(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        key = stripped.casefold()
        if stripped and key not in seen:
            seen.add(key)
            result.append(stripped)
    return result


def validate_optional_string_fields(
    value: dict[str, Any], name: str, fields: Iterable[str]
) -> None:
    for field in fields:
        if field in value and value[field] is not None:
            value[field] = require_string(value[field], f"{name}.{field}")


def reject_unknown_fields(
    value: Mapping[str, Any], name: str, allowed: Iterable[str]
) -> None:
    unknown = set(value) - set(allowed)
    if unknown:
        raise LiteratureError(
            f"{name} has unsupported fields: {', '.join(sorted(unknown))}.", 2
        )


def validate_named_records(
    value: Any,
    name: str,
    *,
    optional_fields: Iterable[str],
    list_fields: Iterable[str] = (),
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LiteratureError(f"{name} must be an array.", 2)
    optional_fields = tuple(optional_fields)
    list_fields = tuple(list_fields)
    allowed = {"name", *optional_fields, *list_fields}
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        item_name = f"{name}[{index}]"
        item = require_mapping(raw, item_name)
        reject_unknown_fields(item, item_name, allowed)
        item["name"] = require_string(item.get("name"), f"{item_name}.name")
        validate_optional_string_fields(item, item_name, optional_fields)
        for field in list_fields:
            item[field] = string_list(item.get(field, []), f"{item_name}.{field}")
        result.append(item)
    return result


def validate_locator(value: Any, name: str) -> dict[str, Any]:
    locator = require_mapping(value, name)
    allowed = {"section", "page", "figure", "table", "appendix", "paragraph"}
    unknown = set(locator) - allowed
    if unknown:
        raise LiteratureError(
            f"{name} has unsupported fields: {', '.join(sorted(unknown))}.", 2
        )
    for key, item in list(locator.items()):
        if item is not None:
            locator[key] = require_string(item, f"{name}.{key}")
    if not any(locator.values()):
        raise LiteratureError(
            f"{name} must identify a section, page, figure, or table.", 2
        )
    return locator


def validate_values(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LiteratureError(f"{name} must be an array.", 2)
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        item_name = f"{name}[{index}]"
        item = require_mapping(raw, item_name)
        reject_unknown_fields(
            item,
            item_name,
            {"name", "value", "unit", "uncertainty", "qualifier"},
        )
        item["name"] = require_string(item.get("name"), f"{item_name}.name")
        item_value = item.get("value")
        if isinstance(item_value, bool) or not isinstance(
            item_value, (str, int, float)
        ):
            raise LiteratureError(f"{item_name}.value must be a string or number.", 2)
        validate_optional_string_fields(
            item, item_name, ("unit", "uncertainty", "qualifier")
        )
        result.append(item)
    return result


def validate_digest(raw: Any) -> dict[str, Any]:
    digest = require_mapping(raw, "digest")
    required = {
        "schema_version",
        "language",
        "overview",
        "keywords",
        "entities",
        "datasets",
        "methods",
        "facets",
        "global_limitations",
        "data_products",
        "reading",
    }
    missing = required - set(digest)
    if missing:
        raise LiteratureError(
            f"digest is missing required fields: {', '.join(sorted(missing))}.", 2
        )
    unknown = set(digest) - required
    if unknown:
        raise LiteratureError(
            f"digest has unsupported fields: {', '.join(sorted(unknown))}.", 2
        )
    if digest["schema_version"] != DIGEST_SCHEMA_VERSION:
        raise LiteratureError(
            f"digest.schema_version must be {DIGEST_SCHEMA_VERSION}.", 2
        )
    digest["language"] = require_string(digest["language"], "digest.language")

    overview = require_mapping(digest["overview"], "digest.overview")
    reject_unknown_fields(
        overview, "digest.overview", {"summary", "significance", "questions"}
    )
    overview["summary"] = require_string(
        overview.get("summary"), "digest.overview.summary"
    )
    overview["significance"] = require_string(
        overview.get("significance"), "digest.overview.significance"
    )
    overview["questions"] = string_list(
        overview.get("questions", []), "digest.overview.questions"
    )
    digest["overview"] = overview
    digest["keywords"] = string_list(digest["keywords"], "digest.keywords")

    digest["entities"] = validate_named_records(
        digest["entities"],
        "digest.entities",
        optional_fields=("type", "description"),
        list_fields=("aliases",),
    )
    digest["datasets"] = validate_named_records(
        digest["datasets"],
        "digest.datasets",
        optional_fields=(
            "description",
            "instrument",
            "sample",
            "time_span",
            "frequency",
        ),
        list_fields=("identifiers",),
    )
    digest["methods"] = validate_named_records(
        digest["methods"],
        "digest.methods",
        optional_fields=("description", "purpose"),
        list_fields=("keywords",),
    )

    facets_raw = digest["facets"]
    if not isinstance(facets_raw, list) or not facets_raw:
        raise LiteratureError("digest.facets must contain at least one facet.", 2)
    facets: list[dict[str, Any]] = []
    facet_keys: set[str] = set()
    for facet_index, raw_facet in enumerate(facets_raw):
        facet_name = f"digest.facets[{facet_index}]"
        facet = require_mapping(raw_facet, facet_name)
        reject_unknown_fields(
            facet,
            facet_name,
            {
                "key",
                "label",
                "summary",
                "aliases",
                "keywords",
                "findings",
                "methods",
                "limitations",
            },
        )
        key = require_string(facet.get("key"), f"{facet_name}.key").lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", key):
            raise LiteratureError(
                f"{facet_name}.key must be a lowercase slug up to 64 characters.", 2
            )
        if key in facet_keys:
            raise LiteratureError(f"duplicate facet key: {key}.", 2)
        facet_keys.add(key)
        facet["key"] = key
        facet["label"] = require_string(facet.get("label"), f"{facet_name}.label")
        facet["summary"] = require_string(facet.get("summary"), f"{facet_name}.summary")
        facet["aliases"] = string_list(
            facet.get("aliases", []), f"{facet_name}.aliases"
        )
        facet["keywords"] = string_list(
            facet.get("keywords", []), f"{facet_name}.keywords"
        )
        facet["methods"] = string_list(
            facet.get("methods", []), f"{facet_name}.methods"
        )
        facet["limitations"] = string_list(
            facet.get("limitations", []), f"{facet_name}.limitations"
        )
        findings_raw = facet.get("findings")
        if not isinstance(findings_raw, list) or not findings_raw:
            raise LiteratureError(f"{facet_name}.findings cannot be empty.", 2)
        findings: list[dict[str, Any]] = []
        for finding_index, raw_finding in enumerate(findings_raw):
            finding_name = f"{facet_name}.findings[{finding_index}]"
            finding = require_mapping(raw_finding, finding_name)
            reject_unknown_fields(
                finding,
                finding_name,
                {
                    "statement",
                    "kind",
                    "confidence",
                    "locator",
                    "values",
                    "keywords",
                },
            )
            finding["statement"] = require_string(
                finding.get("statement"), f"{finding_name}.statement"
            )
            kind = require_string(finding.get("kind"), f"{finding_name}.kind")
            if kind not in FINDING_KINDS:
                raise LiteratureError(
                    f"{finding_name}.kind must be one of "
                    f"{', '.join(sorted(FINDING_KINDS))}.",
                    2,
                )
            finding["kind"] = kind
            confidence = require_string(
                finding.get("confidence"), f"{finding_name}.confidence"
            )
            if confidence not in CONFIDENCE_LEVELS:
                raise LiteratureError(
                    f"{finding_name}.confidence must be high, medium, or low.", 2
                )
            finding["confidence"] = confidence
            finding["locator"] = validate_locator(
                finding.get("locator"), f"{finding_name}.locator"
            )
            finding["values"] = validate_values(
                finding.get("values", []), f"{finding_name}.values"
            )
            finding["keywords"] = string_list(
                finding.get("keywords", []), f"{finding_name}.keywords"
            )
            findings.append(finding)
        facet["findings"] = findings
        facets.append(facet)
    digest["facets"] = facets
    digest["global_limitations"] = string_list(
        digest["global_limitations"], "digest.global_limitations"
    )

    products = validate_named_records(
        digest["data_products"],
        "digest.data_products",
        optional_fields=("type", "url", "availability", "locator"),
    )
    for index, product in enumerate(products):
        product_type = product.get("type", "other")
        if product_type not in DATA_PRODUCT_TYPES:
            raise LiteratureError(
                f"digest.data_products[{index}].type must be one of "
                f"{', '.join(sorted(DATA_PRODUCT_TYPES))}.",
                2,
            )
        product["type"] = product_type
    digest["data_products"] = products

    reading = require_mapping(digest["reading"], "digest.reading")
    reject_unknown_fields(
        reading,
        "digest.reading",
        {
            "status",
            "sections",
            "page_ranges",
            "visual_page_ranges",
            "unread_sections",
            "notes",
        },
    )
    status = require_string(reading.get("status"), "digest.reading.status")
    if status not in READING_STATUSES:
        raise LiteratureError(
            "digest.reading.status must be full, targeted, or visual.", 2
        )
    reading["status"] = status
    for field in (
        "sections",
        "page_ranges",
        "visual_page_ranges",
        "unread_sections",
    ):
        reading[field] = string_list(reading.get(field, []), f"digest.reading.{field}")
    reading["notes"] = require_string(
        reading.get("notes", ""), "digest.reading.notes", allow_empty=True
    )
    if status in {"full", "targeted"} and not reading["sections"]:
        raise LiteratureError(
            "digest.reading.sections cannot be empty for full or targeted reading.", 2
        )
    if status == "visual" and not reading["visual_page_ranges"]:
        raise LiteratureError(
            "digest.reading.visual_page_ranges cannot be empty for visual reading.", 2
        )
    digest["reading"] = reading
    return digest


def digest_template() -> dict[str, Any]:
    return {
        "schema_version": DIGEST_SCHEMA_VERSION,
        "language": "zh-CN",
        "overview": {
            "summary": "",
            "significance": "",
            "questions": [],
        },
        "keywords": [],
        "entities": [{"name": "", "type": "", "description": "", "aliases": []}],
        "datasets": [
            {
                "name": "",
                "description": "",
                "instrument": "",
                "sample": "",
                "time_span": "",
                "frequency": "",
                "identifiers": [],
            }
        ],
        "methods": [{"name": "", "description": "", "purpose": "", "keywords": []}],
        "facets": [
            {
                "key": "topic-slug",
                "label": "",
                "aliases": [],
                "summary": "",
                "keywords": [],
                "findings": [
                    {
                        "statement": "",
                        "kind": "measurement",
                        "confidence": "high",
                        "locator": {"section": ""},
                        "values": [],
                        "keywords": [],
                    }
                ],
                "methods": [],
                "limitations": [],
            }
        ],
        "global_limitations": [],
        "data_products": [],
        "reading": {
            "status": "full",
            "sections": [],
            "page_ranges": [],
            "visual_page_ranges": [],
            "unread_sections": [],
            "notes": "",
        },
    }


def merge_record_lists(
    current: list[dict[str, Any]], incoming: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    result = [dict(item) for item in current]
    positions = {
        str(item.get(key, "")).strip().casefold(): index
        for index, item in enumerate(result)
        if str(item.get(key, "")).strip()
    }
    for item in incoming:
        record_key = str(item.get(key, "")).strip().casefold()
        if record_key and record_key in positions:
            result[positions[record_key]] = dict(item)
        else:
            positions[record_key] = len(result)
            result.append(dict(item))
    return result


def merge_string_lists(current: list[str], incoming: list[str]) -> list[str]:
    return ordered_unique_casefolded_strings([*current, *incoming])


def merge_findings(
    current: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = [dict(item) for item in current]
    positions = {
        (
            str(item.get("statement", "")).strip().casefold(),
            json_text(item.get("locator", {})),
        ): index
        for index, item in enumerate(result)
    }
    for item in incoming:
        key = (
            str(item.get("statement", "")).strip().casefold(),
            json_text(item.get("locator", {})),
        )
        if key in positions:
            result[positions[key]] = dict(item)
        else:
            positions[key] = len(result)
            result.append(dict(item))
    return result


def merge_facets(
    current: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = [json.loads(json.dumps(item)) for item in current]
    positions = {item["key"]: index for index, item in enumerate(result)}
    for new_facet in incoming:
        key = new_facet["key"]
        if key not in positions:
            positions[key] = len(result)
            result.append(json.loads(json.dumps(new_facet)))
            continue
        old = result[positions[key]]
        for field in ("label", "summary"):
            if new_facet.get(field):
                old[field] = new_facet[field]
        for field in ("aliases", "keywords", "methods", "limitations"):
            old[field] = merge_string_lists(
                old.get(field, []), new_facet.get(field, [])
            )
        old["findings"] = merge_findings(
            old.get("findings", []), new_facet.get("findings", [])
        )
    return result


def merge_digests(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(current))
    merged["language"] = incoming.get("language") or merged["language"]
    for field in ("summary", "significance"):
        if incoming["overview"].get(field):
            merged["overview"][field] = incoming["overview"][field]
    merged["overview"]["questions"] = merge_string_lists(
        merged["overview"].get("questions", []),
        incoming["overview"].get("questions", []),
    )
    merged["keywords"] = merge_string_lists(
        merged.get("keywords", []), incoming.get("keywords", [])
    )
    for field in ("entities", "datasets", "methods", "data_products"):
        merged[field] = merge_record_lists(
            merged.get(field, []), incoming.get(field, []), "name"
        )
    merged["facets"] = merge_facets(
        merged.get("facets", []), incoming.get("facets", [])
    )
    merged["global_limitations"] = merge_string_lists(
        merged.get("global_limitations", []),
        incoming.get("global_limitations", []),
    )
    current_reading = merged["reading"]
    incoming_reading = incoming["reading"]
    if (
        READING_STATUS_RANK[incoming_reading["status"]]
        > READING_STATUS_RANK[current_reading["status"]]
    ):
        current_reading["status"] = incoming_reading["status"]
    for field in ("sections", "page_ranges", "visual_page_ranges"):
        current_reading[field] = merge_string_lists(
            current_reading.get(field, []), incoming_reading.get(field, [])
        )
    current_reading["unread_sections"] = incoming_reading.get(
        "unread_sections", current_reading.get("unread_sections", [])
    )
    incoming_notes = incoming_reading.get("notes", "").strip()
    if incoming_notes and incoming_notes not in current_reading.get("notes", ""):
        current_notes = current_reading.get("notes", "").strip()
        current_reading["notes"] = "\n".join(
            part for part in (current_notes, incoming_notes) if part
        )
    return validate_digest(merged)


def normalize_identifier(kind: str, value: str) -> str:
    if kind == "doi":
        normalized = fulltext.doi_from_value(value)
        if not normalized:
            raise LiteratureError(f"Invalid DOI: {value}", 2)
        return normalized.casefold()
    if kind == "arxiv":
        normalized = fulltext.arxiv_id_from_value(value)
        if not normalized:
            raise LiteratureError(f"Invalid arXiv identifier: {value}", 2)
        return re.sub(r"v\d+$", "", normalized, flags=re.IGNORECASE).casefold()
    if kind == "bibcode":
        stripped = value.strip()
        if not stripped:
            raise LiteratureError("Empty bibcode.", 2)
        return stripped.casefold()
    raise LiteratureError(f"Unsupported identifier kind: {kind}", 2)


def classify_alias(value: str) -> tuple[str, str, str]:
    kind, normalized = fulltext.classify_identifier(value)
    display = normalized
    return kind, display, normalize_identifier(kind, normalized)


def aliases_from_manifest(manifest: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    aliases: list[tuple[str, str, str]] = []

    def append(kind: str, value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        normalized = normalize_identifier(kind, value)
        key = (kind, normalized)
        if not any((item[0], item[2]) == key for item in aliases):
            display = value.strip()
            if kind == "arxiv":
                display = re.sub(r"^arxiv:\s*", "", display, flags=re.IGNORECASE)
            aliases.append((kind, display, normalized))

    append("bibcode", manifest.get("bibcode"))
    for doi in manifest.get("doi", []) or []:
        append("doi", doi)
    for arxiv_id in manifest.get("arxiv_ids", []) or []:
        append("arxiv", arxiv_id)
    input_type = manifest.get("input_type")
    if input_type in {"bibcode", "doi", "arxiv"}:
        append(str(input_type), manifest.get("normalized_identifier"))
    if not aliases:
        raise LiteratureError(
            "Manifest contains no usable bibcode, DOI, or arXiv ID.", 2
        )
    return aliases


def canonical_key(aliases: Sequence[tuple[str, str, str]]) -> str:
    for preferred in ("bibcode", "doi", "arxiv"):
        matches = [item for item in aliases if item[0] == preferred]
        if preferred == "doi":
            non_arxiv = [
                item for item in matches if not item[2].startswith("10.48550/")
            ]
            matches = non_arxiv or matches
        if matches:
            return f"{preferred}:{matches[0][2]}"
    raise LiteratureError("Unable to build a canonical paper key.", 2)


def select_manifest_result(payload: Any, identifier: str | None) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        results = [item for item in payload["results"] if isinstance(item, dict)]
        if identifier:
            matches = [
                item
                for item in results
                if identifier
                in {
                    item.get("input"),
                    item.get("normalized_identifier"),
                    item.get("bibcode"),
                }
            ]
            if len(matches) != 1:
                raise LiteratureError(
                    f"Unable to select exactly one manifest result for {identifier}.", 2
                )
            return dict(matches[0])
        if len(results) != 1:
            raise LiteratureError("A multi-result manifest requires --identifier.", 2)
        return dict(results[0])
    return require_mapping(payload, "manifest")


def validate_ingest_manifest(manifest: dict[str, Any], digest: dict[str, Any]) -> None:
    status = manifest.get("status")
    if status not in {"fulltext", "needs_visual_reading"}:
        raise LiteratureError(
            "Only a fulltext or needs_visual_reading manifest can enter the "
            "literature database.",
            2,
        )
    selected = require_mapping(manifest.get("selected"), "manifest.selected")
    artifact = Path(require_string(selected.get("artifact_path"), "artifact_path"))
    if not artifact.is_file():
        raise LiteratureError(f"Selected artifact does not exist: {artifact}", 2)
    expected_hash = require_string(selected.get("sha256"), "selected.sha256")
    actual_hash = fulltext.sha256_file(artifact)
    if actual_hash != expected_hash:
        raise LiteratureError(
            "Selected artifact hash does not match its full-text manifest.", 2
        )
    if status == "fulltext":
        text_path_value = selected.get("text_path")
        if not text_path_value or not Path(str(text_path_value)).is_file():
            raise LiteratureError(
                "A fulltext manifest requires an existing text_path.", 2
            )
        text_path = Path(str(text_path_value))
        actual_text_hash = fulltext.sha256_file(text_path)
        expected_text_hash = selected.get("text_sha256")
        if expected_text_hash and actual_text_hash != expected_text_hash:
            raise LiteratureError(
                "Selected text hash does not match its full-text manifest.", 2
            )
        actual_content_hash = fulltext.canonical_text_sha256(
            text_path.read_text(encoding="utf-8", errors="replace")
        )
        expected_content_hash = selected.get("content_sha256")
        if expected_content_hash and actual_content_hash != expected_content_hash:
            raise LiteratureError(
                "Selected content hash does not match its full-text manifest.", 2
            )
        if digest["reading"]["status"] == "visual":
            raise LiteratureError(
                "A text-bearing fulltext manifest cannot use visual-only "
                "reading status.",
                2,
            )
    if status == "needs_visual_reading" and digest["reading"]["status"] != "visual":
        raise LiteratureError(
            "A needs_visual_reading manifest requires visual reading coverage.", 2
        )
    if status == "needs_visual_reading":
        expected_content_hash = selected.get("content_sha256")
        if expected_content_hash and expected_content_hash != actual_hash:
            raise LiteratureError(
                "A visual-reading manifest must use the raw artifact hash as "
                "its content identity.",
                2,
            )


def atomic_copy(
    source: Path, destination: Path, expected_hash: str | None = None
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if expected_hash is None or fulltext.sha256_file(destination) == expected_hash:
            return
        raise LiteratureError(f"Stored object has an unexpected hash: {destination}")
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        shutil.copyfile(source, temporary)
        if expected_hash and fulltext.sha256_file(temporary) != expected_hash:
            raise LiteratureError(f"Copied object failed hash validation: {source}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def store_objects(library_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    selected = require_mapping(manifest["selected"], "manifest.selected")
    artifact_hash = require_string(selected["sha256"], "selected.sha256")
    object_dir = library_dir / "objects" / artifact_hash[:2] / artifact_hash
    artifact_source = Path(str(selected["artifact_path"])).expanduser().resolve()
    output_format = str(selected.get("actual_format") or "artifact").lower()
    if output_format not in {"pdf", "html"}:
        output_format = "artifact"
    artifact_destination = object_dir / f"article.{output_format}"
    atomic_copy(artifact_source, artifact_destination, artifact_hash)

    text_destination: Path | None = None
    text_hash: str | None = None
    content_hash = artifact_hash
    full_text_value = ""
    if selected.get("text_path"):
        text_source = Path(str(selected["text_path"])).expanduser().resolve()
        if not text_source.is_file():
            raise LiteratureError(f"Selected text does not exist: {text_source}", 2)
        text_hash = fulltext.sha256_file(text_source)
        text_destination = object_dir / "article.txt"
        atomic_copy(text_source, text_destination, text_hash)
        full_text_value = text_destination.read_text(encoding="utf-8", errors="replace")
        if manifest.get("status") == "fulltext":
            content_hash = fulltext.canonical_text_sha256(full_text_value)

    stored_manifest = dict(manifest)
    stored_manifest["database_object"] = {
        "artifact_path": str(artifact_destination.resolve()),
        "text_path": str(text_destination.resolve()) if text_destination else None,
        "artifact_sha256": artifact_hash,
        "text_sha256": text_hash,
        "content_sha256": content_hash,
        "stored_at": fulltext.utc_now(),
    }
    manifest_destination = object_dir / "manifest.json"
    fulltext.atomic_write_text(manifest_destination, pretty_json(stored_manifest))
    return {
        "artifact_path": str(artifact_destination.resolve()),
        "text_path": str(text_destination.resolve()) if text_destination else None,
        "manifest_path": str(manifest_destination.resolve()),
        "sha256": artifact_hash,
        "text_sha256": text_hash,
        "content_sha256": content_hash,
        "full_text": full_text_value,
    }


def paper_ids_for_aliases(
    connection: sqlite3.Connection, aliases: Sequence[tuple[str, str, str]]
) -> set[int]:
    paper_ids: set[int] = set()
    for kind, _display, normalized in aliases:
        row = connection.execute(
            "SELECT paper_id FROM identifiers WHERE kind = ? AND normalized_value = ?",
            (kind, normalized),
        ).fetchone()
        if row:
            paper_ids.add(int(row["paper_id"]))
    return paper_ids


def upsert_paper(
    connection: sqlite3.Connection,
    manifest: dict[str, Any],
    aliases: Sequence[tuple[str, str, str]],
) -> int:
    matches = paper_ids_for_aliases(connection, aliases)
    if len(matches) > 1:
        raise LiteratureError(
            "Identifiers in the manifest already belong to different papers."
        )
    now = fulltext.utc_now()
    title = require_string(manifest.get("title"), "manifest.title")
    authors = manifest.get("author") if isinstance(manifest.get("author"), list) else []
    authors = [str(author) for author in authors]
    abstract = str(manifest.get("abstract") or "")
    bibcode = str(manifest.get("bibcode") or "").strip() or None
    try:
        year = int(manifest["year"]) if manifest.get("year") is not None else None
    except (TypeError, ValueError):
        year = None
    metadata = {
        "property": manifest.get("property") or [],
        "doi": manifest.get("doi") or [],
        "arxiv_ids": manifest.get("arxiv_ids") or [],
        "citation_count": manifest.get("citation_count"),
        "read_count": manifest.get("read_count"),
    }
    if matches:
        paper_id = matches.pop()
        connection.execute(
            """
            UPDATE papers
            SET bibcode = COALESCE(?, bibcode), title = ?, authors_json = ?,
                abstract = ?, year = COALESCE(?, year), pub = ?, doctype = ?,
                metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                bibcode,
                title,
                json_text(authors),
                abstract,
                year,
                manifest.get("pub"),
                manifest.get("doctype"),
                json_text(metadata),
                now,
                paper_id,
            ),
        )
    else:
        cursor = connection.execute(
            """
            INSERT INTO papers(
                canonical_key, bibcode, title, authors_json, abstract, year,
                pub, doctype, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_key(aliases),
                bibcode,
                title,
                json_text(authors),
                abstract,
                year,
                manifest.get("pub"),
                manifest.get("doctype"),
                json_text(metadata),
                now,
                now,
            ),
        )
        paper_id = int(cursor.lastrowid)
    try:
        connection.executemany(
            """
            INSERT INTO identifiers(paper_id, kind, value, normalized_value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(kind, normalized_value) DO NOTHING
            """,
            [
                (paper_id, kind, display, normalized)
                for kind, display, normalized in aliases
            ],
        )
    except sqlite3.IntegrityError as exc:
        raise LiteratureError("One or more paper identifiers conflict.") from exc
    return paper_id


def upsert_version(
    connection: sqlite3.Connection,
    paper_id: int,
    manifest: dict[str, Any],
    stored: dict[str, Any],
) -> tuple[int, bool]:
    selected = manifest["selected"]
    candidate = selected.get("candidate") or {}
    version_kind = candidate.get("version") or "unknown"
    row = connection.execute(
        "SELECT id FROM versions "
        "WHERE paper_id = ? AND version_kind = ? AND content_sha256 = ?",
        (paper_id, version_kind, stored["content_sha256"]),
    ).fetchone()
    statistics = selected.get("statistics") or {}
    if row:
        version_id = int(row["id"])
        connection.execute(
            """
            UPDATE versions
            SET sha256 = ?, text_sha256 = ?, source = ?, format = ?,
                final_url = ?, artifact_path = ?, text_path = ?, manifest_path = ?,
                retrieved_at = ?, word_count = ?, page_count = ?, status = ?
            WHERE id = ?
            """,
            (
                stored["sha256"],
                stored["text_sha256"],
                candidate.get("source") or "unknown",
                selected.get("actual_format") or candidate.get("format") or "unknown",
                selected.get("final_url"),
                stored["artifact_path"],
                stored["text_path"],
                stored["manifest_path"],
                selected.get("retrieved_at") or manifest.get("created_at"),
                statistics.get("words"),
                statistics.get("pages"),
                manifest.get("status"),
                version_id,
            ),
        )
        version_created = False
    else:
        cursor = connection.execute(
            """
            INSERT INTO versions(
                paper_id, sha256, text_sha256, content_sha256, source,
                version_kind, format, final_url, artifact_path, text_path,
                manifest_path, retrieved_at, word_count, page_count, status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                stored["sha256"],
                stored["text_sha256"],
                stored["content_sha256"],
                candidate.get("source") or "unknown",
                version_kind,
                selected.get("actual_format") or candidate.get("format") or "unknown",
                selected.get("final_url"),
                stored["artifact_path"],
                stored["text_path"],
                stored["manifest_path"],
                selected.get("retrieved_at") or manifest.get("created_at"),
                statistics.get("words"),
                statistics.get("pages"),
                manifest.get("status"),
                fulltext.utc_now(),
            ),
        )
        version_id = int(cursor.lastrowid)
        version_created = True
    connection.execute(
        """
        INSERT INTO artifacts(
            version_id, sha256, text_sha256, source, format, final_url,
            artifact_path, text_path, manifest_path, retrieved_at, status,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(version_id, sha256) DO UPDATE SET
            text_sha256 = excluded.text_sha256,
            source = excluded.source,
            format = excluded.format,
            final_url = excluded.final_url,
            artifact_path = excluded.artifact_path,
            text_path = excluded.text_path,
            manifest_path = excluded.manifest_path,
            retrieved_at = excluded.retrieved_at,
            status = excluded.status
        """,
        (
            version_id,
            stored["sha256"],
            stored["text_sha256"],
            candidate.get("source") or "unknown",
            selected.get("actual_format") or candidate.get("format") or "unknown",
            selected.get("final_url"),
            stored["artifact_path"],
            stored["text_path"],
            stored["manifest_path"],
            selected.get("retrieved_at") or manifest.get("created_at"),
            manifest.get("status"),
            fulltext.utc_now(),
        ),
    )
    return version_id, version_created


def current_digest_row(
    connection: sqlite3.Connection, version_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM digests WHERE version_id = ? AND is_current = 1",
        (version_id,),
    ).fetchone()


def insert_digest(
    connection: sqlite3.Connection,
    version_id: int,
    digest: dict[str, Any],
) -> tuple[int, int, bool]:
    digest_hash = stable_digest(digest)
    current = current_digest_row(connection, version_id)
    if current and current["digest_hash"] == digest_hash:
        return int(current["id"]), int(current["revision"]), False
    revision_row = connection.execute(
        "SELECT COALESCE(MAX(revision), 0) AS revision "
        "FROM digests WHERE version_id = ?",
        (version_id,),
    ).fetchone()
    revision = int(revision_row["revision"]) + 1
    connection.execute(
        "UPDATE digests SET is_current = 0 WHERE version_id = ? AND is_current = 1",
        (version_id,),
    )
    cursor = connection.execute(
        """
        INSERT INTO digests(
            version_id, revision, schema_version, language, overview,
            significance, reading_status, digest_hash, digest_json,
            is_current, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            version_id,
            revision,
            digest["schema_version"],
            digest["language"],
            digest["overview"]["summary"],
            digest["overview"]["significance"],
            digest["reading"]["status"],
            digest_hash,
            json_text(digest),
            fulltext.utc_now(),
        ),
    )
    digest_id = int(cursor.lastrowid)
    for facet_index, facet in enumerate(digest["facets"]):
        facet_cursor = connection.execute(
            """
            INSERT INTO facets(
                digest_id, ordinal, key, label, summary, aliases_json,
                keywords_json, methods_json, limitations_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                digest_id,
                facet_index,
                facet["key"],
                facet["label"],
                facet["summary"],
                json_text(facet["aliases"]),
                json_text(facet["keywords"]),
                json_text(facet["methods"]),
                json_text(facet["limitations"]),
            ),
        )
        facet_id = int(facet_cursor.lastrowid)
        for finding_index, finding in enumerate(facet["findings"]):
            connection.execute(
                """
                INSERT INTO findings(
                    facet_id, ordinal, kind, statement, confidence,
                    locator_json, values_json, keywords_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    facet_id,
                    finding_index,
                    finding["kind"],
                    finding["statement"],
                    finding["confidence"],
                    json_text(finding["locator"]),
                    json_text(finding["values"]),
                    json_text(finding["keywords"]),
                ),
            )
    return digest_id, revision, True


def join_record_text(records: Iterable[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for record in records:
        for value in record.values():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(str(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        parts.append(join_record_text([item]))
                    else:
                        parts.append(str(item))
            elif isinstance(value, dict):
                parts.append(join_record_text([value]))
    return "\n".join(parts)


def build_search_document(
    connection: sqlite3.Connection,
    paper_id: int,
    version_id: int,
    digest_id: int,
    digest: dict[str, Any],
    full_text_value: str,
) -> dict[str, str]:
    paper = connection.execute(
        "SELECT * FROM papers WHERE id = ?", (paper_id,)
    ).fetchone()
    identifiers = connection.execute(
        "SELECT kind, value FROM identifiers WHERE paper_id = ? ORDER BY kind, value",
        (paper_id,),
    ).fetchall()
    topics: list[str] = list(digest["keywords"])
    facet_parts: list[str] = []
    finding_parts: list[str] = []
    limitations: list[str] = list(digest["global_limitations"])
    for facet in digest["facets"]:
        topics.extend(
            [
                facet["key"],
                facet["label"],
                *facet["aliases"],
                *facet["keywords"],
            ]
        )
        facet_parts.extend(
            [
                facet["label"],
                facet["summary"],
                *facet["methods"],
            ]
        )
        limitations.extend(facet["limitations"])
        for finding in facet["findings"]:
            finding_parts.append(finding["statement"])
            finding_parts.append(join_record_text(finding["values"]))
            finding_parts.extend(finding["keywords"])
    overview = digest["overview"]
    return {
        "paper_id": str(paper_id),
        "version_id": str(version_id),
        "digest_id": str(digest_id),
        "title": str(paper["title"]),
        "authors": "\n".join(json.loads(paper["authors_json"])),
        "abstract": str(paper["abstract"] or ""),
        "identifiers": "\n".join(
            f"{row['kind']}:{row['value']}" for row in identifiers
        ),
        "entities": join_record_text(digest["entities"]),
        "topics": "\n".join(ordered_unique_casefolded_strings(topics)),
        "overview": "\n".join(
            [overview["summary"], overview["significance"], *overview["questions"]]
        ),
        "facets": "\n".join(facet_parts),
        "findings": "\n".join(finding_parts),
        "methods": "\n".join(
            [join_record_text(digest["methods"]), join_record_text(digest["datasets"])]
        ),
        "limitations": "\n".join(ordered_unique_casefolded_strings(limitations)),
        "full_text": full_text_value,
    }


def replace_search_document(
    connection: sqlite3.Connection,
    document: Mapping[str, str],
    fts5: bool,
) -> None:
    version_id = document["version_id"]
    connection.execute(
        "DELETE FROM search_documents WHERE version_id = ?", (version_id,)
    )
    placeholders = ", ".join("?" for _ in SEARCH_COLUMNS)
    columns = ", ".join(SEARCH_COLUMNS)
    values = [document[column] for column in SEARCH_COLUMNS]
    connection.execute(
        f"INSERT INTO search_documents({columns}, updated_at) "
        f"VALUES ({placeholders}, ?)",
        (*values, fulltext.utc_now()),
    )
    if fts5:
        connection.execute("DELETE FROM search_fts WHERE version_id = ?", (version_id,))
        connection.execute(
            f"INSERT INTO search_fts({columns}) VALUES ({placeholders})", values
        )


def ingest_record(
    connection: sqlite3.Connection,
    fts5: bool,
    library_dir: Path,
    manifest: dict[str, Any],
    digest: dict[str, Any],
    *,
    merge: bool,
) -> dict[str, Any]:
    validate_ingest_manifest(manifest, digest)
    stored = store_objects(library_dir, manifest)
    aliases = aliases_from_manifest(manifest)
    try:
        connection.execute("BEGIN IMMEDIATE")
        paper_id = upsert_paper(connection, manifest, aliases)
        version_id, version_created = upsert_version(
            connection, paper_id, manifest, stored
        )
        current = current_digest_row(connection, version_id)
        if current:
            current_digest = json.loads(current["digest_json"])
            if merge:
                digest = merge_digests(current_digest, digest)
            elif stable_digest(current_digest) != stable_digest(digest):
                raise LiteratureError(
                    "This article version already has a different digest. "
                    "Use --merge to preserve its existing facets and history.",
                    2,
                )
        digest_id, revision, digest_created = insert_digest(
            connection, version_id, digest
        )
        document = build_search_document(
            connection,
            paper_id,
            version_id,
            digest_id,
            digest,
            stored["full_text"],
        )
        replace_search_document(connection, document, fts5)
        stored_paper = connection.execute(
            "SELECT canonical_key FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "status": "ingested" if digest_created else "unchanged",
        "paper_id": paper_id,
        "version_id": version_id,
        "digest_id": digest_id,
        "revision": revision,
        "version_created": version_created,
        "digest_created": digest_created,
        "canonical_key": stored_paper["canonical_key"],
        "bibcode": manifest.get("bibcode"),
        "title": manifest.get("title"),
        "artifact_sha256": stored["sha256"],
        "content_sha256": stored["content_sha256"],
        "object_paths": {
            "artifact": stored["artifact_path"],
            "text": stored["text_path"],
            "manifest": stored["manifest_path"],
        },
        "reading_status": digest["reading"]["status"],
        "facets": [facet["key"] for facet in digest["facets"]],
    }


def find_paper_by_identifier(
    connection: sqlite3.Connection, identifier: str
) -> sqlite3.Row | None:
    kind, _display, normalized = classify_alias(identifier)
    return connection.execute(
        """
        SELECT p.*
        FROM papers p
        JOIN identifiers i ON i.paper_id = p.id
        WHERE i.kind = ? AND i.normalized_value = ?
        """,
        (kind, normalized),
    ).fetchone()


def preferred_version(
    connection: sqlite3.Connection,
    paper_id: int,
    artifact_hash: str | None = None,
) -> sqlite3.Row | None:
    parameters: list[Any] = [paper_id]
    hash_clause = ""
    if artifact_hash:
        hash_clause = "AND (v.sha256 = ? OR v.text_sha256 = ? OR v.content_sha256 = ?)"
        parameters.extend([artifact_hash, artifact_hash, artifact_hash])
    return connection.execute(
        f"""
        SELECT v.*, d.id AS digest_id, d.digest_json, d.reading_status,
               d.revision, d.created_at AS digest_created_at
        FROM versions v
        LEFT JOIN digests d ON d.version_id = v.id AND d.is_current = 1
        WHERE v.paper_id = ? {hash_clause}
        ORDER BY
            CASE v.version_kind
                WHEN 'published' THEN 0
                WHEN 'accepted' THEN 1
                WHEN 'preprint' THEN 2
                WHEN 'scan' THEN 3
                ELSE 4
            END,
            v.retrieved_at DESC,
            v.id DESC
        LIMIT 1
        """,
        parameters,
    ).fetchone()


def topic_match(facet: Mapping[str, Any], topic: str) -> bool:
    needle = topic.strip().casefold()
    if not needle:
        return False
    haystack = "\n".join(
        [
            str(facet.get("key", "")),
            str(facet.get("label", "")),
            *[str(value) for value in facet.get("aliases", [])],
            *[str(value) for value in facet.get("keywords", [])],
        ]
    ).casefold()
    return needle in haystack or all(token in haystack for token in needle.split())


def reuse_assessment(
    version: sqlite3.Row | None,
    topics: Sequence[str],
    artifact_hash: str | None,
) -> dict[str, Any]:
    if version is None:
        return {
            "reuse_status": "version_changed" if artifact_hash else "needs_reading",
            "matched_topics": [],
            "missing_topics": list(topics),
        }
    if version["digest_id"] is None:
        return {
            "reuse_status": "needs_reading",
            "matched_topics": [],
            "missing_topics": list(topics),
        }
    digest = json.loads(version["digest_json"])
    matched: list[str] = []
    missing: list[str] = []
    for topic in topics:
        if any(topic_match(facet, topic) for facet in digest["facets"]):
            matched.append(topic)
        else:
            missing.append(topic)
    reading_status = version["reading_status"]
    if missing or (reading_status == "targeted" and not topics):
        status = "targeted_reading"
    elif reading_status == "targeted":
        status = "reusable_for_topics"
    else:
        status = "reusable"
    return {
        "reuse_status": status,
        "matched_topics": matched,
        "missing_topics": missing,
        "reading_status": reading_status,
        "digest_revision": version["revision"],
    }


def paper_aliases(
    connection: sqlite3.Connection, paper_id: int
) -> list[dict[str, str]]:
    rows = connection.execute(
        "SELECT kind, value FROM identifiers WHERE paper_id = ? ORDER BY kind, value",
        (paper_id,),
    ).fetchall()
    return [{"kind": row["kind"], "value": row["value"]} for row in rows]


def lookup_one(
    connection: sqlite3.Connection,
    identifier: str,
    *,
    topics: Sequence[str],
    artifact_hash: str | None,
    include_digest: bool,
) -> dict[str, Any]:
    paper = find_paper_by_identifier(connection, identifier)
    if paper is None:
        return {
            "input": identifier,
            "found": False,
            "reuse_status": "not_found",
            "matched_topics": [],
            "missing_topics": list(topics),
        }
    version = preferred_version(connection, int(paper["id"]), artifact_hash)
    assessment = reuse_assessment(version, topics, artifact_hash)
    result: dict[str, Any] = {
        "input": identifier,
        "found": True,
        "paper_id": paper["id"],
        "canonical_key": paper["canonical_key"],
        "bibcode": paper["bibcode"],
        "title": paper["title"],
        "year": paper["year"],
        "identifiers": paper_aliases(connection, int(paper["id"])),
        **assessment,
    }
    if version:
        result["version"] = {
            "id": version["id"],
            "artifact_sha256": version["sha256"],
            "content_sha256": version["content_sha256"],
            "source": version["source"],
            "version_kind": version["version_kind"],
            "format": version["format"],
            "artifact_path": version["artifact_path"],
            "text_path": version["text_path"],
            "retrieved_at": version["retrieved_at"],
        }
        if version["digest_id"]:
            digest = json.loads(version["digest_json"])
            result["facet_labels"] = [
                {"key": facet["key"], "label": facet["label"]}
                for facet in digest["facets"]
            ]
            result["overview"] = digest["overview"]
            if include_digest:
                result["digest"] = digest
    return result


def digest_details(digest_row: sqlite3.Row) -> dict[str, Any]:
    digest = json.loads(digest_row["digest_json"])
    return {
        "id": digest_row["id"],
        "revision": digest_row["revision"],
        "schema_version": digest_row["schema_version"],
        "language": digest_row["language"],
        "reading_status": digest_row["reading_status"],
        "is_current": bool(digest_row["is_current"]),
        "created_at": digest_row["created_at"],
        "digest": digest,
    }


def show_paper(
    connection: sqlite3.Connection,
    identifier: str,
    *,
    history: bool,
    include_fulltext: bool,
) -> dict[str, Any]:
    paper = find_paper_by_identifier(connection, identifier)
    if paper is None:
        raise LiteratureError(
            f"Paper is not in the literature database: {identifier}", 2
        )
    versions = connection.execute(
        "SELECT * FROM versions WHERE paper_id = ? ORDER BY id DESC",
        (paper["id"],),
    ).fetchall()
    version_values: list[dict[str, Any]] = []
    for version in versions:
        digest_sql = "SELECT * FROM digests WHERE version_id = ?"
        if not history:
            digest_sql += " AND is_current = 1"
        digest_sql += " ORDER BY revision DESC"
        digest_rows = connection.execute(digest_sql, (version["id"],)).fetchall()
        version_value: dict[str, Any] = {
            "id": version["id"],
            "artifact_sha256": version["sha256"],
            "text_sha256": version["text_sha256"],
            "content_sha256": version["content_sha256"],
            "source": version["source"],
            "version_kind": version["version_kind"],
            "format": version["format"],
            "final_url": version["final_url"],
            "artifact_path": version["artifact_path"],
            "text_path": version["text_path"],
            "manifest_path": version["manifest_path"],
            "retrieved_at": version["retrieved_at"],
            "word_count": version["word_count"],
            "page_count": version["page_count"],
            "status": version["status"],
            "digests": [digest_details(row) for row in digest_rows],
            "artifacts": [
                dict(artifact)
                for artifact in connection.execute(
                    "SELECT id, sha256 AS artifact_sha256, text_sha256, source, "
                    "format, final_url, artifact_path, text_path, manifest_path, "
                    "retrieved_at, status, created_at FROM artifacts "
                    "WHERE version_id = ? ORDER BY id DESC",
                    (version["id"],),
                ).fetchall()
            ],
        }
        if include_fulltext and version["text_path"]:
            text_path = Path(version["text_path"])
            version_value["full_text"] = text_path.read_text(
                encoding="utf-8", errors="replace"
            )
        version_values.append(version_value)
    return {
        "paper": {
            "id": paper["id"],
            "canonical_key": paper["canonical_key"],
            "bibcode": paper["bibcode"],
            "title": paper["title"],
            "authors": json.loads(paper["authors_json"]),
            "abstract": paper["abstract"],
            "year": paper["year"],
            "pub": paper["pub"],
            "doctype": paper["doctype"],
            "metadata": json.loads(paper["metadata_json"]),
            "identifiers": paper_aliases(connection, int(paper["id"])),
        },
        "versions": version_values,
    }


def fts_quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def build_search_expression(query: str, mode: str, scope: str) -> str:
    stripped = query.strip()
    if not stripped:
        raise LiteratureError("Search query cannot be empty.", 2)
    if mode == "fts":
        expression = stripped
    elif mode == "phrase":
        expression = fts_quote(stripped)
    else:
        terms = re.findall(r"[^\s,;:()]+", stripped, flags=re.UNICODE)
        if not terms:
            raise LiteratureError("Search query contains no usable terms.", 2)
        expression = " AND ".join(fts_quote(term) for term in terms)
    columns = SCOPE_COLUMNS[scope]
    if columns:
        return "{" + " ".join(columns) + "} : (" + expression + ")"
    return expression


def topic_filter_matches(
    connection: sqlite3.Connection, digest_id: int, topics: Sequence[str]
) -> tuple[list[str], list[str]]:
    if not topics:
        return [], []
    row = connection.execute(
        "SELECT digest_json FROM digests WHERE id = ?", (digest_id,)
    ).fetchone()
    if not row:
        return [], list(topics)
    digest = json.loads(row["digest_json"])
    matched = [
        topic
        for topic in topics
        if any(topic_match(facet, topic) for facet in digest["facets"])
    ]
    return matched, [topic for topic in topics if topic not in matched]


def facets_for_digest(
    connection: sqlite3.Connection, digest_id: int
) -> list[dict[str, str]]:
    rows = connection.execute(
        "SELECT key, label, summary FROM facets WHERE digest_id = ? ORDER BY ordinal",
        (digest_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def query_terms(query: str, mode: str) -> list[str]:
    if mode == "phrase":
        stripped = query.strip()
        return [stripped] if stripped else []
    terms = re.findall(r"[^\s,;:()]+", query.strip(), flags=re.UNICODE)
    if mode == "fts":
        terms = [
            term for term in terms if term.upper() not in {"AND", "OR", "NOT", "NEAR"}
        ]
        terms = [term.strip('"*{}[]') for term in terms]
    return [term for term in terms if term]


def matched_facets_for_query(
    connection: sqlite3.Connection, digest_id: int, query: str, mode: str
) -> list[dict[str, Any]]:
    row = connection.execute(
        "SELECT digest_json FROM digests WHERE id = ?", (digest_id,)
    ).fetchone()
    if not row:
        return []
    digest = json.loads(row["digest_json"])
    terms = query_terms(query, mode)
    matches: list[dict[str, Any]] = []
    for facet in digest["facets"]:
        facet_text = "\n".join(
            [
                facet["key"],
                facet["label"],
                *facet["aliases"],
                facet["summary"],
                *facet["keywords"],
                *facet["methods"],
                *facet["limitations"],
                *[join_record_text([finding]) for finding in facet["findings"]],
            ]
        )
        facet_haystack = facet_text.casefold()
        matched_terms = [term for term in terms if term.casefold() in facet_haystack]
        if not matched_terms:
            continue
        finding_matches = []
        for finding in facet["findings"]:
            finding_haystack = join_record_text([finding]).casefold()
            finding_terms = [
                term for term in terms if term.casefold() in finding_haystack
            ]
            if finding_terms:
                finding_matches.append(
                    {
                        "kind": finding["kind"],
                        "statement": finding["statement"],
                        "confidence": finding["confidence"],
                        "locator": finding["locator"],
                        "values": finding["values"],
                        "matched_terms": finding_terms,
                    }
                )
        matches.append(
            {
                "key": facet["key"],
                "label": facet["label"],
                "summary": facet["summary"],
                "matched_terms": matched_terms,
                "findings": finding_matches,
            }
        )
    return sorted(matches, key=lambda item: len(item["matched_terms"]), reverse=True)


def contains_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", value))


def search_library(
    connection: sqlite3.Connection,
    fts5: bool,
    query: str,
    *,
    scope: str,
    mode: str,
    topics: Sequence[str],
    year_from: int | None,
    year_to: int | None,
    limit: int,
) -> dict[str, Any]:
    if not query.strip():
        raise LiteratureError("Search query cannot be empty.", 2)
    parameters: list[Any] = []
    year_clauses: list[str] = []
    if year_from is not None:
        year_clauses.append("p.year >= ?")
        parameters.append(year_from)
    if year_to is not None:
        year_clauses.append("p.year <= ?")
        parameters.append(year_to)
    year_sql = "" if not year_clauses else " AND " + " AND ".join(year_clauses)
    candidate_limit = max(limit * 5, limit)
    use_fts = fts5 and (mode == "fts" or not contains_cjk(query))
    if use_fts:
        expression = build_search_expression(query, mode, scope)
        rows = connection.execute(
            f"""
            SELECT p.id AS paper_id, p.bibcode, p.title, p.year, p.pub,
                   v.id AS version_id, v.version_kind, v.sha256,
                   v.content_sha256,
                   d.id AS digest_id, d.reading_status, d.revision,
                   bm25(search_fts) AS score,
                   snippet(search_fts, -1, '[', ']', ' … ', 28) AS snippet
            FROM search_fts
            JOIN papers p ON p.id = CAST(search_fts.paper_id AS INTEGER)
            JOIN versions v ON v.id = CAST(search_fts.version_id AS INTEGER)
            JOIN digests d ON d.id = CAST(search_fts.digest_id AS INTEGER)
            WHERE search_fts MATCH ? AND d.is_current = 1 {year_sql}
            ORDER BY score
            LIMIT ?
            """,
            (expression, *parameters, candidate_limit),
        ).fetchall()
    else:
        columns = SCOPE_COLUMNS[scope] or SEARCH_COLUMNS[3:]
        searchable_columns = [
            column for column in columns if column in SEARCH_COLUMNS[3:]
        ]
        terms = re.findall(r"[^\s,;:()]+", query.strip(), flags=re.UNICODE)
        if mode == "phrase":
            terms = [query.strip()]
        if not terms:
            raise LiteratureError("Search query contains no usable terms.", 2)
        combined = " || ' ' || ".join(f"sd.{column}" for column in searchable_columns)
        term_clauses = [f"lower({combined}) LIKE ?" for _term in terms]
        term_parameters = [f"%{term.casefold()}%" for term in terms]
        rows = connection.execute(
            f"""
            SELECT p.id AS paper_id, p.bibcode, p.title, p.year, p.pub,
                    v.id AS version_id, v.version_kind, v.sha256,
                    v.content_sha256,
                   d.id AS digest_id, d.reading_status, d.revision,
                   0.0 AS score, substr(sd.overview, 1, 300) AS snippet
            FROM search_documents sd
            JOIN papers p ON p.id = sd.paper_id
            JOIN versions v ON v.id = sd.version_id
            JOIN digests d ON d.id = sd.digest_id
            WHERE {" AND ".join(term_clauses)} AND d.is_current = 1 {year_sql}
            LIMIT ?
            """,
            (*term_parameters, *parameters, candidate_limit),
        ).fetchall()
    results: list[dict[str, Any]] = []
    seen_papers: set[int] = set()
    for row in rows:
        paper_id = int(row["paper_id"])
        if paper_id in seen_papers:
            continue
        matched_topics, missing_topics = topic_filter_matches(
            connection, int(row["digest_id"]), topics
        )
        if missing_topics:
            continue
        seen_papers.add(paper_id)
        results.append(
            {
                "paper_id": paper_id,
                "bibcode": row["bibcode"],
                "title": row["title"],
                "year": row["year"],
                "pub": row["pub"],
                "version_id": row["version_id"],
                "version_kind": row["version_kind"],
                "artifact_sha256": row["sha256"],
                "content_sha256": row["content_sha256"],
                "reading_status": row["reading_status"],
                "digest_revision": row["revision"],
                "score": round(float(row["score"]), 6),
                "snippet": row["snippet"],
                "matched_topics": matched_topics,
                "matched_facets": matched_facets_for_query(
                    connection, int(row["digest_id"]), query, mode
                ),
                "facets": facets_for_digest(connection, int(row["digest_id"])),
            }
        )
        if len(results) >= limit:
            break
    return {
        "query": query,
        "scope": scope,
        "mode": mode,
        "fts5": use_fts,
        "fts5_available": fts5,
        "search_engine": "fts5" if use_fts else "substring",
        "topics": list(topics),
        "count": len(results),
        "results": results,
    }


def list_library(
    connection: sqlite3.Connection,
    *,
    topics: Sequence[str],
    year_from: int | None,
    year_to: int | None,
    limit: int,
) -> dict[str, Any]:
    clauses = []
    parameters: list[Any] = []
    if year_from is not None:
        clauses.append("p.year >= ?")
        parameters.append(year_from)
    if year_to is not None:
        clauses.append("p.year <= ?")
        parameters.append(year_to)
    where_sql = "" if not clauses else "WHERE " + " AND ".join(clauses)
    limit_sql = "" if topics else "LIMIT ?"
    if not topics:
        parameters.append(limit)
    rows = connection.execute(
        f"""
        SELECT p.id AS paper_id, p.bibcode, p.title, p.year, p.pub
        FROM papers p
        {where_sql}
        ORDER BY p.year DESC, p.title
        {limit_sql}
        """,
        parameters,
    ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        paper_id = int(row["paper_id"])
        version = preferred_version(connection, paper_id)
        if version is None or version["digest_id"] is None:
            continue
        matched, missing = topic_filter_matches(
            connection, int(version["digest_id"]), topics
        )
        if missing:
            continue
        results.append(
            {
                "paper_id": paper_id,
                "bibcode": row["bibcode"],
                "title": row["title"],
                "year": row["year"],
                "pub": row["pub"],
                "version_kind": version["version_kind"],
                "artifact_sha256": version["sha256"],
                "content_sha256": version["content_sha256"],
                "reading_status": version["reading_status"],
                "digest_revision": version["revision"],
                "matched_topics": matched,
                "facets": facets_for_digest(connection, int(version["digest_id"])),
            }
        )
        if len(results) >= limit:
            break
    return {"count": len(results), "topics": list(topics), "results": results}


def library_stats(
    connection: sqlite3.Connection, fts5: bool, library_dir: Path
) -> dict[str, Any]:
    tables = ("papers", "versions", "artifacts", "digests", "facets", "findings")
    counts = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }
    current = int(
        connection.execute(
            "SELECT COUNT(*) FROM digests WHERE is_current = 1"
        ).fetchone()[0]
    )
    reading_rows = connection.execute(
        "SELECT reading_status, COUNT(*) AS count FROM digests "
        "WHERE is_current = 1 GROUP BY reading_status"
    ).fetchall()
    object_bytes = 0
    object_files = 0
    objects_dir = library_dir / "objects"
    if objects_dir.is_dir():
        for path in objects_dir.rglob("*"):
            if path.is_file():
                object_files += 1
                object_bytes += path.stat().st_size
    return {
        "tool_version": VERSION,
        "database_schema_version": DATABASE_SCHEMA_VERSION,
        "digest_schema_version": DIGEST_SCHEMA_VERSION,
        "library_dir": str(library_dir),
        "database_path": str(library_dir / "literature.sqlite3"),
        "fts5": fts5,
        "counts": {**counts, "current_digests": current},
        "reading_status": {row["reading_status"]: row["count"] for row in reading_rows},
        "objects": {"files": object_files, "bytes": object_bytes},
    }


def rebuild_index(connection: sqlite3.Connection, fts5: bool) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT p.id AS paper_id, v.id AS version_id, v.text_path,
               d.id AS digest_id, d.digest_json
        FROM papers p
        JOIN versions v ON v.paper_id = p.id
        JOIN digests d ON d.version_id = v.id AND d.is_current = 1
        ORDER BY v.id
        """
    ).fetchall()
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("DELETE FROM search_documents")
        if fts5:
            connection.execute("DELETE FROM search_fts")
        for row in rows:
            full_text_value = ""
            if row["text_path"] and Path(row["text_path"]).is_file():
                full_text_value = Path(row["text_path"]).read_text(
                    encoding="utf-8", errors="replace"
                )
            document = build_search_document(
                connection,
                int(row["paper_id"]),
                int(row["version_id"]),
                int(row["digest_id"]),
                json.loads(row["digest_json"]),
                full_text_value,
            )
            replace_search_document(connection, document, fts5)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"status": "rebuilt", "documents": len(rows), "fts5": fts5}


def execute(
    args: argparse.Namespace,
    *,
    environ: Mapping[str, str],
    stdin: TextIO,
    stdout: TextIO,
) -> int:
    if args.command == "template":
        stdout.write(pretty_json(digest_template()))
        return 0
    if args.command == "validate-digest":
        digest = validate_digest(load_json(args.digest, stdin))
        stdout.write(
            pretty_json(
                {
                    "status": "valid",
                    "schema_version": digest["schema_version"],
                    "reading_status": digest["reading"]["status"],
                    "facets": len(digest["facets"]),
                    "findings": sum(
                        len(facet["findings"]) for facet in digest["facets"]
                    ),
                }
            )
        )
        return 0

    library_dir = (
        Path(args.library_dir).expanduser().resolve()
        if args.library_dir
        else default_library_dir(environ)
    )
    connection, fts5 = connect_library(library_dir)
    try:
        if args.command == "init":
            result = {
                "status": "initialized",
                **library_stats(connection, fts5, library_dir),
            }
        elif args.command == "ingest":
            manifest_payload = load_json(args.manifest, stdin)
            manifest = select_manifest_result(manifest_payload, args.identifier)
            digest = validate_digest(load_json(args.digest, stdin))
            result = ingest_record(
                connection,
                fts5,
                library_dir,
                manifest,
                digest,
                merge=args.merge,
            )
        elif args.command == "lookup":
            result = {
                "results": [
                    lookup_one(
                        connection,
                        identifier,
                        topics=args.topic,
                        artifact_hash=args.sha256,
                        include_digest=args.include_digest,
                    )
                    for identifier in args.identifiers
                ]
            }
        elif args.command == "show":
            result = show_paper(
                connection,
                args.identifier,
                history=args.history,
                include_fulltext=args.include_fulltext,
            )
        elif args.command == "search":
            result = search_library(
                connection,
                fts5,
                args.query,
                scope=args.scope,
                mode=args.mode,
                topics=args.topic,
                year_from=args.year_from,
                year_to=args.year_to,
                limit=args.limit,
            )
        elif args.command == "list":
            result = list_library(
                connection,
                topics=args.topic,
                year_from=args.year_from,
                year_to=args.year_to,
                limit=args.limit,
            )
        elif args.command == "stats":
            result = library_stats(connection, fts5, library_dir)
        elif args.command == "reindex":
            result = rebuild_index(connection, fts5)
        else:
            raise LiteratureError(f"Unsupported command: {args.command}", 2)
        stdout.write(pretty_json(result))
        return 0
    finally:
        connection.close()


def run(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return execute(
            args,
            environ=environ if environ is not None else os.environ,
            stdin=stdin or sys.stdin,
            stdout=stdout or sys.stdout,
        )
    except (LiteratureError, sqlite3.Error, OSError) as exc:
        (stderr or sys.stderr).write(f"error: {exc}\n")
        return exc.exit_code if isinstance(exc, LiteratureError) else 1


def main() -> None:
    ads_api.configure_stdio()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
