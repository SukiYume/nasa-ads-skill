#!/usr/bin/env python3
"""Persistent, searchable, evidence-aware literature memory for SciX records."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import unicodedata
import uuid
from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, TextIO

import ads_api
import fulltext
import library_catalog

sys.modules.setdefault("literature_db", sys.modules[__name__])

VERSION = "3.1.0"
DATABASE_SCHEMA_VERSION = 4
DIGEST_SCHEMA_VERSION = 4
DIGEST_REQUIRED_FIELDS = ("schema_version", "language", "facets", "reading")
DIGEST_LANGUAGE = "zh-CN"
DIGEST_LIST_FIELDS = (
    "keywords",
    "entities",
    "datasets",
    "methods",
    "global_limitations",
    "assessment",
    "data_products",
)
DIGEST_FIELDS = {*DIGEST_REQUIRED_FIELDS, "overview", *DIGEST_LIST_FIELDS}
READING_STATUSES = {"full", "targeted", "visual"}
READING_STATUS_RANK = {"targeted": 1, "visual": 2, "full": 3}
FINDING_KINDS = {
    "measurement",
    "constraint",
    "interpretation",
    "prediction",
    "nondetection",
    "method",
    "comparison",
    "limitation",
}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
STUDY_TYPES = {
    "observational",
    "theoretical",
    "simulation",
    "laboratory",
    "instrumentation",
    "methods",
    "catalog",
    "review",
}
ENTITY_TYPES = {
    "source",
    "instrument",
    "survey",
    "catalog",
    "software",
    "simulation",
    "model",
    "other",
}
DATASET_TYPES = {
    "observation",
    "survey",
    "archival",
    "catalog",
    "simulation",
    "laboratory",
}
LOCATOR_FIELDS = (
    "section",
    "page",
    "figure",
    "table",
    "equation",
    "appendix",
    "paragraph",
)
VALUE_STATUSES = {
    "measured",
    "fitted",
    "derived",
    "fixed",
    "assumed",
    "predicted",
    "upper-limit",
    "lower-limit",
}
VALUE_TEXT_FIELDS = (
    "symbol",
    "unit",
    "uncertainty",
    "qualifier",
    "model",
    "dataset",
    "method",
    "condition",
    "cited_from",
)
PARAMETER_FIELDS = ("name", "value", "range", "status", *VALUE_TEXT_FIELDS)
DATA_PRODUCT_TYPES = {"data", "code", "catalog", "table", "software", "other"}
COVERAGE_ROLES = {
    "scientific",
    "methods",
    "context",
    "limitations",
    "data-products",
    "references",
    "administrative",
}
GENERIC_SECTION_LABELS = {
    "all sections",
    "complete article",
    "entire article",
    "full article",
    "full paper",
    "whole article",
    "全文",
    "全部章节",
    "整篇文章",
    "整篇论文",
}
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
    validate.add_argument(
        "--text",
        help="prepared article text; checks that each finding quote occurs in it",
    )

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
    update_mode = ingest.add_mutually_exclusive_group()
    update_mode.add_argument(
        "--merge",
        action="store_true",
        help="merge the incoming evidence into the stored digest in place",
    )
    update_mode.add_argument(
        "--replace-digest",
        action="store_true",
        help=(
            "replace the stored digest in place with a complete full or "
            "whole-document visual digest"
        ),
    )
    enrich = subparsers.add_parser(
        "enrich", help="update metadata and identifiers for an existing paper"
    )
    enrich.add_argument("--manifest", required=True, help="fulltext.py manifest JSON")
    enrich.add_argument(
        "--identifier",
        help="select one input when --manifest contains a multi-result wrapper",
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

    passage = subparsers.add_parser(
        "passage",
        help=(
            "return bounded passages of a stored article: a finding's paragraph, "
            "a section, or paragraphs matching terms"
        ),
    )
    passage.add_argument("identifier")
    passage.add_argument(
        "--finding",
        action="append",
        default=[],
        help="finding_id from findings or parameters rows; repeat for several",
    )
    passage.add_argument(
        "--section",
        action="append",
        default=[],
        help="section number or heading, such as 2.3 or Discussion; repeat for several",
    )
    passage.add_argument(
        "--grep",
        action="append",
        default=[],
        help="term that every returned paragraph contains; repeat to require several",
    )
    passage.add_argument(
        "--outline",
        action="store_true",
        help="list stored section headings with sizes and digest gists",
    )
    passage.add_argument(
        "--sha256",
        help="select a known artifact, extracted-text, or content SHA256",
    )
    passage.add_argument(
        "--context",
        type=int,
        default=0,
        choices=range(0, 6),
        metavar="0-5",
        help="neighboring paragraphs to include on each side (default: 0)",
    )
    passage.add_argument(
        "--max-chars",
        type=int,
        default=3000,
        help="maximum characters per passage; 0 returns complete passages (default: 3000)",
    )
    passage.add_argument(
        "--limit",
        type=ads_api.positive_int,
        default=5,
        help="maximum paragraphs returned for --grep (default: 5)",
    )

    show = subparsers.add_parser("show", help="show a stored paper and its evidence")
    show.add_argument("identifier")
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
        "list", help="list stored papers and their digest coverage"
    )
    list_command.add_argument("--topic", action="append", default=[])
    list_command.add_argument("--year-from", type=int)
    list_command.add_argument("--year-to", type=int)
    list_command.add_argument("--limit", type=ads_api.positive_int, default=50)
    findings = subparsers.add_parser(
        "findings",
        help=(
            "list citable findings (measurements, fits, inferences, predictions, "
            "constraints) from complete digests with locators and citation keys"
        ),
    )
    parameters = subparsers.add_parser(
        "parameters",
        help=(
            "list structured measured, fitted, and derived values from complete "
            "digests with their evidence locators"
        ),
    )
    for command, matched_text, status_help in (
        (
            findings,
            "finding statements, keywords, values, and attributions",
            "keep findings reporting a value with this status; repeat for several",
        ),
        (
            parameters,
            "value names, symbols, models, conditions, and findings",
            "keep only values with this status; repeat for several",
        ),
    ):
        command.add_argument(
            "query",
            nargs="?",
            default="",
            help=f"terms matched against {matched_text}",
        )
        command.add_argument(
            "--paper",
            action="append",
            default=[],
            help="restrict to one stored paper identifier; repeat for several",
        )
        command.add_argument(
            "--entity",
            help="restrict to papers whose digest names this object or alias",
        )
        command.add_argument(
            "--kind",
            action="append",
            choices=sorted(FINDING_KINDS),
            default=[],
            help="keep only findings of this kind; repeat for several",
        )
        command.add_argument(
            "--status",
            action="append",
            choices=sorted(VALUE_STATUSES),
            default=[],
            help=status_help,
        )
        command.add_argument("--year-from", type=int)
        command.add_argument("--year-to", type=int)
        command.add_argument("--limit", type=ads_api.positive_int, default=200)
        command.add_argument("--format", choices=("json", "csv"), default="json")
        command.add_argument(
            "--output", help="write the table to this file outside the managed library"
        )
    for command in (search, list_command, findings, parameters):
        command.add_argument("--collection")
        command.add_argument("--role", choices=library_catalog.WRITING_ROLES)
        command.add_argument("--tag")

    subparsers.add_parser("stats", help="show library and evidence coverage counts")
    audit = subparsers.add_parser(
        "audit",
        help="run read-only integrity, object, index, and digest-quality checks",
    )
    audit.add_argument(
        "--skip-hashes",
        action="store_true",
        help="skip artifact, extracted-text, and canonical-content hash checks",
    )
    backup = subparsers.add_parser(
        "backup", help="create a consistent database and object-store backup"
    )
    backup.add_argument(
        "--destination",
        help="new backup directory; defaults to a timestamped sibling backup",
    )
    subparsers.add_parser("reindex", help="rebuild the local search index")
    subparsers.add_parser(
        "compact", help="return the space of removed records to the file system"
    )
    migrate = subparsers.add_parser(
        "migrate",
        help="back up a library from the previous release and convert it to this release",
    )
    migrate.add_argument(
        "--destination",
        help="new backup directory; defaults to a timestamped sibling backup",
    )
    restore = subparsers.add_parser(
        "restore", help="restore a backup to a new library directory"
    )
    restore.add_argument("backup")
    restore.add_argument("--destination", required=True)
    library_catalog.add_parser_commands(subparsers)
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
    version_id INTEGER NOT NULL UNIQUE REFERENCES versions(id) ON DELETE CASCADE,
    reading_status TEXT NOT NULL,
    digest_hash TEXT NOT NULL,
    digest_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

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


FTS_TABLE_SQL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5("
    "paper_id UNINDEXED, version_id UNINDEXED, digest_id UNINDEXED, "
    + ", ".join(SEARCH_COLUMNS[3:])
    + ", content = 'search_documents', content_rowid = 'id', "
    "tokenize = 'unicode61 remove_diacritics 2')"
)
FTS_INSERT_SQL = (
    f"INSERT INTO search_fts(rowid, {', '.join(SEARCH_COLUMNS)}) VALUES (new.id, "
    + ", ".join(f"new.{column}" for column in SEARCH_COLUMNS)
    + ");"
)
FTS_DELETE_SQL = (
    f"INSERT INTO search_fts(search_fts, rowid, {', '.join(SEARCH_COLUMNS)}) "
    "VALUES ('delete', old.id, "
    + ", ".join(f"old.{column}" for column in SEARCH_COLUMNS)
    + ");"
)
# The index reads its text from search_documents; these triggers keep it in step.
FTS_TRIGGERS = {
    "search_documents_insert": f"AFTER INSERT ON search_documents BEGIN {FTS_INSERT_SQL} END",
    "search_documents_delete": f"AFTER DELETE ON search_documents BEGIN {FTS_DELETE_SQL} END",
    "search_documents_update": (
        f"AFTER UPDATE ON search_documents BEGIN {FTS_DELETE_SQL} {FTS_INSERT_SQL} END"
    ),
}


def create_search_index(connection: sqlite3.Connection) -> None:
    connection.execute(FTS_TABLE_SQL)
    for name, body in FTS_TRIGGERS.items():
        connection.execute(f"CREATE TRIGGER IF NOT EXISTS {name} {body}")


def drop_search_index(connection: sqlite3.Connection) -> None:
    for name in FTS_TRIGGERS:
        connection.execute(f"DROP TRIGGER IF EXISTS {name}")
    connection.execute("DROP TABLE IF EXISTS search_fts")


def unsupported_schema(version: int) -> LiteratureError:
    if version < DATABASE_SCHEMA_VERSION:
        return LiteratureError(
            f"Database schema {version} comes from an earlier release; run "
            "literature_db.py migrate, which backs up the library and converts it "
            f"to schema {DATABASE_SCHEMA_VERSION}.",
            2,
        )
    return LiteratureError(
        f"Database schema {version} is newer than this release, which uses schema "
        f"{DATABASE_SCHEMA_VERSION}; update the skill.",
        2,
    )


def initialize_schema(connection: sqlite3.Connection) -> bool:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version not in (0, DATABASE_SCHEMA_VERSION):
        raise unsupported_schema(version)
    connection.executescript(SCHEMA_SQL)
    connection.executescript(library_catalog.SCHEMA_SQL)
    connection.execute(f"PRAGMA user_version = {DATABASE_SCHEMA_VERSION}")
    fts5 = True
    try:
        create_search_index(connection)
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
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version not in (0, DATABASE_SCHEMA_VERSION):
        connection.close()
        raise unsupported_schema(version)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        fts5 = initialize_schema(connection)
        return connection, fts5
    except Exception:
        connection.close()
        raise


def connect_library_readonly(
    library_dir: Path, *, allow_missing: bool = False
) -> tuple[sqlite3.Connection, bool]:
    database_path = (library_dir / "literature.sqlite3").resolve()
    if not database_path.is_file():
        if allow_missing:
            connection = sqlite3.connect(":memory:")
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            fts5 = initialize_schema(connection)
            connection.execute("PRAGMA query_only = ON")
            return connection, fts5
        raise LiteratureError(f"Literature database does not exist: {database_path}", 2)
    connection = sqlite3.connect(
        f"{database_path.as_uri()}?mode=ro", uri=True, timeout=10.0
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != DATABASE_SCHEMA_VERSION:
        connection.close()
        raise unsupported_schema(version)
    fts_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'search_fts'"
    ).fetchone()
    return connection, fts_table is not None


def load_json(path_value: str, stdin: TextIO) -> Any:
    try:
        if path_value == "-":
            return json.load(stdin)
        return json.loads(Path(path_value).expanduser().read_text(encoding="utf-8-sig"))
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
        if value.get(field) is None:
            value.pop(field, None)
            continue
        text = require_string(value[field], f"{name}.{field}", allow_empty=True)
        if text:
            value[field] = text
        else:
            del value[field]


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
    locator: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LiteratureError(f"{name} must be an array.", 2)
    optional_fields = tuple(optional_fields)
    list_fields = tuple(list_fields)
    allowed = {"name", *optional_fields, *list_fields}
    if locator:
        allowed.add("locator")
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        item_name = f"{name}[{index}]"
        item = require_mapping(raw, item_name)
        reject_unknown_fields(item, item_name, allowed)
        item["name"] = require_string(item.get("name"), f"{item_name}.name")
        validate_optional_string_fields(item, item_name, optional_fields)
        for field in list_fields:
            values = string_list(item.get(field, []), f"{item_name}.{field}")
            if values:
                item[field] = values
            else:
                item.pop(field, None)
        if locator and "locator" in item:
            raw_locator = item["locator"]
            if raw_locator is None or (
                isinstance(raw_locator, dict)
                and not any(
                    str(part).strip() for part in raw_locator.values() if part is not None
                )
            ):
                del item["locator"]
            else:
                item["locator"] = validate_locator(raw_locator, f"{item_name}.locator")
        result.append(item)
    return result


def require_vocabulary(value: Any, name: str, vocabulary: Iterable[str]) -> str:
    text = require_string(value, name)
    if text not in vocabulary:
        raise LiteratureError(
            f"{name} must be one of {', '.join(sorted(vocabulary))}.", 2
        )
    return text


def require_reference(
    value: str, name: str, names: set[str] | None, layer: str
) -> None:
    if names is not None and value.casefold() not in names:
        raise LiteratureError(f"{name} must name an entry of digest.{layer}.", 2)


def validate_locator(value: Any, name: str) -> dict[str, Any]:
    locator = require_mapping(value, name)
    unknown = set(locator) - set(LOCATOR_FIELDS)
    if unknown:
        raise LiteratureError(
            f"{name} has unsupported fields: {', '.join(sorted(unknown))}.", 2
        )
    validate_optional_string_fields(locator, name, LOCATOR_FIELDS)
    if not any(locator.values()):
        raise LiteratureError(
            f"{name} must identify a section, page, figure, table, equation, "
            "appendix, or paragraph.",
            2,
        )
    section = locator.get("section")
    if section and " ".join(section.split()).casefold() in GENERIC_SECTION_LABELS:
        raise LiteratureError(
            f"{name}.section must identify a specific article section.", 2
        )
    return locator


NUMBER_TEXT_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def range_bound(bound: Any) -> float | None:
    """A range bound as a number; strings keep a value's printed digits."""
    if isinstance(bound, bool):
        return None
    if isinstance(bound, (int, float)):
        return float(bound) if math.isfinite(bound) else None
    if isinstance(bound, str) and NUMBER_TEXT_PATTERN.fullmatch(bound.strip()):
        number = float(bound)
        return number if math.isfinite(number) else None
    return None


