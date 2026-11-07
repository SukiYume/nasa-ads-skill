#!/usr/bin/env python3
"""One-time upgrade of a literature library from the previous release.

The library CLI reads only the current database and digest schemas. This module
backs up a schema 3 library, converts its schema 2 and 3 digests to the current
digest schema, rebuilds the digest table and search index, and compacts the
database. Values, types, and study types that earlier records left unclassified
are assigned by rule, and each converted record says so in ``reading.notes``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import fulltext


def library_module():
    import literature_db

    return literature_db


SOURCE_DATABASE_SCHEMA = 3
SKIPPED_SECTION_ROLES = {"references", "administrative"}
ENTITY_TYPE_RULES = (
    ("software", ("software", "code", "pipeline", "package", "tool", "library", "algorithm")),
    ("simulation", ("simulation",)),
    ("catalog", ("catalog", "catalogue", "database")),
    (
        "instrument",
        (
            "telescope", "instrument", "receiver", "interferometer", "array",
            "detector", "observatory", "spectrograph", "camera", "facility",
            "satellite", "backend",
        ),
    ),
    (
        "survey",
        ("survey", "program", "programme", "project", "campaign", "collaboration", "mission"),
    ),
    ("model", ("model", "theory", "framework", "mechanism", "scenario", "relation")),
    (
        "source",
        (
            "frb", "burst", "pulsar", "magnetar", "star", "galaxy", "cluster", "source",
            "object", "transient", "nebula", "remnant", "binary", "agn", "quasar",
            "planet", "dwarf", "black hole", "neutron", "supernova", "grb", "sgr",
            "repeater", "host", "structure", "cloud", "region", "astronomical",
        ),
    ),
)
DATASET_TYPE_RULES = (
    ("simulation", ("simulat",)),
    ("laboratory", ("laborator",)),
    ("catalog", ("catalog", "catalogue")),
    ("survey", ("survey",)),
    ("archival", ("archiv", "published", "literature", "compil", "previous")),
)
METHODS_TITLE_PATTERN = re.compile(
    r"pipeline|algorithm|method|technique|software|package|machine learning|"
    r"neural|deep learning|framework",
    re.IGNORECASE,
)
THEORY_PATTERN = re.compile(r"model|theor|analytic|mechanism|predict", re.IGNORECASE)
UPPER_LIMIT_PATTERN = re.compile(
    r"upper limit|upper bound|at most|less than|below|[<≤]", re.IGNORECASE
)
LOWER_LIMIT_PATTERN = re.compile(
    r"lower limit|lower bound|at least|greater than|exceed|[>≥]", re.IGNORECASE
)
FIT_PATTERN = re.compile(r"\bfit|best[- ]fit|posterior|mcmc|likelihood", re.IGNORECASE)
SENTENCE_END_PATTERN = re.compile(r"[.!?](?=\s+[A-Z0-9\"'(\[])|[。！？]")
FOLD_LABELS = {
    "en": {
        "instrument": "instrument", "setup": "setup", "sample": "sample",
        "time_span": "epochs", "frequency": "band", "software": "Software",
    },
    "zh": {
        "instrument": "仪器", "setup": "配置", "sample": "样本",
        "time_span": "时间", "frequency": "波段", "software": "软件",
    },
}
INFERRED_LABELS_ZH = {
    "dataset types": "数据集类型",
    "entity types": "实体类型",
    "study types": "研究类型",
    "value statuses": "数值状态",
}
ABBREVIATIONS = ("al.", "e.g.", "i.e.", "fig.", "figs.", "eq.", "eqs.", "vs.", "cf.", "approx.", "ca.")


def first_sentence(text: str) -> str:
    """The opening sentence of a summary, skipping abbreviations such as ``et al.``."""
    text = " ".join(text.split())
    for match in SENTENCE_END_PATTERN.finditer(text):
        sentence = text[: match.end()].strip()
        if not sentence.casefold().endswith(ABBREVIATIONS):
            return sentence
    return text


def join_text(first: str, second: str) -> str:
    first, second = first.strip(), second.strip()
    if not second or second in first:
        return first
    if not first:
        return second
    separator = "" if re.search(r"[　-鿿]$", first) else " "
    return first + separator + second


def classify(text: str, rules: tuple[tuple[str, tuple[str, ...]], ...]) -> str | None:
    folded = text.casefold()
    for label, words in rules:
        if any(word in folded for word in words):
            return label
    return None


def infer_value_status(value: dict[str, Any], kind: str) -> str:
    text = " ".join(str(value.get(field, "")) for field in ("qualifier", "name", "value"))
    if UPPER_LIMIT_PATTERN.search(text):
        return "upper-limit"
    if LOWER_LIMIT_PATTERN.search(text):
        return "lower-limit"
    if FIT_PATTERN.search(text):
        return "fitted"
    if kind == "method":
        return "fixed"
    if kind in {"constraint", "nondetection"}:
        return "derived"
    return "measured"


def infer_study_types(digest: dict[str, Any], title: str) -> list[str]:
    text = " ".join([title, digest["overview"].get("summary", "")])
    types: list[str] = []
    if re.search(r"\breview\b", title, re.IGNORECASE):
        types.append("review")
    dataset_types = {record.get("type") for record in digest["datasets"]}
    if "simulation" in dataset_types:
        types.append("simulation")
    if "catalog" in dataset_types:
        types.append("catalog")
    if "laboratory" in dataset_types:
        types.append("laboratory")
    if dataset_types & {"observation", "survey", "archival"}:
        types.append("observational")
    if METHODS_TITLE_PATTERN.search(title):
        types.append("methods")
    if not types or (not digest["datasets"] and THEORY_PATTERN.search(text)):
        types.append("theoretical")
    return list(dict.fromkeys(types))


def upgrade_digest(digest: dict[str, Any], title: str = "") -> tuple[dict[str, Any], Counter]:
    """Convert a stored schema 2, 3, or transitional 4 digest to the current form."""
    library = library_module()
    source_version = digest.get("schema_version")
    if source_version not in (2, 3, 4):
        raise library.LiteratureError(
            f"Digest schema {source_version} cannot be migrated.", 2
        )
    upgraded = json.loads(json.dumps(digest))
    inferred: Counter = Counter()
    upgraded["schema_version"] = library.DIGEST_SCHEMA_VERSION
    overview = upgraded["overview"]
    summary = str(overview.get("summary", ""))
    overview.setdefault("tldr", first_sentence(summary))
    overview["summary"] = join_text(summary, str(overview.pop("significance", "") or ""))
    upgraded.setdefault("assessment", [])

    for entity in upgraded.get("entities", []):
        if entity.get("type") not in library.ENTITY_TYPES:
            entity["type"] = classify(str(entity.get("type") or ""), ENTITY_TYPE_RULES) or "other"
            inferred["entity types"] += 1
    chinese = str(upgraded.get("language", "")).casefold().startswith("zh")
    labels = FOLD_LABELS["zh" if chinese else "en"]
    colon, separator = ("：", "；") if chinese else (": ", "; ")
    for dataset in upgraded.get("datasets", []):
        details = separator.join(
            f"{labels[field]}{colon}{dataset[field]}"
            for field in ("instrument", "setup", "sample", "time_span", "frequency")
            if dataset.get(field)
        )
        for field in ("instrument", "setup", "sample", "time_span", "frequency"):
            dataset.pop(field, None)
        description = str(dataset.get("description", "")).strip()
        if details:
            bracketed = f"（{details}）" if chinese else f"({details})"
            dataset["description"] = join_text(description, bracketed) if description else details
        if dataset.get("type") not in library.DATASET_TYPES:
            dataset["type"] = (
                classify(" ".join([dataset["name"], dataset.get("description", "")]), DATASET_TYPE_RULES)
                or "observation"
            )
            inferred["dataset types"] += 1
    for method in upgraded.get("methods", []):
        description = join_text(
            str(method.pop("purpose", "") or ""), str(method.get("description", ""))
        )
        software = method.pop("software", "")
        if software:
            stop = "。" if chinese else "."
            description = join_text(description, f"{labels['software']}{colon}{software}{stop}")
        upgraded["keywords"] = [*upgraded.get("keywords", []), *method.pop("keywords", [])]
        if description:
            method["description"] = description
    method_names = {method["name"].casefold() for method in upgraded.get("methods", [])}

    for facet in upgraded["facets"]:
        for limitation in facet.pop("limitations", []):
            upgraded["global_limitations"].append(f"{facet['label']}{colon}{limitation}")
        known = [name for name in facet.get("methods", []) if name.casefold() in method_names]
        unknown = [name for name in facet.get("methods", []) if name.casefold() not in method_names]
        facet["methods"] = known
        facet["keywords"] = [*facet.get("keywords", []), *unknown]
        for finding in facet["findings"]:
            for value in finding.get("values", []):
                if not value.get("status"):
                    value["status"] = infer_value_status(value, finding["kind"])
                    inferred["value statuses"] += 1

    if not overview.get("study_types"):
        overview["study_types"] = infer_study_types(upgraded, title)
        inferred["study types"] += 1

    reading = upgraded["reading"]
    roles = {
        library.normalized_heading(item.get("section", "")): item.get("role")
        for item in reading.pop("coverage", [])
    }
    headings = [
        section if isinstance(section, str) else section.get("heading", "")
        for section in reading.get("sections", [])
    ]
    kept = [
        heading
        for heading in headings
        if roles.get(library.normalized_heading(heading)) not in SKIPPED_SECTION_ROLES
    ]
    if isinstance(next(iter(reading.get("sections", [])), None), dict):
        reading["sections"] = [
            section for section in reading["sections"] if section.get("heading") in (kept or headings)
        ]
    else:
        reading["sections"] = kept or headings
    pages = reading.pop("page_ranges", [])
    notes = str(reading.get("notes", ""))
    if pages:
        pages_note = (
            f"已读页码：{'、'.join(pages)}。" if chinese else f"Pages read: {', '.join(pages)}."
        )
        notes = join_text(notes, pages_note)
    if inferred:
        if chinese:
            assigned = "、".join(INFERRED_LABELS_ZH[key] for key in sorted(inferred))
            note = (
                f"由 schema {source_version} 迁移转换：{assigned}由规则推断，"
                "引用前请核对原文。"
            )
        else:
            note = (
                f"Converted from schema {source_version} by migrate: "
                f"{', '.join(sorted(inferred))} were assigned by rule; check them "
                "in the article before citing."
            )
        notes = join_text(notes, note)
    reading["notes"] = notes
    return library.validate_digest(upgraded), inferred


def migrate_library(library_dir: Path, backup_destination: str | None = None) -> dict[str, Any]:
    library = library_module()
    database_path = library_dir / "literature.sqlite3"
    if not database_path.is_file():
        raise library.LiteratureError(f"Literature database does not exist: {database_path}", 2)
    connection = sqlite3.connect(database_path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version == library.DATABASE_SCHEMA_VERSION:
            return {"status": "current", "database_schema_version": version}
        if version != SOURCE_DATABASE_SCHEMA:
            raise library.LiteratureError(
                f"migrate converts schema {SOURCE_DATABASE_SCHEMA} libraries; this "
                f"database is schema {version}.",
                2,
            )
        fts5 = (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'search_fts'"
            ).fetchone()
            is not None
        )
        rows = connection.execute(
            "SELECT d.id, d.version_id, d.reading_status, d.digest_json, d.created_at, "
            "p.title FROM digests d JOIN versions v ON v.id = d.version_id "
            "JOIN papers p ON p.id = v.paper_id ORDER BY d.id"
        ).fetchall()
        converted: list[tuple[Any, ...]] = []
        failures: list[dict[str, Any]] = []
        sources: Counter = Counter()
        inferred_total: Counter = Counter()
        for row in rows:
            raw = json.loads(row["digest_json"])
            try:
                digest, inferred = upgrade_digest(raw, row["title"])
            except library.LiteratureError as exc:
                failures.append({"digest_id": row["id"], "title": row["title"], "error": str(exc)})
                continue
            sources[str(raw.get("schema_version"))] += 1
            inferred_total.update(inferred)
            converted.append(
                (
                    row["id"],
                    row["version_id"],
                    digest["reading"]["status"],
                    library.stable_digest(digest),
                    library.json_text(digest),
                    row["created_at"],
                )
            )
        if failures:
            raise library.LiteratureError(
                "migrate stopped before changing the library; these digests could not "
                "be converted: " + json.dumps(failures[:20], ensure_ascii=False),
                1,
            )
        backup = library.create_library_backup(connection, fts5, library_dir, backup_destination)
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for table in ("findings", "facets", "search_fts"):
                connection.execute(f"DROP TABLE IF EXISTS {table}")
            connection.execute("DELETE FROM search_documents")
            connection.execute("DROP TABLE digests")
            connection.execute(
                """
                CREATE TABLE digests (
                    id INTEGER PRIMARY KEY,
                    version_id INTEGER NOT NULL UNIQUE REFERENCES versions(id) ON DELETE CASCADE,
                    reading_status TEXT NOT NULL,
                    digest_hash TEXT NOT NULL,
                    digest_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.executemany(
                "INSERT INTO digests(id, version_id, reading_status, digest_hash, "
                "digest_json, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                converted,
            )
            connection.execute(f"PRAGMA user_version = {library.DATABASE_SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        connection.execute("PRAGMA foreign_keys = ON")
        fts5 = library.initialize_schema(connection)
        index = library.rebuild_index(connection, fts5)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        connection.execute("VACUUM")
    finally:
        connection.close()
    return {
        "status": "migrated",
        "database_schema_version": library.DATABASE_SCHEMA_VERSION,
        "digest_schema_version": library.DIGEST_SCHEMA_VERSION,
        "backup": backup["destination"],
        "digests": {"converted": len(converted), "by_source_schema": dict(sources)},
        "assigned_by_rule": dict(inferred_total),
        "search_documents": index["documents"],
        "integrity": integrity,
        "foreign_key_violations": len(violations),
        "migrated_at": fulltext.utc_now(),
    }