def validate_values(
    value: Any,
    name: str,
    *,
    datasets: set[str] | None = None,
    methods: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LiteratureError(f"{name} must be an array.", 2)
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        item_name = f"{name}[{index}]"
        item = require_mapping(raw, item_name)
        reject_unknown_fields(item, item_name, PARAMETER_FIELDS)
        item["name"] = require_string(item.get("name"), f"{item_name}.name")
        bounds = item.get("range")
        if bounds is None or bounds == []:
            item.pop("range", None)
        else:
            numbers = (
                [range_bound(bound) for bound in bounds]
                if isinstance(bounds, list) and len(bounds) == 2
                else None
            )
            if numbers is None or None in numbers:
                raise LiteratureError(
                    f"{item_name}.range must be [low, high], each a finite number "
                    "or a number written as a string such as \"57175.743510388\".",
                    2,
                )
            if numbers[0] > numbers[1]:
                raise LiteratureError(f"{item_name}.range low exceeds high.", 2)
            item["range"] = [
                bound.strip() if isinstance(bound, str) else bound for bound in bounds
            ]
        item_value = item.get("value")
        if "range" in item and (
            item_value is None or (isinstance(item_value, str) and not item_value.strip())
        ):
            item.pop("value", None)
        elif isinstance(item_value, bool) or not isinstance(
            item_value, (str, int, float)
        ):
            raise LiteratureError(
                f"{item_name}.value must be a string or number; give a range "
                "for an interval without a central value.",
                2,
            )
        elif isinstance(item_value, float) and not math.isfinite(item_value):
            raise LiteratureError(f"{item_name}.value must be finite.", 2)
        validate_optional_string_fields(item, item_name, (*VALUE_TEXT_FIELDS, "status"))
        status = item.get("status")
        if status is None:
            raise LiteratureError(f"{item_name}.status is required.", 2)
        if status not in VALUE_STATUSES:
            raise LiteratureError(
                f"{item_name}.status must be one of "
                f"{', '.join(sorted(VALUE_STATUSES))}.",
                2,
            )
        if "dataset" in item:
            require_reference(item["dataset"], f"{item_name}.dataset", datasets, "datasets")
        if "method" in item:
            require_reference(item["method"], f"{item_name}.method", methods, "methods")
        result.append(item)
    return result


def normalized_heading(value: str) -> str:
    return " ".join(str(value).split()).casefold()


def validate_section_entries(value: Any, name: str) -> list[dict[str, str]]:
    """Validate read sections: a heading string or {heading, gist} each."""
    if not isinstance(value, list):
        raise LiteratureError(f"{name} must be an array.", 2)
    result: list[dict[str, str]] = []
    positions: dict[str, int] = {}
    for index, raw in enumerate(value):
        item_name = f"{name}[{index}]"
        item = require_mapping({"heading": raw} if isinstance(raw, str) else raw, item_name)
        reject_unknown_fields(item, item_name, {"heading", "gist"})
        heading = require_string(item.get("heading"), f"{item_name}.heading")
        key = normalized_heading(heading)
        if key in GENERIC_SECTION_LABELS:
            raise LiteratureError(
                f"{item_name}.heading must name a real article section.", 2
            )
        gist = require_string(
            item.get("gist") or "", f"{item_name}.gist", allow_empty=True
        )
        if key in positions:
            if gist and "gist" not in result[positions[key]]:
                result[positions[key]]["gist"] = gist
            continue
        entry = {"heading": heading}
        if gist:
            entry["gist"] = gist
        positions[key] = len(result)
        result.append(entry)
    return result


def optional_string_list(record: dict[str, Any], field: str, name: str) -> None:
    """Validate an optional list of strings and drop it when empty."""
    values = string_list(record.get(field, []), f"{name}.{field}")
    if values:
        record[field] = values
    else:
        record.pop(field, None)


def validate_digest(
    raw: Any, *, check_references: bool | None = None
) -> dict[str, Any]:
    """Validate a digest and return its stored form.

    Complete readings (full, visual) carry the overview; a targeted reading
    needs only the facets it adds. Cross-references to datasets and methods are
    checked for complete readings; a targeted digest may reference records that
    only the stored digest holds, so its references are checked after the merge.
    Optional fields left empty are dropped.
    """
    digest = require_mapping(raw, "digest")
    missing = set(DIGEST_REQUIRED_FIELDS) - set(digest)
    if missing:
        raise LiteratureError(
            f"digest is missing required fields: {', '.join(sorted(missing))}.", 2
        )
    unknown = set(digest) - DIGEST_FIELDS
    if unknown:
        raise LiteratureError(
            f"digest has unsupported fields: {', '.join(sorted(unknown))}.", 2
        )
    schema_version = digest["schema_version"]
    if isinstance(schema_version, bool) or schema_version != DIGEST_SCHEMA_VERSION:
        raise LiteratureError(
            f"digest.schema_version must be {DIGEST_SCHEMA_VERSION}; generate the "
            "skeleton with literature_db.py template.",
            2,
        )
    for field in DIGEST_LIST_FIELDS:
        if digest.get(field) is None:
            digest[field] = []

    reading = require_mapping(digest["reading"], "digest.reading")
    status = require_string(reading.get("status"), "digest.reading.status")
    if status not in READING_STATUSES:
        raise LiteratureError(
            "digest.reading.status must be full, targeted, or visual.", 2
        )
    complete = status in {"full", "visual"}
    if check_references is None:
        check_references = complete
    digest["language"] = require_string(digest["language"], "digest.language")

    if "overview" not in digest:
        if complete:
            raise LiteratureError("digest is missing required fields: overview.", 2)
        digest["overview"] = {}
    overview = require_mapping(digest["overview"], "digest.overview")
    reject_unknown_fields(
        overview, "digest.overview", {"tldr", "summary", "questions", "study_types"}
    )
    for field in ("tldr", "summary"):
        if complete:
            overview[field] = require_string(
                overview.get(field), f"digest.overview.{field}"
            )
        else:
            validate_optional_string_fields(overview, "digest.overview", (field,))
    overview["questions"] = string_list(
        overview.get("questions", []), "digest.overview.questions"
    )
    study_types = string_list(
        overview.get("study_types", []), "digest.overview.study_types"
    )
    for index, study_type in enumerate(study_types):
        require_vocabulary(
            study_type, f"digest.overview.study_types[{index}]", STUDY_TYPES
        )
    if complete and not study_types:
        raise LiteratureError(
            "digest.overview.study_types must name at least one study type.", 2
        )
    if study_types:
        overview["study_types"] = study_types
    else:
        overview.pop("study_types", None)
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
        optional_fields=("type", "description", "cited_from"),
        list_fields=("identifiers",),
        locator=True,
    )
    digest["methods"] = validate_named_records(
        digest["methods"],
        "digest.methods",
        optional_fields=("description", "cited_from"),
        list_fields=("assumptions",),
        locator=True,
    )
    for layer, vocabulary in (("entities", ENTITY_TYPES), ("datasets", DATASET_TYPES)):
        for index, record in enumerate(digest[layer]):
            require_vocabulary(
                record.get("type"), f"digest.{layer}[{index}].type", vocabulary
            )
    dataset_names = (
        {record["name"].casefold() for record in digest["datasets"]}
        if check_references
        else None
    )
    method_names = (
        {record["name"].casefold() for record in digest["methods"]}
        if check_references
        else None
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
            {"key", "label", "summary", "aliases", "keywords", "methods", "findings"},
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
        for field in ("aliases", "keywords", "methods"):
            optional_string_list(facet, field, facet_name)
        for index, method in enumerate(facet.get("methods", [])):
            require_reference(
                method, f"{facet_name}.methods[{index}]", method_names, "methods"
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
                    "quote",
                    "values",
                    "keywords",
                    "cited_from",
                    "compared_with",
                },
            )
            finding["statement"] = require_string(
                finding.get("statement"), f"{finding_name}.statement"
            )
            finding["kind"] = require_vocabulary(
                finding.get("kind"), f"{finding_name}.kind", FINDING_KINDS
            )
            finding["confidence"] = require_vocabulary(
                finding.get("confidence"), f"{finding_name}.confidence", CONFIDENCE_LEVELS
            )
            finding["locator"] = validate_locator(
                finding.get("locator"), f"{finding_name}.locator"
            )
            values = validate_values(
                finding.get("values", []),
                f"{finding_name}.values",
                datasets=dataset_names,
                methods=method_names,
            )
            if values:
                finding["values"] = values
            else:
                finding.pop("values", None)
            for field in ("keywords", "compared_with"):
                optional_string_list(finding, field, finding_name)
            validate_optional_string_fields(
                finding, finding_name, ("cited_from", "quote")
            )
            if "quote" in finding:
                finding["quote"] = " ".join(finding["quote"].split())
            findings.append(finding)
        facet["findings"] = findings
        facets.append(facet)
    digest["facets"] = facets
    for field in ("global_limitations", "assessment"):
        digest[field] = string_list(digest[field], f"digest.{field}")

    products = validate_named_records(
        digest["data_products"],
        "digest.data_products",
        optional_fields=("type", "url", "availability", "locator"),
    )
    for index, product in enumerate(products):
        product["type"] = product.get("type", "other")
        require_vocabulary(
            product["type"], f"digest.data_products[{index}].type", DATA_PRODUCT_TYPES
        )
    digest["data_products"] = products

    reject_unknown_fields(
        reading,
        "digest.reading",
        {"status", "sections", "visual_page_ranges", "unread_sections", "notes"},
    )
    reading["status"] = status
    reading["sections"] = validate_section_entries(
        reading.get("sections", []), "digest.reading.sections"
    )
    if not reading["sections"]:
        raise LiteratureError(
            "digest.reading.sections must list the sections that were read.", 2
        )
    for field in ("visual_page_ranges", "unread_sections"):
        optional_string_list(reading, field, "digest.reading")
    validate_optional_string_fields(reading, "digest.reading", ("notes",))
    if status == "visual" and not reading.get("visual_page_ranges"):
        raise LiteratureError(
            "digest.reading.visual_page_ranges cannot be empty for visual reading.", 2
        )
    if complete and reading.get("unread_sections"):
        raise LiteratureError(
            "A complete full or visual digest cannot list unread sections.", 2
        )
    if complete and not overview["questions"]:
        raise LiteratureError(
            "A complete full or visual digest requires at least one research question.",
            2,
        )
    digest["reading"] = reading
    return digest


def require_chinese_digest(digest: Mapping[str, Any]) -> None:
    """Authored digests are written in Chinese so one library reads in one language."""
    if digest["language"] != DIGEST_LANGUAGE:
        raise LiteratureError(
            f"digest.language must be {DIGEST_LANGUAGE}; write the prose fields in "
            "Chinese and keep quotes, names, symbols, and units as the article prints them.",
            2,
        )
    prose: list[tuple[str, str]] = [
        (f"overview.{field}", digest["overview"].get(field, ""))
        for field in ("tldr", "summary")
    ]
    prose += [
        (f"overview.questions[{index}]", question)
        for index, question in enumerate(digest["overview"].get("questions", []))
    ]
    for layer in ("datasets", "methods"):
        prose += [
            (f"{layer}[{index}].description", record.get("description", ""))
            for index, record in enumerate(digest[layer])
        ]
    for index, facet in enumerate(digest["facets"]):
        prose.append((f"facets[{index}].summary", facet["summary"]))
    prose += [
        (f"finding {identifier}", finding["statement"])
        for identifier, _facet, finding in iter_findings(digest)
    ]
    prose += [
        (f"reading.sections[{index}].gist", section.get("gist", ""))
        for index, section in enumerate(digest["reading"]["sections"])
    ]
    for field in ("global_limitations", "assessment"):
        prose += [
            (f"{field}[{index}]", text) for index, text in enumerate(digest[field])
        ]
    foreign = [path for path, text in prose if text and not contains_cjk(text)]
    if foreign:
        raise LiteratureError(
            "Write these digest fields in Chinese: " + listed_ids(foreign) + ".", 2
        )


def finding_id(facet_key: str, index: int) -> str:
    """Stable reference to the ``index``-th (zero-based) finding of a facet."""
    return f"{facet_key}.{index + 1}"


def iter_findings(
    digest: Mapping[str, Any],
) -> Iterable[tuple[str, Mapping[str, Any], Mapping[str, Any]]]:
    for facet in digest.get("facets", []):
        for index, finding in enumerate(facet.get("findings", [])):
            yield finding_id(facet["key"], index), facet, finding


STATEMENT_REFERENCE_PATTERN = re.compile(
    r"\b(?:FRB|PSR|SGR|GRB|AT|SN|XTE|GW|J|B|AR|Abell|NGC|IC|UGC|HD|Mrk)\s?\d[\w.+-]*"
    r"|\b(?:19|20)\d{2}[a-z]?\b"
    r"|\b(?:fig(?:ure)?s?|tab(?:le)?s?|sect(?:ion)?s?|eqs?|equations?|appendix|"
    r"chapter|paper|model|case|run|component|stage|phase|step)\.?\s*\(?[a-z]?\d[\d.]*"
    r"|(?:图|表|式|公式|方程|附录|节|章|模型|情形|成分|阶段|步骤)\s*\(?[A-Za-z]?\d[\d.]*"
    r"|第\s*\d+",
    re.IGNORECASE,
)
# A digit right after a comma is a subscript, and one right after an operator belongs
# to an expression such as a slope plus one; neither is a reported number.
STATEMENT_NUMBER_PATTERN = re.compile(r"(?<![\w.,+\-^_*/])[-+\u2212]?\d+(?:\.\d+)?")
RANGE_TEXT_PATTERN = re.compile(
    r"\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*(?:-|\u2013|\u2014|to|~)\s*"
    r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*"
)
UNCERTAINTY_TEXT_PATTERN = re.compile(
    r"\u00b1|\+/-|\+-|plus or minus|\+\s*\d[\d.]*\s*/\s*-\s*\d", re.IGNORECASE
)
LIMIT_TEXT_PATTERN = re.compile(
    r"^\s*(?:~\s*)?(?:<|>|\u2264|\u2265|less than|greater than|below|above|at most|at least)",
    re.IGNORECASE,
)
MULTIPLE_NUMBER_PATTERN = re.compile(r"\d\s*;\s*[-+]?\d|\d,\s+[-+]?\d")
SECTION_LABEL_PATTERN = re.compile(
    r"\b(?:tab(?:le)?|fig(?:ure)?|eq(?:uation)?)\.?\s*[A-Z]?\d", re.IGNORECASE
)
SEVERAL_WORKS_PATTERN = re.compile(r";|；")
MAX_VALUES_PER_FINDING = 8
MAX_VALUES_PER_DIGEST = 60
MAX_FINDINGS_PER_DIGEST = 40
MAX_STATEMENT_CHARS = 400
MAX_QUOTE_CHARS = 300
MIN_QUOTE_ANCHOR_CHARS = 12


def looks_computed(value: Any) -> bool:
    """A float with more significant digits than an article prints."""
    if not isinstance(value, float):
        return False
    digits = re.sub(r"[^0-9]", "", repr(value).split("e")[0]).lstrip("0")
    return len(digits) >= 15


def listed_ids(ids: Sequence[str], limit: int = 12) -> str:
    shown = ", ".join(ids[:limit])
    return shown + (f", and {len(ids) - limit} more" if len(ids) > limit else "")


def digest_warnings(
    digest: Mapping[str, Any], anchors: Mapping[str, Any] | None = None
) -> list[dict[str, str]]:
    """Flag likely losses of citable structure and excess detail; the reader confirms each."""
    warnings: list[dict[str, str]] = []

    def warn(path: str, message: str) -> None:
        warnings.append({"path": path, "message": message})

    total_values = 0
    total_findings = 0
    unquoted: list[str] = []
    for facet_index, facet in enumerate(digest.get("facets", [])):
        for finding_index, finding in enumerate(facet.get("findings", [])):
            total_findings += 1
            path = f"facets[{facet_index}].findings[{finding_index}]"
            values = finding.get("values", [])
            total_values += len(values)
            statement = finding.get("statement", "")
            stripped = STATEMENT_REFERENCE_PATTERN.sub(" ", statement)
            if not values and STATEMENT_NUMBER_PATTERN.search(stripped):
                warn(path, "The statement reports a number that is missing from values.")
            if len(statement) > MAX_STATEMENT_CHARS:
                warn(path, "Keep one citable result per finding; shorten or split the statement.")
            if len(finding.get("quote", "")) > MAX_QUOTE_CHARS:
                warn(path, "Shorten the quote to the words that state the result.")
            if not finding.get("quote"):
                unquoted.append(finding_id(facet["key"], finding_index))
            if len(values) > MAX_VALUES_PER_FINDING:
                warn(path, "Keep the numbers a manuscript would quote; summarize long tables with counts and ranges and register the table under data_products.")
            if SECTION_LABEL_PATTERN.search(finding.get("locator", {}).get("section", "")):
                warn(path, "Put table, figure, and equation labels in their own locator fields.")
            if SEVERAL_WORKS_PATTERN.search(finding.get("cited_from", "")):
                warn(path, "Name one source in cited_from; split findings that draw on several works.")
            for value_index, value in enumerate(values):
                value_path = f"{path}.values[{value_index}]"
                reported = value.get("value")
                if looks_computed(reported) or any(
                    looks_computed(bound) for bound in value.get("range") or []
                ):
                    warn(value_path, "Copy the value as printed, as a string when it is long or in scientific notation.")
                if value.get("status") == "fitted" and not value.get("model"):
                    warn(value_path, "Name the model behind the fitted value.")
                if SEVERAL_WORKS_PATTERN.search(value.get("cited_from", "")):
                    warn(value_path, "Name one source in cited_from.")
                if isinstance(reported, str):
                    if LIMIT_TEXT_PATTERN.search(reported):
                        warn(value_path, "Record a limit as status upper-limit or lower-limit with the bound as value.")
                    elif UNCERTAINTY_TEXT_PATTERN.search(reported):
                        warn(value_path, "Move the uncertainty from value to uncertainty.")
                    elif RANGE_TEXT_PATTERN.fullmatch(reported):
                        warn(value_path, "Record an interval as range [low, high].")
                    elif MULTIPLE_NUMBER_PATTERN.search(reported):
                        warn(value_path, "Record each number as its own value with its condition.")
                if UNCERTAINTY_TEXT_PATTERN.search(str(value.get("qualifier", ""))):
                    warn(value_path, "Move the uncertainty from qualifier to uncertainty.")
    if total_values > MAX_VALUES_PER_DIGEST:
        warn("facets", "Keep the values a manuscript would quote; leave configuration, sample logs, and table rows to the stored article.")
    if total_findings > MAX_FINDINGS_PER_DIGEST:
        warn("facets", "Keep the results a manuscript would cite; merge findings that are always cited together.")
    if digest.get("reading", {}).get("status") == "full" and unquoted:
        warn(
            "facets",
            f"Add a short verbatim quote to {listed_ids(unquoted)} so passage can return the paragraph that states each result.",
        )
    if anchors and anchors.get("unlocated"):
        warn(
            "facets",
            "Quotes for "
            f"{listed_ids(anchors['unlocated'])} do not occur in the article text; "
            "copy each one verbatim from the prepared text.",
        )
    return warnings


def digest_template() -> dict[str, Any]:
    """Return the schema 4 skeleton; blank optional fields are dropped on validation."""
    return {
        "schema_version": DIGEST_SCHEMA_VERSION,
        "language": "zh-CN",
        "overview": {
            "tldr": "",
            "summary": "",
            "questions": [""],
            "study_types": ["observational"],
        },
        "keywords": [],
        "entities": [{"name": "", "type": "source", "aliases": []}],
        "datasets": [
            {
                "name": "",
                "type": "observation",
                "description": "",
                "locator": {"section": ""},
            }
        ],
        "methods": [
            {
                "name": "",
                "description": "",
                "assumptions": [],
                "locator": {"section": ""},
            }
        ],
        "facets": [
            {
                "key": "topic-slug",
                "label": "",
                "summary": "",
                "findings": [
                    {
                        "statement": "",
                        "kind": "measurement",
                        "confidence": "high",
                        "locator": {"section": ""},
                        "quote": "",
                        "values": [
                            {
                                "name": "",
                                "value": "",
                                "uncertainty": "",
                                "unit": "",
                                "status": "measured",
                            }
                        ],
                        "cited_from": "",
                    },
                ],
            },
        ],
        "global_limitations": [],
        "assessment": [],
        "data_products": [],
        "reading": {
            "status": "full",
            "sections": [
                {"heading": "1 Introduction", "gist": ""},
                {"heading": "2 Observations", "gist": ""},
            ],
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
            old = result[positions[record_key]]
            for field, value in item.items():
                if isinstance(value, list):
                    old[field] = merge_string_lists(old.get(field, []), value)
                elif value and not old.get(field):
                    old[field] = value
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
        for field in ("aliases", "keywords", "methods"):
            old[field] = merge_string_lists(old.get(field, []), new_facet.get(field, []))
        old["findings"] = merge_findings(old["findings"], new_facet["findings"])
    return result


def merge_digests(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge a new reading into the stored digest of the same article version."""
    merged = json.loads(json.dumps(current))
    targeted = incoming["reading"]["status"] == "targeted"
    if not targeted:
        merged["language"] = incoming["language"]
        for field in ("tldr", "summary"):
            if incoming["overview"].get(field):
                merged["overview"][field] = incoming["overview"][field]
    for field in ("questions", "study_types"):
        merged["overview"][field] = merge_string_lists(
            merged["overview"].get(field, []), incoming["overview"].get(field, [])
        )
    for field in ("keywords", "global_limitations", "assessment"):
        merged[field] = merge_string_lists(merged[field], incoming[field])
    for field in ("entities", "datasets", "methods", "data_products"):
        merged[field] = merge_record_lists(merged[field], incoming[field], "name")
    merged["facets"] = merge_facets(merged["facets"], incoming["facets"])
    reading = merged["reading"]
    new_reading = incoming["reading"]
    was_complete = reading["status"] in {"full", "visual"}
    if READING_STATUS_RANK[new_reading["status"]] > READING_STATUS_RANK[reading["status"]]:
        reading["status"] = new_reading["status"]
    reading["visual_page_ranges"] = merge_string_lists(
        reading.get("visual_page_ranges", []), new_reading.get("visual_page_ranges", [])
    )
    reading["sections"] = [*reading["sections"], *new_reading["sections"]]
    if not was_complete:
        reading["unread_sections"] = new_reading.get("unread_sections", [])
    new_notes = new_reading.get("notes", "")
    if new_notes and new_notes not in reading.get("notes", ""):
        reading["notes"] = "\n".join(
            part for part in (reading.get("notes", ""), new_notes) if part
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
    for bibcode in fulltext.list_value(manifest.get("alternate_bibcode")):
        append("bibcode", bibcode)
    for doi in fulltext.list_value(manifest.get("doi")):
        append("doi", doi)
        arxiv_doi = re.match(r"10\.48550/arxiv\.(.+)", doi, re.IGNORECASE)
        if arxiv_doi and fulltext.arxiv_id_from_value(arxiv_doi[1]):
            append("arxiv", arxiv_doi[1])
    for arxiv_id in fulltext.list_value(manifest.get("arxiv_ids")):
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


def validate_visual_coverage(selected: dict[str, Any], digest: dict[str, Any]) -> None:
    pages = (selected.get("statistics") or {}).get("pages")
    if isinstance(pages, bool) or not isinstance(pages, int) or pages < 1:
        raise LiteratureError(
            "Visual completeness requires a verified positive page count.", 2
        )
    covered: set[int] = set()
    for value in digest["reading"].get("visual_page_ranges", []):
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", value.strip())
        if not match:
            raise LiteratureError(
                "Visual page ranges must contain positive page numbers or ascending ranges.",
                2,
            )
        first, last = int(match[1]), int(match[2] or match[1])
        if first < 1 or last < first or last > pages:
            raise LiteratureError(
                "Visual page ranges exceed the verified document bounds.", 2
            )
        covered.update(range(first, last + 1))
    if len(covered) != pages:
        raise LiteratureError(
            "Visual reading must cover every page of the document.", 2
        )


def validate_ingest_manifest(manifest: dict[str, Any], digest: dict[str, Any]) -> str:
    status = manifest.get("status")
    if status not in {"fulltext", "needs_visual_reading"}:
        raise LiteratureError(
            "A complete article digest requires a fulltext or needs_visual_reading manifest in the "
            "literature database.",
            2,
        )
    selected = require_mapping(manifest.get("selected"), "manifest.selected")
    # A stored manifest keeps download-cache paths in selected and names the
    # durable object-store copies in database_object.
    objects = manifest.get("database_object") or {}
    if isinstance(objects, dict) and objects.get("artifact_sha256") == selected.get(
        "sha256"
    ):
        if objects.get("artifact_path"):
            selected["artifact_path"] = objects["artifact_path"]
        if objects.get("text_sha256") == selected.get("text_sha256") and objects.get(
            "text_path"
        ):
            selected["text_path"] = objects["text_path"]
        manifest["selected"] = selected
    artifact = Path(require_string(selected.get("artifact_path"), "artifact_path"))
    if not artifact.is_file():
        raise LiteratureError(f"Selected artifact does not exist: {artifact}", 2)
    expected_hash = require_string(selected.get("sha256"), "selected.sha256")
    actual_hash = fulltext.sha256_file(artifact)
    if actual_hash != expected_hash:
        raise LiteratureError(
            "Selected artifact hash does not match its full-text manifest.", 2
        )
    content_hash = actual_hash
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
        full_text_value = text_path.read_text(encoding="utf-8", errors="replace")
        content_hash = fulltext.canonical_text_sha256(full_text_value)
        expected_content_hash = selected.get("content_sha256")
        if expected_content_hash and content_hash != expected_content_hash:
            raise LiteratureError(
                "Selected content hash does not match its full-text manifest.", 2
            )
        if digest["reading"]["status"] == "visual":
            raise LiteratureError(
                "A text-bearing fulltext manifest cannot use visual-only "
                "reading status.",
                2,
            )
    else:
        if digest["reading"]["status"] != "visual":
            raise LiteratureError(
                "A needs_visual_reading manifest requires visual reading coverage.", 2
            )
        validate_visual_coverage(selected, digest)
        expected_content_hash = selected.get("content_sha256")
        if expected_content_hash and expected_content_hash != actual_hash:
            raise LiteratureError(
                "A visual-reading manifest must use the raw artifact hash as "
                "its content identity.",
                2,
            )
    return content_hash


def validate_paper_metadata(
    manifest: dict[str, Any],
) -> list[tuple[str, str, str]]:
    require_string(manifest.get("title"), "manifest.title")
    aliases = aliases_from_manifest(manifest)
    canonical_key(aliases)
    return aliases


def validate_ingest_metadata(
    manifest: dict[str, Any],
) -> list[tuple[str, str, str]]:
    aliases = validate_paper_metadata(manifest)
    manifest_version_kind(manifest)
    return aliases


def atomic_copy(
    source: Path, destination: Path, expected_hash: str | None = None
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if expected_hash is None or fulltext.sha256_file(destination) == expected_hash:
            return
        raise LiteratureError(f"Stored object has an unexpected hash: {destination}")
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
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
        text_destination = object_dir / f"article-{text_hash}.txt"
        atomic_copy(text_source, text_destination, text_hash)
        full_text_value = text_destination.read_text(encoding="utf-8", errors="replace")
        if manifest.get("status") == "fulltext":
            content_hash = fulltext.canonical_text_sha256(full_text_value)

    stored_manifest = dict(manifest)
    stored_manifest["selected"] = {
        **selected,
        "artifact_path": str(artifact_destination.resolve()),
        "text_path": str(text_destination.resolve()) if text_destination else None,
        "text_sha256": text_hash,
        "content_sha256": content_hash,
    }
    stored_manifest["database_object"] = {
        "artifact_path": str(artifact_destination.resolve()),
        "text_path": str(text_destination.resolve()) if text_destination else None,
        "artifact_sha256": artifact_hash,
        "text_sha256": text_hash,
        "content_sha256": content_hash,
        "stored_at": fulltext.utc_now(),
    }
    manifest_identity = stable_digest(
        {
            "source": selected.get("candidate"),
            "final_url": selected.get("final_url"),
            "content_sha256": content_hash,
            "text_sha256": text_hash,
            "status": manifest.get("status"),
        }
    )
    manifest_destination = object_dir / f"manifest-{manifest_identity}.json"
    stored_manifest["manifest_path"] = str(manifest_destination.resolve())
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


def require_compatible_stored_digests(
    target: sqlite3.Row | None, source: sqlite3.Row | None
) -> None:
    if target is not None and source is not None:
        if json.loads(source["digest_json"]) != json.loads(target["digest_json"]):
            raise LiteratureError(
                "Automatic paper merge found different stored digests for "
                f"duplicate full-text versions {source['version_id']} "
                f"and {target['version_id']}. "
                "Reconcile both stored digests explicitly before retrying.",
                2,
            )


def merge_duplicate_versions(
    connection: sqlite3.Connection, target: int, source: int
) -> None:
    """Preserve reading data before removing a duplicate article version."""
    target_digest = stored_digest_row(connection, target)
    source_digest = stored_digest_row(connection, source)
    require_compatible_stored_digests(target_digest, source_digest)
    if source_digest is not None and target_digest is None:
        connection.execute(
            "UPDATE digests SET version_id = ? WHERE id = ?",
            (target, source_digest["id"]),
        )
    connection.execute(
        "UPDATE OR IGNORE artifacts SET version_id = ? WHERE version_id = ?",
        (target, source),
    )
    connection.execute(
        "INSERT OR IGNORE INTO version_labels(version_id, arxiv_id) "
        "SELECT ?, arxiv_id FROM version_labels WHERE version_id = ?",
        (target, source),
    )


def merge_papers(connection: sqlite3.Connection, paper_ids: Iterable[int]) -> int:
    """Combine records that one SciX manifest identifies as the same work.

    A preprint captured before its publication was indexed and the published
    record stored separately become one paper once SciX links their
    identifiers. The survivor keeps read versions; published metadata wins.
    Runs inside the caller's transaction and returns the surviving paper id.
    """
    rows = [
        connection.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        for paper_id in sorted(set(paper_ids))
    ]

    def survivor_rank(row: sqlite3.Row) -> tuple[bool, bool, int]:
        has_versions = connection.execute(
            "SELECT 1 FROM versions WHERE paper_id = ? LIMIT 1", (row["id"],)
        ).fetchone()
        return (has_versions is None, row["doctype"] == "eprint", row["id"])

    survivor, *others = sorted(rows, key=survivor_rank)
    published = next(
        (row for row in sorted(rows, key=lambda row: row["id"]) if row["doctype"] != "eprint"),
        survivor,
    )
    target = survivor["id"]
    metadata = json.loads(survivor["metadata_json"])
    for row in others:
        source = row["id"]
        for field, value in json.loads(row["metadata_json"]).items():
            if isinstance(value, list):
                metadata[field] = ordered_unique_casefolded_strings(
                    [*fulltext.list_value(metadata.get(field)), *value]
                )
            elif row["id"] == published["id"] or metadata.get(field) is None:
                metadata[field] = value if value is not None else metadata.get(field)
        connection.execute(
            "UPDATE identifiers SET paper_id = ? WHERE paper_id = ?", (target, source)
        )
        for version in connection.execute(
            "SELECT id, version_kind, content_sha256 FROM versions WHERE paper_id = ?",
            (source,),
        ).fetchall():
            duplicate = connection.execute(
                "SELECT id FROM versions WHERE paper_id = ? AND version_kind = ? "
                "AND content_sha256 = ?",
                (target, version["version_kind"], version["content_sha256"]),
            ).fetchone()
            if duplicate is not None:
                merge_duplicate_versions(connection, duplicate["id"], version["id"])
                connection.execute(
                    "DELETE FROM search_documents WHERE version_id = ?", (version["id"],)
                )
                connection.execute("DELETE FROM versions WHERE id = ?", (version["id"],))
            else:
                connection.execute(
                    "UPDATE versions SET paper_id = ? WHERE id = ?",
                    (target, version["id"]),
                )
        connection.execute(
            "UPDATE search_documents SET paper_id = ? WHERE paper_id = ?",
            (target, source),
        )
        connection.execute(
            "UPDATE OR IGNORE search_hits SET paper_id = ? WHERE paper_id = ?",
            (target, source),
        )
        connection.execute("DELETE FROM search_hits WHERE paper_id = ?", (source,))
        for brief in connection.execute(
            "SELECT * FROM briefs WHERE paper_id = ?", (source,)
        ).fetchall():
            kept = connection.execute(
                "SELECT * FROM briefs WHERE paper_id = ? AND source_hash = ?",
                (target, brief["source_hash"]),
            ).fetchone()
            if kept is None:
                connection.execute(
                    "UPDATE briefs SET paper_id = ? WHERE id = ?", (target, brief["id"])
                )
                continue
            if not kept["summary"] and brief["summary"]:
                connection.execute(
                    "UPDATE briefs SET summary = ?, keywords_json = ? WHERE id = ?",
                    (brief["summary"], brief["keywords_json"], kept["id"]),
                )
            connection.execute(
                "UPDATE search_hits SET brief_id = ? WHERE brief_id = ?",
                (kept["id"], brief["id"]),
            )
            connection.execute("DELETE FROM briefs WHERE id = ?", (brief["id"],))
        for table, column in (
            ("paper_collections", "collection_path"),
            ("paper_tags", "tag"),
            ("paper_roles", "role"),
        ):
            connection.execute(
                f"INSERT OR IGNORE INTO {table}(paper_id, {column}) "
                f"SELECT ?, {column} FROM {table} WHERE paper_id = ?",
                (target, source),
            )
        connection.execute(
            "UPDATE OR IGNORE paper_notes SET paper_id = ? WHERE paper_id = ?",
            (target, source),
        )
        citation = connection.execute(
            "SELECT citekey FROM citations WHERE paper_id = ?", (source,)
        ).fetchone()
        if citation and citation["citekey"] == published["bibcode"]:
            connection.execute("DELETE FROM citations WHERE paper_id = ?", (target,))
            connection.execute(
                "UPDATE citations SET paper_id = ? WHERE paper_id = ?", (target, source)
            )
        connection.execute("DELETE FROM papers WHERE id = ?", (source,))
    connection.execute(
        """
        UPDATE papers
        SET bibcode = ?, title = ?, authors_json = ?, abstract = ?, year = ?,
            pub = ?, doctype = ?, metadata_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            published["bibcode"] or survivor["bibcode"],
            published["title"],
            published["authors_json"],
            str(published["abstract"] or "").strip() and published["abstract"]
            or survivor["abstract"],
            published["year"] if published["year"] is not None else survivor["year"],
            published["pub"] or survivor["pub"],
            published["doctype"] or survivor["doctype"],
            json_text(metadata),
            fulltext.utc_now(),
            target,
        ),
    )
    return target


def reindex_paper_documents(connection: sqlite3.Connection, paper_id: int) -> int:
    rows = connection.execute(
        """
        SELECT v.id AS version_id, v.text_path, d.id AS digest_id, d.digest_json
        FROM versions v
        JOIN digests d ON d.version_id = v.id
        WHERE v.paper_id = ?
        ORDER BY v.id
        """,
        (paper_id,),
    ).fetchall()
    for row in rows:
        full_text_value = ""
        if row["text_path"] and Path(row["text_path"]).is_file():
            full_text_value = Path(row["text_path"]).read_text(
                encoding="utf-8", errors="replace"
            )
        document = build_search_document(
            connection,
            paper_id,
            int(row["version_id"]),
            int(row["digest_id"]),
            json.loads(row["digest_json"]),
            full_text_value,
        )
        replace_search_document(connection, document)
    return len(rows)


def resolve_paper_identity(
    connection: sqlite3.Connection,
    aliases: Sequence[tuple[str, str, str]],
) -> set[int]:
    """Resolve aliases inside the caller's transaction and search-index update."""
    matches = paper_ids_for_aliases(connection, aliases)
    if len(matches) > 1:
        matches = {merge_papers(connection, matches)}
    return matches


def manifest_version_kind(manifest: Mapping[str, Any]) -> str:
    selected = require_mapping(manifest.get("selected"), "manifest.selected")
    candidate = selected.get("candidate")
    if not isinstance(candidate, Mapping):
        return "unknown"
    return str(candidate.get("version") or "unknown")


def existing_version_id(
    connection: sqlite3.Connection,
    paper_id: int,
    version_kind: str,
    content_sha256: str,
) -> int | None:
    row = connection.execute(
        "SELECT id FROM versions "
        "WHERE paper_id = ? AND version_kind = ? AND content_sha256 = ?",
        (paper_id, version_kind, content_sha256),
    ).fetchone()
    return int(row["id"]) if row else None


def upsert_paper(
    connection: sqlite3.Connection,
    manifest: dict[str, Any],
    aliases: Sequence[tuple[str, str, str]],
    *,
    refresh_metadata: bool = False,
) -> int:
    matches = paper_ids_for_aliases(connection, aliases)
    if len(matches) > 1:
        matches = {merge_papers(connection, matches)}
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
        "property": ordered_unique_casefolded_strings(
            fulltext.list_value(manifest.get("property"))
        ),
        "doi": ordered_unique_casefolded_strings(
            fulltext.list_value(manifest.get("doi"))
        ),
        "arxiv_ids": ordered_unique_casefolded_strings(
            fulltext.list_value(manifest.get("arxiv_ids"))
        ),
        "citation_count": manifest.get("citation_count"),
        "read_count": manifest.get("read_count"),
        **{
            field: ordered_unique_casefolded_strings(
                fulltext.list_value(manifest.get(field))
            )
            for field in ("uat", "has")
        },
        **{
            field: manifest.get(field)
            for field in ("volume", "issue", "page", "eid", "pubdate")
        },
    }
    if matches:
        paper_id = matches.pop()
        existing = connection.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        existing_authors = json.loads(existing["authors_json"])
        existing_metadata = json.loads(existing["metadata_json"])
        # SciX lists a replaced bibcode, such as a preprint or .tmp. record,
        # among the alternates of the current record.
        superseded = (
            bibcode is not None
            and existing["bibcode"] not in (None, bibcode)
            and existing["bibcode"]
            in fulltext.list_value(manifest.get("alternate_bibcode"))
        )
        existing_preprint = (
            existing["doctype"] == "eprint"
            or "arxiv" in str(existing["bibcode"] or "").casefold()
            or str(existing["pub"] or "").casefold() in {"arxiv", "arxiv e-prints"}
        )
        incoming_preprint = (
            manifest.get("doctype") == "eprint"
            or "arxiv" in str(bibcode or "").casefold()
            or str(manifest.get("pub") or "").casefold() in {"arxiv", "arxiv e-prints"}
        )
        upgrade = superseded or (
            existing_preprint
            and manifest.get("doctype") == "article"
            and not incoming_preprint
            and bool(bibcode or manifest.get("pub"))
        )
        # Capture/enrich refresh the current source. Ingest can reuse an older
        # artifact manifest, whose bibliographic fields must stay historical.
        preserve_publication = (
            incoming_preprint
            and not existing_preprint
            and existing["doctype"] == "article"
            and bool(existing["bibcode"] or existing["pub"])
        )
        prefer_incoming = not preserve_publication and (
            upgrade or (
                refresh_metadata
                and (not existing["bibcode"] or existing["bibcode"] == bibcode)
            )
        )
        # A publication awaiting indexing keeps its preprint bibcode as an alias.
        bibcode = (
            existing["bibcode"]
            if preserve_publication
            else bibcode
            if upgrade
            else str(existing["bibcode"] or "").strip() or bibcode
        )
        title = title if prefer_incoming else str(existing["title"] or "").strip() or title
        authors = (
            (authors or existing_authors) if prefer_incoming else existing_authors or authors
        )
        abstract = (
            (abstract or existing["abstract"])
            if prefer_incoming
            else str(existing["abstract"] or "").strip() or abstract
        )
        year = (
            year
            if prefer_incoming and year is not None
            else existing["year"]
            if existing["year"] is not None
            else year
        )
        pub = (
            (manifest.get("pub") or existing["pub"])
            if prefer_incoming
            else str(existing["pub"] or "").strip() or manifest.get("pub")
        )
        doctype = (
            (manifest.get("doctype") or existing["doctype"])
            if prefer_incoming
            else str(existing["doctype"] or "").strip() or manifest.get("doctype")
        )
        for field in ("doi", "arxiv_ids"):
            metadata[field] = ordered_unique_casefolded_strings(
                [
                    *fulltext.list_value(existing_metadata.get(field)),
                    *metadata[field],
                ]
            )
        metadata["property"] = (
            metadata["property"] or existing_metadata.get("property", [])
            if prefer_incoming
            else existing_metadata.get("property") or metadata["property"]
        )
        for field in ("citation_count", "read_count"):
            if metadata[field] is None:
                metadata[field] = existing_metadata.get(field)
        for field in ("uat", "has"):
            metadata[field] = metadata[field] or existing_metadata.get(field, [])
        for field in ("volume", "issue", "page", "eid", "pubdate"):
            metadata[field] = (
                metadata[field] or existing_metadata.get(field)
                if prefer_incoming
                else existing_metadata.get(field) or metadata[field]
            )
        if (
            (bibcode, title, authors, year, pub, doctype)
            != (
                existing["bibcode"], existing["title"], existing_authors,
                existing["year"], existing["pub"], existing["doctype"],
            )
            or any(
                metadata[field] != existing_metadata.get(field)
                for field in ("doi", "arxiv_ids", "volume", "issue", "page", "eid")
            )
        ):
            connection.execute("DELETE FROM citations WHERE paper_id = ?", (paper_id,))
        connection.execute(
            """
            UPDATE papers
            SET bibcode = ?, title = ?, authors_json = ?,
                abstract = ?, year = ?, pub = ?, doctype = ?,
                metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                bibcode,
                title,
                json_text(authors),
                abstract,
                year,
                pub,
                doctype,
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
    version_kind = manifest_version_kind(manifest)
    version_id = existing_version_id(
        connection, paper_id, version_kind, stored["content_sha256"]
    )
    statistics = selected.get("statistics") or {}
    if version_id is not None:
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
    library_catalog.record_version_label(connection, version_id, manifest)
    return version_id, version_created


def stored_digest_row(
    connection: sqlite3.Connection, version_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM digests WHERE version_id = ?",
        (version_id,),
    ).fetchone()


def stored_digest_is_complete(row: sqlite3.Row | None) -> bool:
    if row is None:
        return False
    try:
        digest = validate_digest(json.loads(row["digest_json"]))
    except (json.JSONDecodeError, LiteratureError):
        return False
    return digest["reading"]["status"] in {"full", "visual"}


def insert_digest(
    connection: sqlite3.Connection,
    version_id: int,
    digest: dict[str, Any],
) -> tuple[int, bool, bool]:
    digest_hash = stable_digest(digest)
    stored_digest = stored_digest_row(connection, version_id)
    if stored_digest and stored_digest["digest_hash"] == digest_hash:
        return int(stored_digest["id"]), False, False
    values = (
        digest["reading"]["status"],
        digest_hash,
        json_text(digest),
        fulltext.utc_now(),
    )
    if stored_digest:
        connection.execute(
            "UPDATE digests SET reading_status = ?, digest_hash = ?, digest_json = ?, "
            "updated_at = ? WHERE id = ?",
            (*values, stored_digest["id"]),
        )
        return int(stored_digest["id"]), True, False
    cursor = connection.execute(
        "INSERT INTO digests(version_id, reading_status, digest_hash, digest_json, "
        "updated_at) VALUES (?, ?, ?, ?, ?)",
        (version_id, *values),
    )
    return int(cursor.lastrowid), True, True


def join_record_text(records: Iterable[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for record in records:
        for key in sorted(record):
            value = record[key]
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
    topics: list[str] = [
        *digest["keywords"],
        *json.loads(paper["metadata_json"]).get("uat", []),
    ]
    facet_parts: list[str] = []
    finding_parts: list[str] = []
    limitations: list[str] = [
        *digest["global_limitations"],
        *digest.get("assessment", []),
    ]
    for facet in digest["facets"]:
        topics.extend(
            [
                facet["key"],
                facet["label"],
                *facet.get("aliases", []),
                *facet.get("keywords", []),
            ]
        )
        facet_parts.extend(
            [facet["label"], facet["summary"], *facet.get("methods", [])]
        )
        for finding in facet["findings"]:
            finding_parts.append(finding["statement"])
            finding_parts.append(join_record_text(finding.get("values", [])))
            finding_parts.extend(finding.get("keywords", []))
            finding_parts.append(finding.get("cited_from", ""))
            finding_parts.extend(finding.get("compared_with", []))
    facet_parts.extend(
        section["gist"] for section in digest["reading"]["sections"] if "gist" in section
    )
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
            [overview["tldr"], overview["summary"], *overview["questions"]]
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
    connection: sqlite3.Connection, document: Mapping[str, str]
) -> None:
    connection.execute(
        "DELETE FROM search_documents WHERE version_id = ?", (document["version_id"],)
    )
    placeholders = ", ".join("?" for _ in SEARCH_COLUMNS)
    connection.execute(
        f"INSERT INTO search_documents({', '.join(SEARCH_COLUMNS)}, updated_at) "
        f"VALUES ({placeholders}, ?)",
        (*(document[column] for column in SEARCH_COLUMNS), fulltext.utc_now()),
    )


def prepare_ingest_digest(
    connection: sqlite3.Connection,
    paper_ids: set[int],
    version_kind: str,
    content_sha256: str,
    digest: dict[str, Any],
    *,
    merge: bool,
    replace_digest: bool,
) -> dict[str, Any]:
    """Check stored readings without changing paper identities or evidence."""
    readings: dict[tuple[str, str], sqlite3.Row] = {}
    for paper_id in sorted(paper_ids):
        for row in connection.execute(
            "SELECT d.*, v.version_kind, v.content_sha256 FROM versions v "
            "JOIN digests d ON d.version_id = v.id WHERE v.paper_id = ?",
            (paper_id,),
        ):
            key = (row["version_kind"], row["content_sha256"])
            require_compatible_stored_digests(readings.get(key), row)
            readings[key] = row
    stored = readings.get((version_kind, content_sha256))
    if digest["reading"]["status"] == "targeted" and not stored_digest_is_complete(stored):
        raise LiteratureError(
            "A targeted digest requires a complete full or whole-document visual "
            "digest for this exact article version.",
            2,
        )
    if replace_digest:
        if not paper_ids:
            raise LiteratureError(
                "--replace-digest requires an existing paper and stored digest.", 2
            )
        if digest["reading"]["status"] not in {"full", "visual"}:
            raise LiteratureError(
                "--replace-digest requires a complete full or whole-document "
                "visual digest.",
                2,
            )
        if stored is None:
            raise LiteratureError(
                "--replace-digest requires an existing stored digest for "
                "this exact article version.",
                2,
            )
    elif stored is not None:
        stored_payload = json.loads(stored["digest_json"])
        if merge:
            return merge_digests(stored_payload, digest)
        if stable_digest(stored_payload) != stable_digest(digest):
            raise LiteratureError(
                "This article version already has a different digest. Use "
                "--merge for additive evidence or --replace-digest for a "
                "verified complete replacement. Both operations update the "
                "single stored digest in place.",
                2,
            )
    return digest


def ingest_record(
    connection: sqlite3.Connection,
    fts5: bool,
    library_dir: Path,
    manifest: dict[str, Any],
    digest: dict[str, Any],
    *,
    merge: bool,
    replace_digest: bool = False,
) -> dict[str, Any]:
    digest = validate_digest(digest)
    incoming = digest
    aliases = validate_ingest_metadata(manifest)
    content_sha256 = validate_ingest_manifest(manifest, digest)
    prepare_ingest_digest(
        connection,
        paper_ids_for_aliases(connection, aliases),
        manifest_version_kind(manifest),
        content_sha256,
        digest,
        merge=merge,
        replace_digest=replace_digest,
    )
    stored = store_objects(library_dir, manifest)
    anchors = None
    if stored.get("text_path"):
        article_text = Path(stored["text_path"]).read_text(
            encoding="utf-8", errors="replace"
        )
        anchors = quote_anchors(
            incoming, article_text, article_sections(article_text, manifest, incoming)
        )
    warnings = digest_warnings(incoming, anchors)
    try:
        connection.execute("BEGIN IMMEDIATE")
        matching_papers = resolve_paper_identity(connection, aliases)
        digest = prepare_ingest_digest(
            connection,
            matching_papers,
            manifest_version_kind(manifest),
            stored["content_sha256"],
            digest,
            merge=merge,
            replace_digest=replace_digest,
        )
        paper_id = upsert_paper(connection, manifest, aliases)
        version_id, version_created = upsert_version(
            connection, paper_id, manifest, stored
        )
        digest_id, digest_changed, digest_created = insert_digest(
            connection, version_id, digest
        )
        reindex_paper_documents(connection, paper_id)
        stored_paper = connection.execute(
            "SELECT canonical_key FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        library_catalog.annotate_paper(connection, paper_id, tags=digest["keywords"])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "status": (
            "ingested"
            if digest_created
            else "updated"
            if digest_changed
            else "unchanged"
        ),
        "paper_id": paper_id,
        "version_id": version_id,
        "digest_id": digest_id,
        "version_created": version_created,
        "digest_created": digest_created,
        "digest_changed": digest_changed,
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
        **({"anchors": anchors} if anchors is not None else {}),
        "warnings": warnings,
        "classification_status": "complete"
        if library_catalog.paper_organization(connection, paper_id)["collections"]
        else "pending",
    }


def enrich_paper_metadata(
    connection: sqlite3.Connection,
    fts5: bool,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    aliases = validate_paper_metadata(manifest)
    try:
        connection.execute("BEGIN IMMEDIATE")
        matching = resolve_paper_identity(connection, aliases)
        if not matching:
            raise LiteratureError(
                "Metadata enrichment requires an existing paper identifier.", 2
            )
        expected_paper_id = next(iter(matching))
        paper_id = upsert_paper(connection, manifest, aliases, refresh_metadata=True)
        if paper_id != expected_paper_id:
            raise LiteratureError("Metadata enrichment changed paper identity.")
        versions_reindexed = reindex_paper_documents(connection, paper_id)
        paper = connection.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "status": "enriched",
        "paper_id": paper_id,
        "canonical_key": paper["canonical_key"],
        "bibcode": paper["bibcode"],
        "title": paper["title"],
        "authors": len(json.loads(paper["authors_json"])),
        "abstract": bool(str(paper["abstract"] or "").strip()),
        "year": paper["year"],
        "versions_reindexed": versions_reindexed,
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
    identifier: str | None = None,
) -> sqlite3.Row | None:
    parameters: list[Any] = [paper_id]
    hash_clause = ""
    if artifact_hash:
        hash_clause = (
            "AND (v.sha256 = ? OR v.text_sha256 = ? OR v.content_sha256 = ? "
            "OR EXISTS (SELECT 1 FROM artifacts a WHERE a.version_id = v.id AND (a.sha256 = ? OR a.text_sha256 = ?)))"
        )
        parameters.extend([artifact_hash] * 5)
    arxiv_id = fulltext.arxiv_id_from_value(identifier or "")
    if arxiv_id and re.search(r"v\d+$", arxiv_id):
        hash_clause += " AND EXISTS (SELECT 1 FROM version_labels vl WHERE vl.version_id = v.id AND vl.arxiv_id = ?)"
        parameters.append(arxiv_id.casefold())
    return connection.execute(
        f"""
        SELECT v.*, d.id AS digest_id, d.digest_json, d.reading_status,
               d.updated_at AS digest_updated_at
        FROM versions v
        LEFT JOIN digests d ON d.version_id = v.id
        WHERE v.paper_id = ? {hash_clause}
        ORDER BY
            CASE v.version_kind
                WHEN 'published' THEN 0
                WHEN 'accepted' THEN 1
                WHEN 'preprint' THEN 2
                WHEN 'scan' THEN 3
                ELSE 4
            END,
            COALESCE((SELECT MAX(CAST(substr(vl.arxiv_id, length(rtrim(vl.arxiv_id, '0123456789')) + 1) AS INTEGER))
                      FROM version_labels vl WHERE vl.version_id = v.id), 0) DESC,
            v.retrieved_at DESC,
            v.id DESC
        LIMIT 1
        """,
        parameters,
    ).fetchone()


TOPIC_VALUE_FIELDS = ("name", "symbol", "model", "condition", "dataset", "method")


def text_covers(haystack: str, topic: str) -> bool:
    needle = topic.strip().casefold()
    if not needle:
        return False
    haystack = haystack.casefold()
    return needle in haystack or all(token in haystack for token in needle.split())


def topic_match(facet: Mapping[str, Any], topic: str) -> bool:
    """Whether a facet covers a topic through its text, findings, quotes, or values."""
    haystack = "\n".join(
        [
            str(facet.get("key", "")),
            str(facet.get("label", "")),
            str(facet.get("summary", "")),
            *[str(value) for value in facet.get("aliases", [])],
            *[str(value) for value in facet.get("keywords", [])],
            *[
                str(part)
                for finding in facet.get("findings", [])
                for part in (
                    finding.get("statement", ""),
                    finding.get("quote", ""),
                    *finding.get("keywords", []),
                    *[
                        value.get(field, "")
                        for value in finding.get("values", [])
                        for field in TOPIC_VALUE_FIELDS
                    ],
                )
            ],
        ]
    )
    return text_covers(haystack, topic)


def digest_context_match(digest: Mapping[str, Any], topic: str) -> bool:
    """Whether a topic names the paper's own objects, keywords, data, or methods."""
    haystack = "\n".join(
        [
            *[str(value) for value in digest.get("keywords", [])],
            *[
                str(part)
                for entity in digest.get("entities", [])
                for part in (entity.get("name", ""), *entity.get("aliases", []))
            ],
            *[
                str(record.get("name", ""))
                for field in ("datasets", "methods")
                for record in digest.get(field, [])
            ],
        ]
    )
    return text_covers(haystack, topic)


def article_open_gate(reuse_status: str) -> dict[str, Any]:
    if reuse_status == "reusable":
        return {
            "open_gate_action": "reuse_complete_record",
            "complete_ingest_required": False,
        }
    if reuse_status == "targeted_reading":
        return {
            "open_gate_action": "targeted_merge",
            "complete_ingest_required": False,
        }
    return {
        "open_gate_action": "complete_ingest",
        "complete_ingest_required": True,
    }


def reuse_assessment(
    version: sqlite3.Row | None,
    topics: Sequence[str],
    artifact_hash: str | None,
) -> dict[str, Any]:
    if version is None:
        status = "version_changed" if artifact_hash else "needs_reading"
        return {
            "reuse_status": status,
            "matched_topics": [],
            "missing_topics": list(topics),
            **article_open_gate(status),
        }
    if version["digest_id"] is None:
        return {
            "reuse_status": "needs_reading",
            "matched_topics": [],
            "missing_topics": list(topics),
            **article_open_gate("needs_reading"),
        }
    try:
        digest = validate_digest(json.loads(version["digest_json"]))
        artifact = Path(version["artifact_path"])
        if (
            not artifact.is_file()
            or fulltext.sha256_file(artifact) != version["sha256"]
        ):
            raise LiteratureError("Stored article artifact is missing or has changed.")
        if version["status"] == "needs_visual_reading":
            manifest = json.loads(
                Path(version["manifest_path"]).read_text(encoding="utf-8")
            )
            validate_visual_coverage(manifest.get("selected") or {}, digest)
        if version["status"] == "fulltext":
            text_path = Path(version["text_path"] or "")
            if (
                not text_path.is_file()
                or fulltext.sha256_file(text_path) != version["text_sha256"]
            ):
                raise LiteratureError("Stored article text is missing or has changed.")
    except (LiteratureError, json.JSONDecodeError, OSError) as exc:
        return {
            "reuse_status": "needs_reading",
            "reason": str(exc),
            "matched_topics": [],
            "missing_topics": list(topics),
            **article_open_gate("needs_reading"),
        }
    matched: list[str] = []
    missing: list[str] = []
    for topic in topics:
        if any(
            topic_match(facet, topic) for facet in digest["facets"]
        ) or digest_context_match(digest, topic):
            matched.append(topic)
        else:
            missing.append(topic)
    reading_status = version["reading_status"]
    if reading_status == "targeted":
        status = "needs_reading"
    elif missing:
        status = "targeted_reading"
    else:
        status = "reusable"
    return {
        "reuse_status": status,
        "matched_topics": matched,
        "missing_topics": missing,
        "reading_status": reading_status,
        **article_open_gate(status),
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
            **article_open_gate("not_found"),
        }
    version = preferred_version(connection, int(paper["id"]), artifact_hash, identifier)
    assessment = reuse_assessment(version, topics, artifact_hash)
    if version is None and re.search(
        r"v\d+$", fulltext.arxiv_id_from_value(identifier) or ""
    ):
        assessment["reuse_status"] = "version_changed"
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
        "brief": library_catalog.brief_value(
            library_catalog.latest_brief(connection, int(paper["id"]))
        ),
        **library_catalog.paper_organization(connection, int(paper["id"])),
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
            "manifest_path": version["manifest_path"],
            "retrieved_at": version["retrieved_at"],
        }
        if version["digest_id"] and "reason" not in assessment:
            digest = json.loads(version["digest_json"])
            result["facet_labels"] = [
                {
                    "key": facet["key"],
                    "label": facet["label"],
                    "findings": len(facet["findings"]),
                }
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
        "reading_status": digest_row["reading_status"],
        "updated_at": digest_row["updated_at"],
        "digest": digest,
    }


def show_paper(
    connection: sqlite3.Connection,
    identifier: str,
    *,
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
        digest_row = connection.execute(
            "SELECT * FROM digests WHERE version_id = ?", (version["id"],)
        ).fetchone()
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
            "digest": digest_details(digest_row) if digest_row else None,
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
        "brief": library_catalog.brief_value(
            library_catalog.latest_brief(connection, int(paper["id"]))
        ),
        "citation": library_catalog.citation_for_paper(connection, int(paper["id"])),
        **library_catalog.paper_organization(connection, int(paper["id"])),
    }


SECTION_PREFIX_PATTERN = re.compile(
    r"^(?:(?:sections?|sects?|secs?)(?![a-z])\.?|§)\s*", re.IGNORECASE
)
HEADING_NUMBER_PATTERN = re.compile(
    r"^(?:§\s*)?((?:appendix|supplement)\s+[a-z0-9]+|[a-z]?\d+(?:\.\d+)*"
    r"|[a-z](?:\.\d+)+|[ivxlc]+(?:\.\d+)*)[.):]?(?=\s|$)",
    re.IGNORECASE,
)
LOCATOR_LABEL_PATTERNS = {
    "table": r"tab(?:le)?\.?",
    "figure": r"fig(?:ure)?s?\.?",
    "equation": r"eq(?:uation)?s?\.?",
}
LOCATOR_PART_PATTERN = re.compile(r"\s*(?:[;,]|\band\b)\s*", re.IGNORECASE)
LOCATOR_RANGE_PATTERN = re.compile(
    r"^((?:§\s*)?(?:[a-z]?\d+(?:\.\d+)*|[ivxlc]+))\s*[-\u2013\u2014]\s*\S+$",
    re.IGNORECASE,
)
SECTION_TEXT_LABEL_PATTERN = re.compile(
    r"\b(tab(?:le)?|fig(?:ure)?s?|eq(?:uation)?s?)\.?\s*([A-Z]?\d+[a-z]?)",
    re.IGNORECASE,
)


def text_skeleton(text: str) -> tuple[str, list[int]]:
    """Casefolded letters and digits of ``text`` with their source offsets.

    Matching on this skeleton tolerates the whitespace, hyphenation, ligature,
    and punctuation differences between a copied quote and extracted text.
    """
    characters: list[str] = []
    offsets: list[int] = []
    for index, character in enumerate(text):
        if character.isascii():
            if character.isalnum():
                characters.append(character.lower())
                offsets.append(index)
            continue
        if character == "×":
            character = "x"
        for piece in unicodedata.normalize("NFKC", character).casefold():
            if piece.isalnum():
                characters.append(piece)
                offsets.append(index)
    return "".join(characters), offsets


def locate_quote(
    skeleton: str,
    offsets: Sequence[int],
    quote: str,
    *,
    within: tuple[int, int] | None = None,
) -> tuple[int, int, bool] | None:
    """Find a quote's source span, preferring the given section span."""
    needle = text_skeleton(quote)[0]
    if len(needle) < MIN_QUOTE_ANCHOR_CHARS:
        return None
    pieces = [(needle, True)]
    if len(needle) >= 40:
        half = len(needle) // 2
        pieces.extend([(needle[:half], False), (needle[half:], False)])
    for piece, exact in pieces:
        position = -1
        if within:
            position = skeleton.find(
                piece, bisect_left(offsets, within[0]), bisect_left(offsets, within[1])
            )
        if position < 0:
            position = skeleton.find(piece)
        if position >= 0:
            return offsets[position], offsets[position + len(piece) - 1] + 1, exact
    return None


def heading_number(heading: str) -> str | None:
    match = HEADING_NUMBER_PATTERN.match(" ".join(heading.split()))
    return match.group(1).casefold() if match else None


def match_section(
    sections: Sequence[Mapping[str, Any]], label: str | None
) -> Mapping[str, Any] | None:
    """Resolve a locator or user label such as ``2.3``, ``Sec. 4``, or a heading.

    Compound labels such as ``2; Table 1`` or ``III-IV`` resolve through their
    first part that names a section.
    """
    found = match_section_label(sections, label)
    if found is not None or not label:
        return found
    for part in LOCATOR_PART_PATTERN.split(label):
        part = SECTION_PREFIX_PATTERN.sub("", part.strip())
        ranged = LOCATOR_RANGE_PATTERN.match(part)
        for candidate in (part, ranged.group(1) if ranged else ""):
            if candidate and candidate != label:
                found = match_section_label(sections, candidate)
                if found is not None:
                    return found
    return None


def match_section_label(
    sections: Sequence[Mapping[str, Any]], label: str | None
) -> Mapping[str, Any] | None:
    key = normalized_heading(label or "")
    if not key or SECTION_TEXT_LABEL_PATTERN.fullmatch(key):
        return None
    for section in sections:
        if normalized_heading(section["heading"]) == key:
            return section
    bare = SECTION_PREFIX_PATTERN.sub("", key).strip()
    number = heading_number(bare)
    if number and HEADING_NUMBER_PATTERN.fullmatch(bare):
        numbered = [
            (heading_number(section["heading"]) or "", section) for section in sections
        ]
        for candidate, section in numbered:
            if candidate == number:
                return section
        for candidate, section in numbered:
            if candidate.startswith(number + "."):
                return section
        return None
    for section in sections:
        if bare and bare in normalized_heading(section["heading"]):
            return section
    for section in sections:
        title = HEADING_NUMBER_PATTERN.sub("", normalized_heading(section["heading"]))
        title = title.strip(" .:)")
        if len(title) >= 4 and title in bare:
            return section
    return None


def reading_headings(digest: Mapping[str, Any] | None) -> list[str]:
    """Section headings a digest records as read, in reading order."""
    reading = digest.get("reading") if isinstance(digest, Mapping) else None
    entries = reading.get("sections") if isinstance(reading, Mapping) else None
    headings: list[str] = []
    for entry in entries if isinstance(entries, list) else []:
        heading = entry.get("heading") if isinstance(entry, Mapping) else entry
        if isinstance(heading, str) and heading.strip():
            headings.append(heading)
    return headings


def article_sections(
    text: str,
    manifest: Mapping[str, Any] | None = None,
    digest: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Section spans of stored text, from the manifest outline or inferred headings.

    The digest's read sections fill headings that the outline missed.
    """
    return fulltext.article_outline(
        text, manifest, reading_headings=reading_headings(digest)
    )


def section_at(
    sections: Sequence[Mapping[str, Any]], offset: int
) -> Mapping[str, Any] | None:
    for section in sections:
        if section["start"] <= offset < section["end"]:
            return section
    return sections[-1] if sections else None


def quote_anchors(
    digest: Mapping[str, Any],
    text: str,
    sections: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check that each finding's quote occurs in the article text."""
    sections = sections if sections is not None else article_sections(text, None, digest)
    skeleton, offsets = text_skeleton(text)
    located = 0
    quoted = 0
    unlocated: list[str] = []
    for identifier, _facet, finding in iter_findings(digest):
        if not finding.get("quote"):
            continue
        quoted += 1
        section = match_section(sections, finding.get("locator", {}).get("section"))
        span = (section["start"], section["end"]) if section else None
        if locate_quote(skeleton, offsets, finding["quote"], within=span):
            located += 1
        else:
            unlocated.append(identifier)
    return {"quoted": quoted, "located": located, "unlocated": unlocated}


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def bounded_window(
    text: str, start: int, end: int, floor: int, ceiling: int, max_chars: int
) -> tuple[int, int, bool]:
    """Clip ``[floor, ceiling)`` to at most ``max_chars`` around ``[start, end)``."""
    if not max_chars or ceiling - floor <= max_chars:
        return floor, ceiling, False
    span = min(end - start, max_chars)
    left = max(floor, min(start - (max_chars - span) // 2, ceiling - max_chars))
    right = min(ceiling, left + max_chars)
    if left > floor:
        boundary = text.find(" ", left, start) if start > left else -1
        left = boundary + 1 if boundary >= 0 else left
    if right < ceiling:
        boundary = text.rfind(" ", max(end, left), right)
        right = boundary if boundary > left else right
    return left, right, True


PARAGRAPH_END_PATTERN = re.compile(r"[.!?:]['\")\]]*$")
PARAGRAPH_CONTINUATION_PATTERN = re.compile(r"^[a-z$\\,.;:)\]\u2013\u2014-]")


def paragraph_blocks(text: str, floor: int, ceiling: int) -> list[tuple[int, int]]:
    """Logical paragraphs of ``text[floor:ceiling]``.

    Extracted HTML often isolates inline math between blank lines, so a block
    joins the next one unless it ends a sentence and the next starts a new one.
    """
    blocks: list[tuple[int, int]] = []
    for match in re.finditer(r"(?:[^\n]|\n(?!\n))+", text[floor:ceiling]):
        chunk = match.group()
        if not chunk.strip():
            continue
        start = floor + match.start() + len(chunk) - len(chunk.lstrip())
        end = floor + match.end() - (len(chunk) - len(chunk.rstrip()))
        if blocks:
            previous = text[blocks[-1][0] : blocks[-1][1]].strip()
            following = text[start:end].lstrip()
            last_line = previous.rsplit("\n", 1)[-1].strip()
            heading = (
                len(last_line) <= 150
                and re.match(r"[A-Z0-9§]", last_line)
                and not PARAGRAPH_END_PATTERN.search(last_line)
                and re.match(r"[A-Z]", following)
            )
            if not heading and (
                not PARAGRAPH_END_PATTERN.search(previous)
                or PARAGRAPH_CONTINUATION_PATTERN.match(following)
            ):
                blocks[-1] = (blocks[-1][0], end)
                continue
        blocks.append((start, end))
    return blocks


def paragraph_span(
    text: str, start: int, end: int, floor: int, ceiling: int, context: int
) -> tuple[int, int]:
    """The logical paragraph holding ``[start, end)`` plus ``context`` neighbors."""
    blocks = paragraph_blocks(text, floor, ceiling)
    if not blocks:
        return floor, ceiling
    index = next(
        (position for position, (_left, right) in enumerate(blocks) if start < right),
        len(blocks) - 1,
    )
    last = index
    while last + 1 < len(blocks) and blocks[last][1] < end:
        last += 1
    first = max(index - context, 0)
    last = min(last + context, len(blocks) - 1)
    return blocks[first][0], blocks[last][1]


def passage_record(
    text: str,
    sections: Sequence[Mapping[str, Any]],
    left: int,
    right: int,
    *,
    match: str,
    truncated: bool,
) -> dict[str, Any]:
    section = section_at(sections, left)
    return {
        "section": section["heading"] if section else None,
        "match": match,
        "lines": [line_number(text, left), line_number(text, max(right - 1, left))],
        "truncated": truncated,
        "text": text[left:right].strip(),
    }


def paragraph_chunks(text: str, max_chars: int) -> list[tuple[int, int]]:
    """Logical paragraphs; overlong ones are cut at line breaks."""
    chunks: list[tuple[int, int]] = []
    limit = max(max_chars, 1500) if max_chars else 0
    for start, end in paragraph_blocks(text, 0, len(text)):
        while limit and end - start > limit:
            cut = text.rfind("\n", start, start + limit)
            cut = cut if cut > start else start + limit
            chunks.append((start, cut))
            start = cut
        chunks.append((start, end))
    return chunks


def first_term_offset(chunk: str, term: str) -> int:
    folded = chunk.casefold()
    if re.match(r"[0-9a-z]", term):
        found = re.search(r"(?<![0-9a-z])" + re.escape(term), folded)
        return found.start() if found else 0
    position = folded.find(term)
    return max(position, 0)


def label_terms(kind: str, label: str) -> re.Pattern[str]:
    number = re.escape(re.sub(r"^\D+", "", label.strip()) or label.strip())
    return re.compile(
        rf"(?<![0-9A-Za-z]){LOCATOR_LABEL_PATTERNS[kind]}\s*{number}(?![0-9])",
        re.IGNORECASE,
    )


def article_passages(
    connection: sqlite3.Connection,
    identifier: str,
    *,
    findings: Sequence[str] = (),
    sections: Sequence[str] = (),
    terms: Sequence[str] = (),
    outline: bool = False,
    artifact_hash: str | None = None,
    context: int = 0,
    max_chars: int = 3000,
    limit: int = 5,
) -> dict[str, Any]:
    """Return bounded passages of a stored article instead of its whole text."""
    paper = find_paper_by_identifier(connection, identifier)
    if paper is None:
        raise LiteratureError(f"Paper is not in the literature database: {identifier}", 2)
    paper_id = int(paper["id"])
    version = preferred_version(connection, paper_id, artifact_hash, identifier)
    if version is None:
        raise LiteratureError(f"No stored article version matches {identifier}.", 2)
    digest = json.loads(version["digest_json"]) if version["digest_json"] else None
    text = ""
    text_path = Path(version["text_path"]) if version["text_path"] else None
    if text_path is not None:
        if (
            not text_path.is_file()
            or fulltext.sha256_file(text_path) != version["text_sha256"]
        ):
            raise LiteratureError(
                "Stored article text is missing or has changed; restore a backup "
                "or retrieve the exact version again.",
                2,
            )
        text = text_path.read_text(encoding="utf-8", errors="replace")
    manifest: dict[str, Any] = {}
    try:
        manifest = json.loads(Path(version["manifest_path"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    spans = article_sections(text, manifest, digest) if text else []
    result: dict[str, Any] = {
        "paper": {
            "canonical_key": paper["canonical_key"],
            "bibcode": paper["bibcode"],
            "citekey": library_catalog.citation_for_paper(connection, paper_id)["citekey"],
            "title": paper["title"],
        },
        "version": {
            "id": version["id"],
            "version_kind": version["version_kind"],
            "format": version["format"],
            "reading_status": version["reading_status"],
            "text_path": version["text_path"],
            "artifact_path": version["artifact_path"],
        },
        "passages": [],
        "unresolved": [],
    }
    if not (findings or sections or terms):
        outline = True
    if outline:
        if spans:
            gists: dict[int, str] = {}
            for entry in digest["reading"]["sections"] if digest else []:
                span = match_section(spans, entry["heading"])
                if span is not None and entry.get("gist"):
                    gists.setdefault(span["start"], entry["gist"])
            result["outline"] = []
            for span in spans:
                entry = {
                    "heading": span["heading"],
                    "line": span["line"],
                    "words": fulltext.count_words(text[span["start"] : span["end"]]),
                }
                if span["start"] in gists:
                    entry["gist"] = gists[span["start"]]
                result["outline"].append(entry)
        else:
            result["outline"] = digest["reading"]["sections"] if digest else []
    if not text and (findings or sections or terms):
        result["unresolved"].append(
            {
                "reason": "This version has no extracted text; inspect the artifact "
                "at the recorded pages.",
                "artifact_path": version["artifact_path"],
            }
        )
        if digest:
            for requested in findings:
                for found_id, _facet, finding in iter_findings(digest):
                    if found_id == requested:
                        result["unresolved"][-1].setdefault("locators", {})[
                            requested
                        ] = finding["locator"]
        return result
    skeleton: tuple[str, list[int]] | None = None
    by_id = {found_id: finding for found_id, _facet, finding in iter_findings(digest or {})}
    for requested in findings:
        finding = by_id.get(requested)
        if finding is None:
            result["unresolved"].append(
                {
                    "finding": requested,
                    "reason": "No finding has this id; findings and parameters rows list each finding_id.",
                }
            )
            continue
        summary = {
            "finding_id": requested,
            "statement": finding["statement"],
            "kind": finding["kind"],
            "locator": finding["locator"],
        }
        locator = finding["locator"]
        section = match_section(spans, locator.get("section"))
        hit = None
        if finding.get("quote"):
            if skeleton is None:
                skeleton = text_skeleton(text)
            hit = locate_quote(
                *skeleton,
                finding["quote"],
                within=(section["start"], section["end"]) if section else None,
            )
        if hit:
            start, end, exact = hit
            holder = section_at(spans, start)
            floor, ceiling = (holder["start"], holder["end"]) if holder else (0, len(text))
            left, right = paragraph_span(text, start, end, floor, ceiling, context)
            left, right, truncated = bounded_window(text, start, end, left, right, max_chars)
            result["passages"].append(
                {
                    **summary,
                    **passage_record(
                        text,
                        spans,
                        left,
                        right,
                        match="quote" if exact else "partial-quote",
                        truncated=truncated,
                    ),
                }
            )
            continue
        labelled = None
        labels = [
            (kind, str(locator[kind]))
            for kind in ("table", "figure", "equation")
            if locator.get(kind)
        ]
        for word, number in SECTION_TEXT_LABEL_PATTERN.findall(locator.get("section", "")):
            kind = "table" if word.lower().startswith("tab") else (
                "figure" if word.lower().startswith("fig") else "equation"
            )
            labels.append((kind, number))
        for kind, value in labels:
            if value:
                pattern = label_terms(kind, value)
                floor, ceiling = (section["start"], section["end"]) if section else (0, len(text))
                found = pattern.search(text, floor, ceiling) or pattern.search(text)
                if found:
                    labelled = (found.start(), found.end(), kind)
                    break
        if labelled:
            start, end, kind = labelled
            holder = section_at(spans, start)
            floor, ceiling = (holder["start"], holder["end"]) if holder else (0, len(text))
            left, right = paragraph_span(text, start, end, floor, ceiling, context)
            left, right, truncated = bounded_window(text, start, end, left, right, max_chars)
            result["passages"].append(
                {
                    **summary,
                    **passage_record(
                        text, spans, left, right, match=kind, truncated=truncated
                    ),
                }
            )
        elif section:
            left, right, truncated = bounded_window(
                text, section["start"], section["start"], section["start"], section["end"], max_chars
            )
            result["passages"].append(
                {
                    **summary,
                    **passage_record(
                        text, spans, left, right, match="section", truncated=truncated
                    ),
                }
            )
        else:
            result["unresolved"].append(
                {
                    **summary,
                    "reason": "Neither the quote nor the locator resolves in the stored text; "
                    "search it with --grep or read the artifact at the locator.",
                }
            )
    for label in sections:
        section = match_section(spans, label)
        if section is None:
            result["unresolved"].append(
                {
                    "section": label,
                    "reason": "No stored section matches; run passage --outline for headings.",
                }
            )
            continue
        left, right, truncated = bounded_window(
            text, section["start"], section["start"], section["start"], section["end"], max_chars
        )
        result["passages"].append(
            {
                "request": {"section": label},
                **passage_record(text, spans, left, right, match="section", truncated=truncated),
            }
        )
        if truncated:
            result["passages"][-1]["section_lines"] = [
                section["line"],
                section["line"] + section["lines"] - 1,
            ]
    if terms:
        folded = [term.casefold() for term in terms if term.strip()]
        matchers = [term_matcher(term) for term in folded]
        total = 0
        for start, end in paragraph_chunks(text, max_chars):
            chunk = text[start:end]
            if not all(matcher(chunk) for matcher in matchers):
                continue
            total += 1
            if total > limit:
                continue
            anchor = start + first_term_offset(chunk, folded[0])
            left, right, truncated = bounded_window(
                text, anchor, anchor + len(folded[0]), start, end, max_chars
            )
            result["passages"].append(
                {
                    "request": {"grep": list(terms)},
                    **passage_record(text, spans, left, right, match="terms", truncated=truncated),
                }
            )
        result["term_matches"] = total
        if total > limit:
            result["truncated"] = True
    return result


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
    row = connection.execute(
        "SELECT digest_json FROM digests WHERE id = ?", (digest_id,)
    ).fetchone()
    if row is None:
        return []
    return [
        {"key": facet["key"], "label": facet["label"], "summary": facet["summary"]}
        for facet in json.loads(row["digest_json"])["facets"]
    ]


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
                *facet.get("aliases", []),
                facet["summary"],
                *facet.get("keywords", []),
                *facet.get("methods", []),
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
                        "values": finding.get("values", []),
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
    if mode == "fts" and not fts5:
        raise LiteratureError(
            "FTS5 is unavailable. Use --mode terms or --mode phrase.", 2
        )
    if year_from is not None and year_to is not None and year_from > year_to:
        raise LiteratureError("year-from must be at most year-to.", 2)
    parameters: list[Any] = []
    year_clauses: list[str] = []
    if year_from is not None:
        year_clauses.append("p.year >= ?")
        parameters.append(year_from)
    if year_to is not None:
        year_clauses.append("p.year <= ?")
        parameters.append(year_to)
    year_sql = "" if not year_clauses else " AND " + " AND ".join(year_clauses)
    use_fts = fts5 and (mode == "fts" or not contains_cjk(query))
    if use_fts:
        expression = build_search_expression(query, mode, scope)
        rows = connection.execute(
            f"""
            SELECT p.id AS paper_id, p.bibcode, p.title, p.year, p.pub,
                   v.id AS version_id, v.version_kind, v.sha256,
                   v.content_sha256,
                   d.id AS digest_id, d.reading_status,
                   bm25(search_fts) AS score,
                   snippet(search_fts, -1, '[', ']', ' … ', 28) AS snippet
            FROM search_fts
            JOIN papers p ON p.id = CAST(search_fts.paper_id AS INTEGER)
            JOIN versions v ON v.id = CAST(search_fts.version_id AS INTEGER)
            JOIN digests d ON d.id = CAST(search_fts.digest_id AS INTEGER)
            WHERE search_fts MATCH ? {year_sql}
            ORDER BY score, p.id, v.id
            """,
            (expression, *parameters),
        )
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
        connection.create_function(
            "unicode_casefold", 1, lambda text: str(text).casefold()
        )
        term_clauses = [
            f"instr(unicode_casefold({combined}), ?) > 0" for _term in terms
        ]
        term_parameters = [term.casefold() for term in terms]
        rows = connection.execute(
            f"""
            SELECT p.id AS paper_id, p.bibcode, p.title, p.year, p.pub,
                    v.id AS version_id, v.version_kind, v.sha256,
                    v.content_sha256,
                   d.id AS digest_id, d.reading_status,
                   0.0 AS score, substr(sd.overview, 1, 300) AS snippet
            FROM search_documents sd
            JOIN papers p ON p.id = sd.paper_id
            JOIN versions v ON v.id = sd.version_id
            JOIN digests d ON d.id = sd.digest_id
            WHERE {" AND ".join(term_clauses)} {year_sql}
            ORDER BY p.id, v.id
            """,
            (*term_parameters, *parameters),
        )
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
    for item in library_catalog.brief_search_results(
        connection,
        query,
        scope=scope,
        mode=mode,
        topics=topics,
        year_from=year_from,
        year_to=year_to,
    ):
        if len(results) >= limit:
            break
        if item["paper_id"] not in seen_papers:
            results.append(item)
            seen_papers.add(item["paper_id"])
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
    if year_from is not None and year_to is not None and year_from > year_to:
        raise LiteratureError("year-from must be at most year-to.", 2)
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
            if not topics:
                brief = library_catalog.latest_brief(connection, paper_id)
                results.append(
                    {
                        **dict(row),
                        "version_kind": None,
                        "reading_status": brief["evidence_level"]
                        if brief
                        else "metadata",
                        "summary_status": "complete"
                        if brief and brief["summary"]
                        else "pending",
                        "facets": [],
                        "matched_topics": [],
                    }
                )
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
                "matched_topics": matched,
                "facets": facets_for_digest(connection, int(version["digest_id"])),
            }
        )
        if len(results) >= limit:
            break
    return {"count": len(results), "topics": list(topics), "results": results}


EVIDENCE_UNITS = ("findings", "values")
EVIDENCE_CSV_COLUMNS = {
    "findings": (
        "bibcode",
        "citekey",
        "year",
        "title",
        "facet",
        "finding_id",
        "kind",
        "confidence",
        "statement",
        "locator",
        "quote",
        "cited_from",
        "compared_with",
        "values",
        "version_kind",
        "reading_status",
    ),
    "values": (
        "bibcode",
        "citekey",
        "year",
        "title",
        "facet",
        "finding_id",
        "statement",
        "kind",
        "confidence",
        "locator",
        *PARAMETER_FIELDS,
        "version_kind",
        "reading_status",
    ),
}


def locator_text(locator: Mapping[str, Any]) -> str:
    return "; ".join(
        f"{key} {locator[key]}" for key in LOCATOR_FIELDS if locator.get(key)
    )


def value_text(value: Mapping[str, Any]) -> str:
    label = str(value.get("name", ""))
    if value.get("symbol"):
        label += f" ({value['symbol']})"
    uncertainty = str(value.get("uncertainty") or "")
    if uncertainty and uncertainty[0] not in "+-±":
        uncertainty = f"± {uncertainty}"
    amount = " ".join(
        str(part) for part in (value.get("value"), uncertainty) if part not in (None, "")
    )
    if value.get("range"):
        low, high = value["range"]
        amount = f"{amount} [{low}, {high}]".strip()
    if value.get("unit"):
        amount = f"{amount} {value['unit']}".strip()
    context = [
        str(value[field])
        for field in ("status", "qualifier", "condition")
        if value.get(field)
    ]
    return f"{label} = {amount}" + (f" [{', '.join(context)}]" if context else "")


def term_matcher(term: str):
    """Match Latin terms at a word start and other scripts as substrings."""
    if re.match(r"[0-9a-z]", term):
        pattern = re.compile(r"(?<![0-9a-z])" + re.escape(term))
        return lambda text: bool(pattern.search(text.casefold()))
    return lambda text: term in text.casefold()


def digest_names_entity(digest: Mapping[str, Any], needle: str) -> bool:
    names = [
        name
        for entity in digest.get("entities", [])
        for name in (entity.get("name", ""), *entity.get("aliases", []))
    ]
    names.extend(
        identifier
        for dataset in digest.get("datasets", [])
        for identifier in dataset.get("identifiers", [])
    )
    return any(needle in " ".join(str(name).split()).casefold() for name in names)


def evidence_table(
    connection: sqlite3.Connection,
    unit: str,
    *,
    query: str = "",
    identifiers: Sequence[str] = (),
    entity: str | None = None,
    kinds: Sequence[str] = (),
    statuses: Sequence[str] = (),
    collection: str | None = None,
    role: str | None = None,
    tag: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Flatten complete digests into citable finding or value rows with locators."""
    if unit not in EVIDENCE_UNITS:
        raise LiteratureError(f"Unknown evidence unit: {unit}.", 2)
    if year_from is not None and year_to is not None and year_from > year_to:
        raise LiteratureError("year-from must be at most year-to.", 2)
    terms = [term.casefold() for term in query_terms(query, "terms")]
    entity_needle = " ".join((entity or "").split()).casefold()
    missing: list[str] = []
    candidates: list[tuple[sqlite3.Row, str | None]] = []
    if identifiers:
        for identifier in identifiers:
            paper = find_paper_by_identifier(connection, identifier)
            if paper is None:
                missing.append(identifier)
            else:
                candidates.append((paper, identifier))
    else:
        candidates = [
            (paper, None)
            for paper in connection.execute(
                "SELECT * FROM papers ORDER BY year DESC, title"
            )
        ]
    matchers = [term_matcher(term) for term in terms]
    matched: list[tuple[int, int, dict[str, Any]]] = []
    without_digest: list[str] = []
    papers_scanned = 0
    seen_papers: set[int] = set()
    for paper, identifier in candidates:
        paper_id = int(paper["id"])
        if paper_id in seen_papers:
            continue
        seen_papers.add(paper_id)
        year = paper["year"]
        if year_from is not None and (year is None or year < year_from):
            continue
        if year_to is not None and (year is None or year > year_to):
            continue
        if not library_catalog.matches_organization(
            connection, paper_id, collection=collection, role=role, tag=tag
        ):
            continue
        version = preferred_version(connection, paper_id, identifier=identifier)
        if version is None or version["digest_id"] is None:
            if identifiers:
                without_digest.append(identifier or paper["bibcode"] or str(paper_id))
            continue
        digest = json.loads(version["digest_json"])
        if entity_needle and not digest_names_entity(digest, entity_needle):
            continue
        papers_scanned += 1
        for facet in digest["facets"]:
            facet_text = "\n".join(
                [
                    facet["key"],
                    facet["label"],
                    *facet.get("aliases", []),
                    *facet.get("keywords", []),
                ]
            )
            for finding_index, finding in enumerate(facet["findings"]):
                if kinds and finding["kind"] not in kinds:
                    continue
                values = finding.get("values", [])
                finding_text = "\n".join(
                    [
                        finding["statement"],
                        *finding.get("keywords", []),
                        finding.get("cited_from") or "",
                        *finding.get("compared_with", []),
                    ]
                )
                base = {
                    "paper_id": paper_id,
                    "bibcode": paper["bibcode"],
                    "citekey": None,
                    "title": paper["title"],
                    "year": year,
                    "version_id": int(version["id"]),
                    "version_kind": version["version_kind"],
                    "reading_status": version["reading_status"],
                    "facet": facet["key"],
                    "facet_label": facet["label"],
                    "finding_id": finding_id(facet["key"], finding_index),
                    "statement": finding["statement"],
                    "kind": finding["kind"],
                    "confidence": finding["confidence"],
                    "locator": finding["locator"],
                    "cited_from": finding.get("cited_from"),
                    "compared_with": finding.get("compared_with", []),
                }
                if unit == "findings":
                    if statuses and not any(
                        value.get("status") in statuses for value in values
                    ):
                        continue
                    own_text = "\n".join([finding_text, join_record_text(values)])
                    candidates_for_finding = [
                        (
                            own_text,
                            {
                                **base,
                                "quote": finding.get("quote"),
                                "keywords": finding.get("keywords", []),
                                "values": values,
                            },
                        )
                    ]
                else:
                    candidates_for_finding = []
                    for value in values:
                        if statuses and value.get("status") not in statuses:
                            continue
                        own_text = "\n".join(
                            str(value[field])
                            for field in PARAMETER_FIELDS
                            if field not in {"value", "range"}
                            and value.get(field) is not None
                        )
                        candidates_for_finding.append(
                            (
                                own_text,
                                {
                                    **base,
                                    **{
                                        field: value.get(field)
                                        for field in PARAMETER_FIELDS
                                    },
                                    "cited_from": value.get("cited_from")
                                    or finding.get("cited_from"),
                                    "_context": "\n".join(
                                        [str(value.get("value")), finding_text]
                                    ),
                                },
                            )
                        )
                for own_text, row in candidates_for_finding:
                    context = "\n".join(
                        [own_text, row.pop("_context", ""), facet_text]
                    )
                    if not all(matcher(context) for matcher in matchers):
                        continue
                    rank = 0 if all(matcher(own_text) for matcher in matchers) else 1
                    matched.append((rank, len(matched), row))
    matched.sort(key=lambda item: (item[0], item[1]))
    truncated = len(matched) > limit
    own_label = "finding" if unit == "findings" else "value"
    rows = []
    citekeys: dict[int, str] = {}
    for rank, _order, row in matched[:limit]:
        row["match"] = "all" if not terms else "context" if rank else own_label
        if row["paper_id"] not in citekeys:
            citekeys[row["paper_id"]] = library_catalog.citation_for_paper(
                connection, row["paper_id"]
            )["citekey"]
        row["citekey"] = citekeys[row["paper_id"]]
        rows.append(row)
    return {
        "query": query,
        "unit": unit,
        "filters": {
            "papers": list(identifiers),
            "entity": entity,
            "kind": list(kinds),
            "status": list(statuses),
            "collection": collection,
            "role": role,
            "tag": tag,
            "year_from": year_from,
            "year_to": year_to,
        },
        "papers_scanned": papers_scanned,
        "count": len(rows),
        "truncated": truncated,
        "missing": missing,
        "without_complete_digest": without_digest,
        "results": rows,
    }


def evidence_csv(table: Mapping[str, Any]) -> str:
    columns = EVIDENCE_CSV_COLUMNS[table["unit"]]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in table["results"]:
        cells = []
        for column in columns:
            if column == "locator":
                cells.append(locator_text(row["locator"]))
            elif column == "values":
                cells.append("; ".join(value_text(value) for value in row["values"]))
            elif column == "compared_with":
                cells.append("; ".join(row["compared_with"]))
            elif column == "range":
                bounds = row.get("range")
                cells.append(f"[{bounds[0]}, {bounds[1]}]" if bounds else "")
            elif row.get(column) is None:
                cells.append("")
            else:
                cells.append(row[column])
        writer.writerow(cells)
    return buffer.getvalue()


def library_stats(
    connection: sqlite3.Connection, fts5: bool, library_dir: Path
) -> dict[str, Any]:
    available = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    tables = [
        name
        for name in (
            "papers",
            "versions",
            "artifacts",
            "digests",
            "briefs",
            "search_runs",
            "collections",
            "citations",
        )
        if name in available
    ]
    counts = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }
    reading_rows = connection.execute(
        "SELECT reading_status, COUNT(*) AS count FROM digests GROUP BY reading_status"
    ).fetchall()
    reading = {row["reading_status"]: row["count"] for row in reading_rows}
    complete = reading.get("full", 0) + reading.get("visual", 0)
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
        "database_schema_version": int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        ),
        "digest_schema_version": DIGEST_SCHEMA_VERSION,
        "library_dir": str(library_dir),
        "database_path": str(library_dir / "literature.sqlite3"),
        "fts5": fts5,
        "counts": {**counts, "complete_digests": complete},
        "reading_status": reading,
        "objects": {"files": object_files, "bytes": object_bytes},
    }


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def create_library_backup(
    connection: sqlite3.Connection,
    fts5: bool,
    library_dir: Path,
    destination_value: str | None,
) -> dict[str, Any]:
    timestamp = fulltext.utc_now()
    stamp = re.sub(r"[^0-9A-Za-z]", "", timestamp)[:15]
    destination = (
        Path(destination_value).expanduser().resolve()
        if destination_value
        else (library_dir.parent / "backups" / f"literature-{stamp}").resolve()
    )
    if path_is_within(destination, library_dir):
        raise LiteratureError("Backup destination must be outside the live library.", 2)
    if destination.exists():
        raise LiteratureError(f"Backup destination already exists: {destination}", 2)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise LiteratureError(f"Temporary backup path already exists: {temporary}", 2)
    try:
        temporary.mkdir(parents=False)
        backup_database = temporary / "literature.sqlite3"
        target = sqlite3.connect(backup_database)
        try:
            connection.backup(target)
        finally:
            target.close()
        objects_source = library_dir / "objects"
        if objects_source.is_dir():
            shutil.copytree(objects_source, temporary / "objects")
        relocate_object_paths(backup_database, temporary, destination, [library_dir])
        check = sqlite3.connect(backup_database)
        try:
            integrity = [row[0] for row in check.execute("PRAGMA integrity_check")]
        finally:
            check.close()
        if integrity != ["ok"]:
            raise LiteratureError("Backup database failed its integrity check.")
        stats = library_stats(connection, fts5, library_dir)
        fulltext.atomic_write_text(
            temporary / "backup.json",
            pretty_json(
                {
                    "backup_schema_version": 1,
                    "database_schema_version": stats["database_schema_version"],
                    "created_at": timestamp,
                    "source_library": str(library_dir.resolve()),
                    "backup_library": str(destination.resolve()),
                    "database_integrity": integrity,
                    "counts": stats["counts"],
                    "objects": stats["objects"],
                }
            ),
        )
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists() and path_is_within(temporary, destination.parent):
            shutil.rmtree(temporary)
        raise
    return {
        "status": "created",
        "destination": str(destination),
        "created_at": timestamp,
        "counts": stats["counts"],
        "objects": stats["objects"],
    }


def relocate_object_paths(
    database: Path, staged_root: Path, final_root: Path, old_roots: Sequence[Path | str]
) -> None:
    """Rewrite only managed object references in a copied database and manifests."""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    manifests: set[Path] = set()

    def relocated(value: str) -> tuple[Path, Path]:
        path_type = (
            PureWindowsPath
            if re.match(r"^(?:[A-Za-z]:|\\\\)", value)
            else PurePosixPath
        )
        source = path_type(value)
        for root in old_roots:
            original = path_type(str(root))
            if not source.is_absolute() or not original.is_absolute():
                continue
            if source.is_relative_to(original / "objects"):
                relative = Path(*source.relative_to(original).parts)
                staged = staged_root / relative
                if (
                    not path_is_within(staged, staged_root / "objects")
                    or not staged.is_file()
                ):
                    raise LiteratureError(
                        f"Backup object is missing or outside its store: {relative}", 2
                    )
                return staged, final_root / relative
        raise LiteratureError("A stored object path is outside the source library.", 2)

    try:
        with connection:
            for table in ("versions", "artifacts"):
                for row in connection.execute(f"SELECT * FROM {table}").fetchall():
                    changes = {}
                    for column in ("artifact_path", "text_path", "manifest_path"):
                        if row[column]:
                            staged, final = relocated(row[column])
                            changes[column] = str(final.resolve())
                            if column == "manifest_path":
                                manifests.add(staged)
                            expected = (
                                row["sha256"]
                                if column == "artifact_path"
                                else row["text_sha256"]
                                if column == "text_path"
                                else None
                            )
                            if expected and fulltext.sha256_file(staged) != expected:
                                raise LiteratureError(
                                    "Backup object failed hash verification.", 2
                                )
                    connection.execute(
                        f"UPDATE {table} SET "
                        + ", ".join(f"{key} = ?" for key in changes)
                        + " WHERE id = ?",
                        (*changes.values(), row["id"]),
                    )
            for path in manifests:
                payload = json.loads(path.read_text(encoding="utf-8"))
                objects = payload.get("database_object") or {}
                for field in ("artifact_path", "text_path"):
                    if objects.get(field):
                        _staged, final = relocated(objects[field])
                        objects[field] = str(final.resolve())
                payload["database_object"] = objects
                if isinstance(payload.get("selected"), dict):
                    for field in ("artifact_path", "text_path"):
                        payload["selected"][field] = objects.get(field)
                payload["manifest_path"] = str(
                    (final_root / path.relative_to(staged_root)).resolve()
                )
                fulltext.atomic_write_text(path, pretty_json(payload))
    finally:
        connection.close()


def restore_library(backup: Path, destination: Path) -> dict[str, Any]:
    backup, destination = (
        backup.expanduser().resolve(),
        destination.expanduser().resolve(),
    )
    if destination.exists() or path_is_within(destination, backup):
        raise LiteratureError(
            "Restore destination must be a new directory outside the backup.", 2
        )
    metadata = json.loads((backup / "backup.json").read_text(encoding="utf-8"))
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.restore")
    if temporary.exists():
        raise LiteratureError("Temporary restore destination already exists.", 2)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(backup, temporary)
        relocate_object_paths(
            temporary / "literature.sqlite3",
            temporary,
            destination,
            [
                backup,
                metadata.get("backup_library", str(backup)),
                metadata["source_library"],
            ],
        )
        check = sqlite3.connect(temporary / "literature.sqlite3")
        try:
            if [row[0] for row in check.execute("PRAGMA integrity_check")] != ["ok"]:
                raise LiteratureError(
                    "Restored database failed its integrity check.", 2
                )
        finally:
            check.close()
        os.replace(temporary, destination)
    except Exception:
        if temporary.exists() and path_is_within(temporary, destination.parent):
            shutil.rmtree(temporary)
        raise
    return {
        "status": "restored",
        "library_dir": str(destination),
        "database_schema_version": metadata["database_schema_version"],
    }


def audit_library(
    connection: sqlite3.Connection,
    fts5: bool,
    library_dir: Path,
    *,
    verify_hashes: bool,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    information: dict[str, Any] = {}

    integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    quick_check = [row[0] for row in connection.execute("PRAGMA quick_check")]
    foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
    if integrity != ["ok"] or quick_check != ["ok"]:
        errors.append({"kind": "sqlite_integrity", "details": integrity})
    if foreign_keys:
        errors.append({"kind": "foreign_key_violations", "count": len(foreign_keys)})

    relation_checks = {
        "papers_without_versions": """
            SELECT COUNT(*) FROM papers p
            WHERE NOT EXISTS (SELECT 1 FROM versions v WHERE v.paper_id = p.id)
            AND NOT EXISTS (SELECT 1 FROM briefs b WHERE b.paper_id = p.id)
        """,
        "versions_without_digest": """
            SELECT COUNT(*) FROM versions v
            WHERE NOT EXISTS (
                SELECT 1 FROM digests d
                WHERE d.version_id = v.id
            )
        """,
        "versions_with_multiple_digests": """
            SELECT COUNT(*) FROM (
                SELECT version_id FROM digests
                GROUP BY version_id HAVING COUNT(*) > 1
            )
        """,
        "digests_without_search_documents": """
            SELECT COUNT(*) FROM digests d
            WHERE NOT EXISTS (
                SELECT 1 FROM search_documents sd WHERE sd.digest_id = d.id
            )
        """,
        "search_documents_without_matching_digest": """
            SELECT COUNT(*) FROM search_documents sd
            WHERE NOT EXISTS (
                SELECT 1 FROM digests d
                WHERE d.id = sd.digest_id AND d.version_id = sd.version_id
            )
        """,
    }
    relation_results = {
        name: int(connection.execute(sql).fetchone()[0])
        for name, sql in relation_checks.items()
    }
    for name, count in relation_results.items():
        if count:
            errors.append({"kind": name, "count": count})

    rows = connection.execute(
        """
        SELECT p.id AS paper_id, p.canonical_key, p.bibcode, p.title,
               p.authors_json, p.abstract, p.year, v.id AS version_id,
               v.status, v.sha256,
               v.text_sha256, v.content_sha256, v.artifact_path, v.text_path,
               v.manifest_path, d.id AS digest_id, d.digest_json
        FROM papers p
        JOIN versions v ON v.paper_id = p.id
        JOIN digests d ON d.version_id = v.id
        ORDER BY v.id
        """
    ).fetchall()

    invalid_digests: list[dict[str, str]] = []
    incomplete_reading: list[str] = []
    metadata_missing = {"bibcode": [], "authors": [], "abstract": [], "year": []}
    arxiv_awaiting_bibcode: list[str] = []
    search_mismatches: list[str] = []
    referenced_object_dirs: set[Path] = set()
    object_issues: list[dict[str, str]] = []

    for paper in connection.execute("SELECT * FROM papers ORDER BY id"):
        key = str(paper["canonical_key"])
        if not paper["bibcode"]:
            if key.startswith("arxiv:"):
                arxiv_awaiting_bibcode.append(key)
            else:
                metadata_missing["bibcode"].append(key)
        try:
            authors = json.loads(paper["authors_json"])
        except json.JSONDecodeError:
            authors = []
        if not authors:
            metadata_missing["authors"].append(key)
        if not str(paper["abstract"] or "").strip():
            metadata_missing["abstract"].append(key)
        if paper["year"] is None:
            metadata_missing["year"].append(key)

    invalid_sources: list[int] = []
    for brief in connection.execute("SELECT * FROM briefs ORDER BY id"):
        try:
            source = json.loads(brief["source_json"])
        except json.JSONDecodeError:
            invalid_sources.append(brief["id"])
            continue
        if (
            not isinstance(source, dict)
            or stable_digest(source) != brief["source_hash"]
            or brief["evidence_level"] != (
                "abstract" if str(source.get("abstract") or "").strip() else "metadata"
            )
        ):
            invalid_sources.append(brief["id"])
    if invalid_sources:
        errors.append({"kind": "invalid_source_snapshots", "brief_ids": invalid_sources})

    completion = library_catalog.completion_report(connection)
    if completion["status"] != "complete":
        warnings.append({"kind": "catalog_completion", **completion})
    information["missing_cached_citations"] = [
        row[0] for row in connection.execute(
            "SELECT p.canonical_key FROM papers p LEFT JOIN citations c ON c.paper_id = p.id "
            "WHERE p.bibcode IS NOT NULL AND (c.paper_id IS NULL OR c.citekey <> p.bibcode) "
            "ORDER BY p.id"
        )
    ]

    for row in rows:
        key = str(row["canonical_key"])
        try:
            raw_digest = json.loads(row["digest_json"])
            digest = validate_digest(raw_digest)
            if row["status"] == "needs_visual_reading":
                manifest = json.loads(
                    Path(row["manifest_path"]).read_text(encoding="utf-8")
                )
                validate_visual_coverage(manifest.get("selected") or {}, digest)
        except (json.JSONDecodeError, LiteratureError, OSError) as exc:
            invalid_digests.append({"paper": key, "error": str(exc)})
            digest = None
        if digest is not None:
            if (
                digest["reading"]["status"] not in {"full", "visual"}
                or digest["reading"].get("unread_sections")
            ):
                incomplete_reading.append(key)

        full_text_value = ""
        text_path = Path(str(row["text_path"])) if row["text_path"] else None
        if text_path and text_path.is_file():
            full_text_value = text_path.read_text(encoding="utf-8", errors="replace")
        if digest is not None:
            expected_document = build_search_document(
                connection,
                int(row["paper_id"]),
                int(row["version_id"]),
                int(row["digest_id"]),
                digest,
                full_text_value,
            )
            stored_document = connection.execute(
                "SELECT * FROM search_documents WHERE version_id = ?",
                (row["version_id"],),
            ).fetchone()
            if stored_document is None or any(
                str(stored_document[column]) != expected_document[column]
                for column in SEARCH_COLUMNS
            ):
                search_mismatches.append(key)

        for column in ("artifact_path", "text_path", "manifest_path"):
            raw_path = row[column]
            if not raw_path:
                if column != "text_path" or row["status"] == "fulltext":
                    object_issues.append({"paper": key, "kind": f"missing_{column}"})
                continue
            path = Path(str(raw_path))
            referenced_object_dirs.add(path.parent.resolve())
            if not path.is_file():
                object_issues.append(
                    {"paper": key, "kind": f"missing_{column}", "path": str(path)}
                )
            elif not path_is_within(path, library_dir / "objects"):
                object_issues.append(
                    {
                        "paper": key,
                        "kind": "path_outside_object_store",
                        "path": str(path),
                    }
                )
        artifact_path = (
            Path(str(row["artifact_path"])) if row["artifact_path"] else None
        )
        if verify_hashes and artifact_path and artifact_path.is_file():
            if fulltext.sha256_file(artifact_path) != row["sha256"]:
                object_issues.append({"paper": key, "kind": "artifact_hash_mismatch"})
        if verify_hashes and text_path and text_path.is_file():
            if fulltext.sha256_file(text_path) != row["text_sha256"]:
                object_issues.append({"paper": key, "kind": "text_hash_mismatch"})
            if (
                row["status"] == "fulltext"
                and fulltext.canonical_text_sha256(full_text_value)
                != row["content_sha256"]
            ):
                object_issues.append({"paper": key, "kind": "content_hash_mismatch"})
        if (
            verify_hashes
            and row["status"] == "needs_visual_reading"
            and row["content_sha256"] != row["sha256"]
        ):
            object_issues.append(
                {"paper": key, "kind": "visual_content_identity_mismatch"}
            )
        manifest_path = (
            Path(str(row["manifest_path"])) if row["manifest_path"] else None
        )
        if manifest_path and manifest_path.is_file():
            try:
                stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                database_object = stored_manifest.get("database_object") or {}
                expected_paths = {
                    "artifact_path": str(artifact_path.resolve())
                    if artifact_path
                    else None,
                    "text_path": str(text_path.resolve()) if text_path else None,
                    "content_sha256": row["content_sha256"],
                }
                if any(
                    database_object.get(name) != value
                    for name, value in expected_paths.items()
                ):
                    object_issues.append(
                        {"paper": key, "kind": "manifest_database_object_mismatch"}
                    )
            except (OSError, json.JSONDecodeError):
                object_issues.append({"paper": key, "kind": "invalid_stored_manifest"})

    orphan_dirs: list[dict[str, Any]] = []
    for row in connection.execute(
        "SELECT artifact_path, text_path, manifest_path, sha256, text_sha256 FROM artifacts"
    ):
        for column in ("artifact_path", "text_path", "manifest_path"):
            if row[column]:
                path = Path(row[column])
                referenced_object_dirs.add(path.parent.resolve())
                if not path.is_file() or not path_is_within(
                    path, library_dir / "objects"
                ):
                    object_issues.append(
                        {
                            "kind": "historical_artifact_missing_or_external",
                            "path": str(path),
                        }
                    )
                elif verify_hashes and column != "manifest_path":
                    expected = (
                        row["sha256"]
                        if column == "artifact_path"
                        else row["text_sha256"]
                    )
                    if expected and fulltext.sha256_file(path) != expected:
                        object_issues.append(
                            {
                                "kind": "historical_artifact_hash_mismatch",
                                "path": str(path),
                            }
                        )
    objects_dir = library_dir / "objects"
    if objects_dir.is_dir():
        for prefix in objects_dir.iterdir():
            if not prefix.is_dir():
                continue
            for object_dir in prefix.iterdir():
                if (
                    not object_dir.is_dir()
                    or object_dir.resolve() in referenced_object_dirs
                ):
                    continue
                files = [path for path in object_dir.rglob("*") if path.is_file()]
                if files:
                    orphan_dirs.append(
                        {
                            "path": str(object_dir.resolve()),
                            "files": len(files),
                            "bytes": sum(path.stat().st_size for path in files),
                        }
                    )

    fts_mismatches: list[str] = []
    if fts5:
        fts_mismatches = [
            str(row[0])
            for row in connection.execute(
                "SELECT sd.version_id FROM search_documents sd "
                "WHERE sd.id NOT IN (SELECT id FROM search_fts_docsize) "
                "UNION SELECT 'index row ' || id FROM search_fts_docsize "
                "WHERE id NOT IN (SELECT id FROM search_documents)"
            )
        ]

    if invalid_digests:
        errors.append({"kind": "invalid_digests", "items": invalid_digests})
    if incomplete_reading:
        errors.append(
            {"kind": "incomplete_reading_digests", "papers": incomplete_reading}
        )
    if object_issues:
        errors.append({"kind": "object_integrity", "items": object_issues})
    if search_mismatches:
        warnings.append({"kind": "search_document_drift", "papers": search_mismatches})
    if fts_mismatches:
        errors.append({"kind": "fts_document_mismatch", "version_ids": fts_mismatches})
    if orphan_dirs:
        warnings.append({"kind": "orphan_object_directories", "items": orphan_dirs})
    missing_metadata_counts = {
        name: len(items) for name, items in metadata_missing.items()
    }
    if any(missing_metadata_counts.values()):
        warnings.append(
            {
                "kind": "incomplete_metadata",
                "counts": missing_metadata_counts,
                "papers": metadata_missing,
            }
        )
    information.update(
        {
            "arxiv_records_awaiting_ads_bibcode": arxiv_awaiting_bibcode,
        }
    )
    status = "unhealthy" if errors else "attention" if warnings else "healthy"
    return {
        "status": status,
        "checked_at": fulltext.utc_now(),
        "library_dir": str(library_dir),
        "database": {
            "integrity_check": integrity,
            "quick_check": quick_check,
            "foreign_key_violations": len(foreign_keys),
            "relations": relation_results,
        },
        "counts": library_stats(connection, fts5, library_dir)["counts"],
        "hashes_verified": verify_hashes,
        "errors": errors,
        "warnings": warnings,
        "information": information,
    }


def rebuild_index(connection: sqlite3.Connection, fts5: bool) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT p.id AS paper_id, v.id AS version_id, v.text_path,
               d.id AS digest_id, d.digest_json
        FROM papers p
        JOIN versions v ON v.paper_id = p.id
        JOIN digests d ON d.version_id = v.id
        ORDER BY v.id
        """
    ).fetchall()
    connection.execute("BEGIN IMMEDIATE")
    try:
        if fts5:
            drop_search_index(connection)
        connection.execute("DELETE FROM search_documents")
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
            replace_search_document(connection, document)
        if fts5:
            create_search_index(connection)
            connection.execute("INSERT INTO search_fts(search_fts) VALUES('rebuild')")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"status": "rebuilt", "documents": len(rows), "fts5": fts5}


def compact_library(connection: sqlite3.Connection, library_dir: Path) -> dict[str, Any]:
    """Rewrite the database file without the pages that removed records left free."""
    database = library_dir / "literature.sqlite3"
    before = database.stat().st_size
    connection.execute("VACUUM")
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    after = database.stat().st_size
    return {
        "status": "compacted",
        "database_path": str(database),
        "bytes_before": before,
        "bytes_after": after,
        "bytes_freed": before - after,
        "integrity": integrity,
    }


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
        require_chinese_digest(digest)
        anchors = None
        if args.text:
            text_path = Path(args.text).expanduser()
            try:
                text = text_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise LiteratureError(f"Unable to read article text: {exc}", 2) from exc
            anchors = quote_anchors(digest, text)
        report: dict[str, Any] = {
            "status": "valid",
            "schema_version": digest["schema_version"],
            "reading_status": digest["reading"]["status"],
            "facets": len(digest["facets"]),
            "findings": sum(len(facet["findings"]) for facet in digest["facets"]),
            "values": sum(
                len(finding.get("values", []))
                for facet in digest["facets"]
                for finding in facet["findings"]
            ),
            "references_checked": digest["reading"]["status"] != "targeted",
        }
        if anchors is not None:
            report["anchors"] = anchors
        report["warnings"] = digest_warnings(digest, anchors)
        stdout.write(pretty_json(report))
        return 0
    if args.command == "restore":
        stdout.write(
            pretty_json(restore_library(Path(args.backup), Path(args.destination)))
        )
        return 0

    library_dir = (
        Path(args.library_dir).expanduser().resolve()
        if args.library_dir
        else default_library_dir(environ)
    )
    if args.command == "migrate":
        import library_migrate

        stdout.write(
            pretty_json(library_migrate.migrate_library(library_dir, args.destination))
        )
        return 0
    if args.command == "serve":
        import library_web

        library_web.serve(library_dir, args.port, stdout)
        return 0
    read_commands = {
        "lookup",
        "passage",
        "show",
        "search",
        "list",
        "findings",
        "parameters",
        "stats",
        "audit",
        "backup",
        "pending",
        "check",
        "reading-check",
        "runs",
    }
    if args.command == "collections" and not args.create:
        read_commands.add("collections")
    if args.command == "citations" and not args.fetch:
        read_commands.add("citations")
    if args.command in read_commands:
        connection, fts5 = connect_library_readonly(
            library_dir,
            allow_missing=args.command not in {"audit", "backup"},
        )
    else:
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
            require_chinese_digest(digest)
            result = ingest_record(
                connection,
                fts5,
                library_dir,
                manifest,
                digest,
                merge=args.merge,
                replace_digest=args.replace_digest,
            )
        elif args.command == "enrich":
            manifest_payload = load_json(args.manifest, stdin)
            manifest = select_manifest_result(manifest_payload, args.identifier)
            result = enrich_paper_metadata(connection, fts5, manifest)
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
        elif args.command == "passage":
            if args.max_chars < 0:
                raise LiteratureError("--max-chars must be zero or positive.", 2)
            result = article_passages(
                connection,
                args.identifier,
                findings=args.finding,
                sections=args.section,
                terms=args.grep,
                outline=args.outline,
                artifact_hash=args.sha256,
                context=args.context,
                max_chars=args.max_chars,
                limit=args.limit,
            )
        elif args.command == "show":
            result = show_paper(
                connection,
                args.identifier,
                include_fulltext=args.include_fulltext,
            )
        elif args.command in {"search", "list"} and (
            args.collection or args.role or args.tag
        ):
            result = library_catalog.browse(
                connection,
                fts5,
                query=getattr(args, "query", ""),
                collection=args.collection,
                role=args.role,
                tag=args.tag,
                limit=args.limit,
                scope=getattr(args, "scope", "all"),
                mode=getattr(args, "mode", "terms"),
                topics=args.topic,
                year_from=args.year_from,
                year_to=args.year_to,
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
        elif args.command in ("findings", "parameters"):
            table = evidence_table(
                connection,
                "findings" if args.command == "findings" else "values",
                query=args.query,
                identifiers=args.paper,
                entity=args.entity,
                kinds=args.kind,
                statuses=args.status,
                collection=args.collection,
                role=args.role,
                tag=args.tag,
                year_from=args.year_from,
                year_to=args.year_to,
                limit=args.limit,
            )
            text = (
                evidence_csv(table) if args.format == "csv" else pretty_json(table)
            )
            if args.output:
                output = Path(args.output).expanduser().resolve()
                if path_is_within(output, library_dir):
                    raise LiteratureError(
                        "Evidence output must be outside the managed library.", 2
                    )
                fulltext.atomic_write_text(
                    output, ("﻿" + text) if args.format == "csv" else text
                )
                result = {
                    "status": "exported",
                    "format": args.format,
                    "count": table["count"],
                    "truncated": table["truncated"],
                    "path": str(output),
                }
            else:
                result = text
        elif args.command == "stats":
            result = library_stats(connection, fts5, library_dir)
        elif args.command == "audit":
            result = audit_library(
                connection,
                fts5,
                library_dir,
                verify_hashes=not args.skip_hashes,
            )
        elif args.command == "backup":
            result = create_library_backup(
                connection, fts5, library_dir, args.destination
            )
        elif args.command == "reindex":
            result = rebuild_index(connection, fts5)
        elif args.command == "compact":
            result = compact_library(connection, library_dir)
        else:
            result = library_catalog.execute_command(
                args, connection, fts5, library_dir, environ, stdin
            )
        stdout.write(result if isinstance(result, str) else pretty_json(result))
        return (
            1
            if (args.command == "audit" and result["errors"])
            or (args.command in {"check", "reading-check"} and result["status"] != "complete")
            else 0
        )
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
    except (
        LiteratureError,
        fulltext.FullTextError,
        ads_api.CliError,
        sqlite3.Error,
        OSError,
        ValueError,
    ) as exc:
        (stderr or sys.stderr).write(f"error: {exc}\n")
        return exc.exit_code if isinstance(exc, LiteratureError) else 1


def main() -> None:
    ads_api.configure_stdio()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
