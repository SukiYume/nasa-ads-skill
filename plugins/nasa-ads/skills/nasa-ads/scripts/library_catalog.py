"""Search capture, personal organization, and offline citation support.

Scientific summaries are authored by the host agent. Capture stores the source
and an explicit pending state until a summary is supplied.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import ads_api
import fulltext

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    source_hash TEXT NOT NULL,
    source_json TEXT NOT NULL,
    evidence_level TEXT NOT NULL CHECK(evidence_level IN ('abstract','metadata')),
    summary TEXT NOT NULL DEFAULT '',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(paper_id, source_hash)
);
CREATE INDEX IF NOT EXISTS briefs_paper_idx ON briefs(paper_id, id);
CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY,
    query TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    num_found INTEGER NOT NULL,
    returned_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS search_hits (
    run_id INTEGER NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    brief_id INTEGER NOT NULL REFERENCES briefs(id),
    position INTEGER NOT NULL,
    PRIMARY KEY(run_id, paper_id)
);
CREATE TABLE IF NOT EXISTS collections (
    path TEXT PRIMARY KEY,
    parent TEXT REFERENCES collections(path),
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS paper_collections (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    collection_path TEXT NOT NULL REFERENCES collections(path),
    PRIMARY KEY(paper_id, collection_path)
);
CREATE TABLE IF NOT EXISTS paper_tags (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY(paper_id, tag)
);
CREATE TABLE IF NOT EXISTS paper_roles (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY(paper_id, role)
);
CREATE TABLE IF NOT EXISTS paper_notes (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(paper_id, text)
);
CREATE TABLE IF NOT EXISTS citations (
    paper_id INTEGER PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    citekey TEXT NOT NULL UNIQUE,
    bibtex TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS version_labels (
    version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
    arxiv_id TEXT NOT NULL,
    PRIMARY KEY(version_id, arxiv_id)
);
"""

WRITING_ROLES = ("review", "intro", "methods", "discussion", "comparison")


def db():
    # Lazy import keeps the three CLI entrypoints independently executable.
    import literature_db

    return literature_db


def metadata_manifest(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    result["title"] = fulltext.first_value(record.get("title"))
    result["arxiv_ids"] = fulltext.ordered_unique_strings(
        value
        for item in fulltext.list_value(record.get("identifier"))
        if (value := fulltext.arxiv_id_from_value(item))
    )
    result["arxiv_ids"] += fulltext.list_value(record.get("arxiv_ids"))
    result["alternate_bibcode"] = fulltext.list_value(record.get("alternate_bibcode"))
    result["alternate_bibcode"] += [
        item
        for item in fulltext.list_value(record.get("identifier"))
        if re.fullmatch(r"\d{4}[A-Za-z&.][^\s]{14}", item)
    ]
    return result


def source_snapshot(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        key: manifest.get(key)
        for key in (
            "bibcode",
            "title",
            "author",
            "abstract",
            "year",
            "pub",
            "doctype",
            "doi",
            "arxiv_ids",
            "volume",
            "issue",
            "page",
            "eid",
            "pubdate",
        )
    }


def collection_path(value: str) -> str:
    parts = [part.strip() for part in value.strip().split("/")]
    if (
        not parts
        or len(parts) > 12
        or any(
            not part
            or part in {".", ".."}
            or len(part) > 100
            or any(ord(char) < 32 or char == "\\" for char in part)
            for part in parts
        )
    ):
        raise db().LiteratureError(
            "Collection paths require 1-12 named levels separated by /.", 2
        )
    return "/".join(parts)


def add_collection(connection, path: str, description: str = "") -> str:
    path = collection_path(path)
    parts = path.split("/")
    for index in range(1, len(parts) + 1):
        prefix = "/".join(parts[:index])
        parent = "/".join(parts[: index - 1]) or None
        connection.execute(
            "INSERT OR IGNORE INTO collections(path, parent) VALUES (?, ?)",
            (prefix, parent),
        )
    if description:
        connection.execute(
            "UPDATE collections SET description = ? WHERE path = ?", (description, path)
        )
    return path


def annotate_paper(
    connection, paper_id: int, *, collections=(), tags=(), roles=(), note=""
):
    roles = list(roles)
    if any(role not in WRITING_ROLES for role in roles):
        raise db().LiteratureError(
            "Writing role must be review, intro, methods, discussion, or comparison.", 2
        )
    paths = [
        collection_path(value)
        for value in db().string_list(list(collections), "collections")
    ]
    if not isinstance(note, str):
        raise db().LiteratureError("A personal note must be text.", 2)
    tags = db().string_list(list(tags), "tags")
    for path in paths:
        add_collection(connection, path)
        connection.execute(
            "INSERT OR IGNORE INTO paper_collections VALUES (?, ?)", (paper_id, path)
        )
    for tag in tags:
        connection.execute(
            "INSERT OR IGNORE INTO paper_tags VALUES (?, ?)", (paper_id, tag)
        )
    for role in roles:
        connection.execute(
            "INSERT OR IGNORE INTO paper_roles VALUES (?, ?)", (paper_id, role)
        )
    if note.strip():
        connection.execute(
            "INSERT OR IGNORE INTO paper_notes(paper_id, text, created_at) VALUES (?, ?, ?)",
            (paper_id, note.strip(), fulltext.utc_now()),
        )


def paper_organization(connection, paper_id: int) -> dict[str, Any]:
    return {
        "collections": [
            row[0]
            for row in connection.execute(
                "SELECT collection_path FROM paper_collections WHERE paper_id = ? ORDER BY collection_path",
                (paper_id,),
            )
        ],
        "tags": [
            row[0]
            for row in connection.execute(
                "SELECT tag FROM paper_tags WHERE paper_id = ? ORDER BY tag",
                (paper_id,),
            )
        ],
        "roles": [
            row[0]
            for row in connection.execute(
                "SELECT role FROM paper_roles WHERE paper_id = ? ORDER BY role",
                (paper_id,),
            )
        ],
        "notes": [
            dict(row)
            for row in connection.execute(
                "SELECT id, text, created_at FROM paper_notes WHERE paper_id = ? ORDER BY id",
                (paper_id,),
            )
        ],
    }


def latest_brief(connection, paper_id: int):
    return connection.execute(
        "SELECT * FROM briefs WHERE paper_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
        (paper_id,),
    ).fetchone()


def brief_value(row) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "source_hash": row["source_hash"],
        "evidence_level": row["evidence_level"],
        "summary_status": "complete" if row["summary"] else "pending",
        "summary": row["summary"],
        "keywords": json.loads(row["keywords_json"]),
        "source": json.loads(row["source_json"]),
        "updated_at": row["updated_at"],
    }


def capture_search(
    connection,
    fts5: bool,
    payload: dict,
    *,
    query: str,
    parameters: dict,
    collections=(),
    roles=(),
) -> dict[str, Any]:
    library = db()
    response = payload.get("response")
    if not isinstance(response, dict) or not isinstance(response.get("docs"), list):
        raise library.LiteratureError("ADS search response requires response.docs.", 2)
    count = response.get("numFound")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise library.LiteratureError(
            "ADS search response requires a nonnegative numFound.", 2
        )
    manifests = [
        metadata_manifest(library.require_mapping(record, "ADS record"))
        for record in response["docs"]
    ]
    prepared = [
        (manifest, library.validate_paper_metadata(manifest)) for manifest in manifests
    ]
    now = fulltext.utc_now()
    captured = []
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        run_id = connection.execute(
            "INSERT INTO search_runs(query, parameters_json, num_found, returned_count, created_at) VALUES (?, ?, ?, ?, ?)",
            (query, library.json_text(parameters), count, len(manifests), now),
        ).lastrowid
        for position, (manifest, aliases) in enumerate(prepared):
            paper_id = library.upsert_paper(connection, manifest, aliases)
            snapshot = source_snapshot(manifest)
            source_hash = library.stable_digest(snapshot)
            level = (
                "abstract"
                if str(snapshot.get("abstract") or "").strip()
                else "metadata"
            )
            connection.execute(
                "INSERT INTO briefs(paper_id, source_hash, source_json, evidence_level, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(paper_id, source_hash) DO UPDATE SET updated_at = excluded.updated_at",
                (paper_id, source_hash, library.json_text(snapshot), level, now, now),
            )
            brief = connection.execute(
                "SELECT * FROM briefs WHERE paper_id = ? AND source_hash = ?",
                (paper_id, source_hash),
            ).fetchone()
            connection.execute(
                "INSERT OR IGNORE INTO search_hits VALUES (?, ?, ?, ?)",
                (run_id, paper_id, brief["id"], position),
            )
            annotate_paper(connection, paper_id, collections=collections, roles=roles)
            captured.append(
                {
                    "paper_id": paper_id,
                    "identifier": manifest.get("bibcode") or aliases[0][1],
                    "source_hash": source_hash,
                    "evidence_level": level,
                    "summary_status": "complete" if brief["summary"] else "pending",
                }
            )
            reindex_paper(connection, fts5, paper_id)
    unique = list({item["paper_id"]: item for item in captured}.values())
    return {
        "status": "captured",
        "run_id": run_id,
        "captured": len(unique),
        "pending_summaries": sum(
            item["summary_status"] == "pending" for item in unique
        ),
        "reused_summaries": sum(
            item["summary_status"] == "complete" for item in unique
        ),
        "uncategorized": completion_report(connection, run_id=run_id)["uncategorized"],
        "records": unique,
    }


def reindex_paper(connection, fts5: bool, paper_id: int):
    library = db()
    for row in connection.execute(
        "SELECT v.id, v.text_path, d.id AS digest_id, d.digest_json FROM versions v "
        "JOIN digests d ON d.version_id = v.id WHERE v.paper_id = ?",
        (paper_id,),
    ).fetchall():
        text = (
            Path(row["text_path"]).read_text(encoding="utf-8")
            if row["text_path"] and Path(row["text_path"]).is_file()
            else ""
        )
        document = library.build_search_document(
            connection,
            paper_id,
            row["id"],
            row["digest_id"],
            json.loads(row["digest_json"]),
            text,
        )
        library.replace_search_document(connection, document, fts5)


def pending_summaries(connection, *, run_id=None, limit=50, offset=0) -> dict:
    where = "WHERE b.summary = ''"
    params = []
    if run_id is not None:
        where += " AND EXISTS (SELECT 1 FROM search_hits h WHERE h.brief_id = b.id AND h.run_id = ?)"
        params.append(run_id)
    else:
        where += " AND b.id = (SELECT recent.id FROM briefs recent WHERE recent.paper_id = b.paper_id ORDER BY recent.updated_at DESC, recent.id DESC LIMIT 1)"
    total = connection.execute(
        f"SELECT COUNT(*) FROM briefs b {where}", params
    ).fetchone()[0]
    rows = connection.execute(
        f"SELECT b.*, p.bibcode, p.canonical_key FROM briefs b JOIN papers p ON p.id = b.paper_id {where} ORDER BY b.id LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return {
        "count": total,
        "results": [
            {
                "identifier": row["bibcode"] or row["canonical_key"].split(":", 1)[1],
                "paper_id": row["paper_id"],
                **brief_value(row),
            }
            for row in rows
        ],
    }


def summarize(connection, raw: Any) -> dict:
    library = db()
    records = raw.get("summaries") if isinstance(raw, dict) else raw
    if not isinstance(records, list) or not records:
        raise library.LiteratureError(
            "Summaries must be a nonempty array or an object containing summaries.", 2
        )
    prepared = []
    for record in records:
        record = library.require_mapping(record, "summary")
        library.reject_unknown_fields(
            record,
            "summary",
            {
                "identifier",
                "source_hash",
                "summary",
                "keywords",
                "collections",
                "roles",
                "note",
            },
        )
        identifier = library.require_string(
            record.get("identifier"), "summary.identifier"
        )
        paper = library.find_paper_by_identifier(connection, identifier)
        if paper is None:
            raise library.LiteratureError(
                f"Capture metadata before summarizing {identifier}.", 2
            )
        source_hash = library.require_string(
            record.get("source_hash"), "summary.source_hash"
        )
        brief = connection.execute(
            "SELECT * FROM briefs WHERE paper_id = ? AND source_hash = ?",
            (paper["id"], source_hash),
        ).fetchone()
        if brief is None:
            raise library.LiteratureError(
                f"Summary source_hash does not match a stored source for {identifier}.",
                2,
            )
        summary = library.require_string(record.get("summary"), "summary.summary")
        for field in ("collections", "roles"):
            library.string_list(record.get(field, []), "summary." + field)
        if not isinstance(record.get("note", ""), str):
            raise library.LiteratureError("A personal note must be text.", 2)
        keywords = library.string_list(record.get("keywords", []), "summary.keywords")
        if brief["summary"] and (
            brief["summary"] != summary
            or json.loads(brief["keywords_json"]) != keywords
        ):
            raise library.LiteratureError(
                "This source already has a summary. Append a personal note or enrich its complete article digest.",
                2,
            )
        prepared.append((paper["id"], brief["id"], summary, keywords, record))
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        for paper_id, brief_id, summary, keywords, record in prepared:
            current = connection.execute(
                "SELECT summary, keywords_json FROM briefs WHERE id = ?", (brief_id,)
            ).fetchone()
            if current["summary"] and (
                current["summary"] != summary
                or json.loads(current["keywords_json"]) != keywords
            ):
                raise library.LiteratureError(
                    "The stored summary changed during this operation. Read it before retrying.",
                    2,
                )
            connection.execute(
                "UPDATE briefs SET summary = ?, keywords_json = ? WHERE id = ?",
                (summary, library.json_text(keywords), brief_id),
            )
            annotate_paper(
                connection,
                paper_id,
                collections=record.get("collections", []),
                tags=keywords,
                roles=record.get("roles", []),
                note=record.get("note", ""),
            )
    return {"status": "summarized", "count": len(prepared)}


def completion_report(connection, *, run_id=None) -> dict:
    """Report both authorship and organization before a research task is complete."""
    if (
        run_id is not None
        and not connection.execute(
            "SELECT 1 FROM search_runs WHERE id = ?", (run_id,)
        ).fetchone()
    ):
        raise db().LiteratureError("Unknown search run.", 2)
    pending = pending_summaries(connection, run_id=run_id, limit=1)["count"]
    where = ""
    params = ()
    if run_id is not None:
        where = "WHERE EXISTS (SELECT 1 FROM search_hits h WHERE h.paper_id = p.id AND h.run_id = ?)"
        params = (run_id,)
    papers = connection.execute(
        "SELECT p.id, p.bibcode, p.canonical_key, p.title FROM papers p "
        + where
        + " ORDER BY p.id",
        params,
    ).fetchall()
    uncategorized = [
        {
            "paper_id": p["id"],
            "identifier": p["bibcode"] or p["canonical_key"].split(":", 1)[1],
            "title": p["title"],
        }
        for p in papers
        if not connection.execute(
            "SELECT 1 FROM paper_collections WHERE paper_id = ?", (p["id"],)
        ).fetchone()
    ]
    return {
        "status": "complete" if not pending and not uncategorized else "incomplete",
        "papers": len(papers),
        "pending_summaries": pending,
        "uncategorized": len(uncategorized),
        "needs_classification": uncategorized,
    }


def reading_completion_report(connection, identifiers) -> dict:
    """Verify complete, intact versions and topics for the explicit reading set."""
    identifiers = list(dict.fromkeys(
        db().require_string(item, "reading identifier") for item in identifiers
    ))
    if not identifiers:
        raise db().LiteratureError("Supply the refined reading list identifiers.", 2)
    results = []
    for identifier in identifiers:
        record = db().lookup_one(
            connection, identifier, topics=[], artifact_hash=None, include_digest=False
        )
        read = record["reuse_status"] == "reusable" and record.get("reading_status") in {"full", "visual"}
        classified = bool(record.get("collections"))
        results.append({
            "identifier": identifier,
            "paper_id": record.get("paper_id"),
            "title": record.get("title"),
            "complete_reading": read,
            "classified": classified,
            "reuse_status": record["reuse_status"],
            "reason": record.get("reason"),
            "version": record.get("version"),
        })
    pending = [item for item in results if not item["complete_reading"]]
    unclassified = [item["identifier"] for item in results if not item["classified"]]
    return {
        "status": "incomplete" if pending or unclassified else "complete",
        "requested_versions": len(results),
        "complete_readings": len(results) - len(pending),
        "pending_readings": len(pending),
        "needs_reading": pending,
        "needs_classification": unclassified,
        "results": results,
    }


def organize_batch(connection, raw) -> dict:
    """Apply reviewed topic memberships atomically and preserve earlier annotations."""
    records = raw.get("annotations") if isinstance(raw, dict) else raw
    if not isinstance(records, list) or not records:
        raise db().LiteratureError("Supply a nonempty annotations array.", 2)
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        for record in records:
            record = db().require_mapping(record, "annotation")
            db().reject_unknown_fields(
                record,
                "annotation",
                {"identifier", "collections", "tags", "roles", "note"},
            )
            identifier = db().require_string(
                record.get("identifier"), "annotation.identifier"
            )
            paper = db().find_paper_by_identifier(connection, identifier)
            if paper is None:
                raise db().LiteratureError(f"Unknown paper: {identifier}", 2)
            paths = db().string_list(
                record.get("collections"), "annotation.collections"
            )
            if not paths:
                raise db().LiteratureError(
                    "Every organized paper requires a topic collection.", 2
                )
            annotate_paper(
                connection,
                paper["id"],
                collections=paths,
                tags=db().string_list(record.get("tags", []), "annotation.tags"),
                roles=db().string_list(record.get("roles", []), "annotation.roles"),
                note=record.get("note", ""),
            )
    return {"status": "organized", "count": len(records)}


def collection_tree(connection) -> dict:
    nodes = {}
    roots = []
    for row in connection.execute("SELECT * FROM collections ORDER BY path"):
        node = dict(row)
        paper_ids = {
            item[0]
            for item in connection.execute(
                "SELECT DISTINCT paper_id FROM paper_collections WHERE collection_path = ? OR substr(collection_path, 1, ?) = ?",
                (row["path"], len(row["path"]) + 1, row["path"] + "/"),
            )
        }
        node.update(
            name=row["path"].rsplit("/", 1)[-1], count=len(paper_ids), children=[]
        )
        nodes[node["path"]] = node
    for node in nodes.values():
        if node["parent"] in nodes:
            nodes[node["parent"]]["children"].append(node)
        else:
            roots.append(node)
    return {"count": len(nodes), "collections": roots}


def matches_organization(
    connection, paper_id: int, *, collection=None, role=None, tag=None
) -> bool:
    if (
        collection
        and not connection.execute(
            "SELECT 1 FROM paper_collections WHERE paper_id = ? AND (collection_path = ? OR substr(collection_path, 1, ?) = ?)",
            (paper_id, collection, len(collection) + 1, collection + "/"),
        ).fetchone()
    ):
        return False
    for value, table, column in (
        (role, "paper_roles", "role"),
        (tag, "paper_tags", "tag"),
    ):
        if (
            value
            and not connection.execute(
                f"SELECT 1 FROM {table} WHERE paper_id = ? AND {column} = ?",
                (paper_id, value),
            ).fetchone()
        ):
            return False
    return True


def brief_search_results(
    connection,
    query: str,
    *,
    scope="all",
    mode="terms",
    topics=(),
    year_from=None,
    year_to=None,
):
    library = db()
    if scope == "fulltext" or mode == "fts" or topics:
        return []
    terms = library.query_terms(query, mode)
    results = []
    for paper in connection.execute("SELECT * FROM papers ORDER BY year DESC, title"):
        if year_from is not None and (
            paper["year"] is None or paper["year"] < year_from
        ):
            continue
        if year_to is not None and (paper["year"] is None or paper["year"] > year_to):
            continue
        brief = latest_brief(connection, paper["id"])
        metadata = "\n".join(
            str(paper[field] or "")
            for field in (
                "title",
                "authors_json",
                "abstract",
                "bibcode",
                "metadata_json",
            )
        )
        summary = (brief["summary"] + "\n" + brief["keywords_json"]) if brief else ""
        haystack = (
            metadata
            if scope == "metadata"
            else summary
            if scope == "summary"
            else metadata + "\n" + summary
        ).casefold()
        if not all(term.casefold() in haystack for term in terms):
            continue
        results.append(
            {
                "paper_id": paper["id"],
                "bibcode": paper["bibcode"],
                "title": paper["title"],
                "year": paper["year"],
                "pub": paper["pub"],
                "version_id": None,
                "version_kind": None,
                "reading_status": brief["evidence_level"] if brief else "metadata",
                "summary_status": "complete"
                if brief and brief["summary"]
                else "pending",
                "snippet": brief["summary"][:400]
                if brief and brief["summary"]
                else str(paper["abstract"] or "")[:400],
                "facets": [],
                "matched_facets": [],
                "matched_topics": [],
                "score": 0.0,
            }
        )
    return results


def browse(
    connection,
    fts5: bool,
    *,
    query="",
    collection=None,
    role=None,
    tag=None,
    status=None,
    limit=30,
    offset=0,
    scope="all",
    mode="terms",
    topics=(),
    year_from=None,
    year_to=None,
    sort="year-desc",
    uncategorized=False,
) -> dict:
    library = db()
    if sort not in {"year-desc", "year-asc", "title", "recent", "relevance"}:
        raise library.LiteratureError("Unknown sort order.", 2)
    total_papers = connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    candidates = (
        library.search_library(
            connection,
            fts5,
            query,
            scope=scope,
            mode=mode,
            topics=topics,
            year_from=year_from,
            year_to=year_to,
            limit=max(1, total_papers),
        )["results"]
        if query.strip()
        else library.list_library(
            connection,
            topics=topics,
            year_from=year_from,
            year_to=year_to,
            limit=max(1, total_papers),
        )["results"]
    )
    matches = []
    for item in candidates:
        paper_id = item["paper_id"]
        if not matches_organization(
            connection, paper_id, collection=collection, role=role, tag=tag
        ):
            continue
        if status and item.get("reading_status") != status:
            continue
        if (
            uncategorized
            and connection.execute(
                "SELECT 1 FROM paper_collections WHERE paper_id = ?", (paper_id,)
            ).fetchone()
        ):
            continue
        matches.append(item)
    paper_rows = {row["id"]: row for row in connection.execute("SELECT * FROM papers")}
    if sort == "title":
        matches.sort(key=lambda item: (item["title"].casefold(), item["paper_id"]))
    elif sort == "recent":
        matches.sort(
            key=lambda item: (
                paper_rows[item["paper_id"]]["created_at"],
                item["paper_id"],
            ),
            reverse=True,
        )
    elif sort in {"year-desc", "year-asc"}:
        matches.sort(
            key=lambda item: (
                item["year"] is None,
                -(item["year"] or 0) if sort == "year-desc" else (item["year"] or 0),
                item["title"].casefold(),
            )
        )
    results = []
    for item in matches[offset : offset + limit]:
        paper = connection.execute(
            "SELECT * FROM papers WHERE id = ?", (item["paper_id"],)
        ).fetchone()
        brief = brief_value(latest_brief(connection, item["paper_id"]))
        preferred = library.preferred_version(connection, item["paper_id"])
        digest_summary = ""
        if preferred:
            digest_row = connection.execute(
                "SELECT overview FROM digests WHERE version_id = ?", (preferred["id"],)
            ).fetchone()
            digest_summary = digest_row[0] if digest_row else ""
        results.append(
            {
                **item,
                "authors": json.loads(paper["authors_json"]),
                "identifier": paper["bibcode"]
                or paper["canonical_key"].split(":", 1)[1],
                "brief": brief,
                "snippet": item.get("snippet")
                or digest_summary
                or (brief or {}).get("summary", ""),
                "added_at": paper["created_at"],
                **paper_organization(connection, item["paper_id"]),
            }
        )
    return {"count": len(matches), "offset": offset, "limit": limit, "results": results}


def bibtex_escape(value: Any) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "$": r"\$",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(
        replacements.get(char, char) for char in " ".join(str(value).split())
    )


def citation_for_paper(connection, paper_id: int) -> dict:
    paper = connection.execute(
        "SELECT * FROM papers WHERE id = ?", (paper_id,)
    ).fetchone()
    if paper is None:
        raise db().LiteratureError("Unknown paper.", 2)
    cached = connection.execute(
        "SELECT * FROM citations WHERE paper_id = ?", (paper_id,)
    ).fetchone()
    if cached and cached["citekey"] == paper["bibcode"]:
        return dict(cached)
    brief = latest_brief(connection, paper_id)
    snapshot = json.loads(brief["source_json"]) if brief else {}
    metadata = json.loads(paper["metadata_json"])
    aliases = db().paper_aliases(connection, paper_id)
    doi = next(
        (
            item["value"]
            for item in aliases
            if item["kind"] == "doi"
            and not item["value"].lower().startswith("10.48550/")
        ),
        None,
    )
    arxiv_id = next(
        (item["value"] for item in aliases if item["kind"] == "arxiv"), None
    )
    key = paper["bibcode"] or (
        f"arxiv:{arxiv_id}" if arxiv_id else "doi:" + (doi or str(paper_id))
    )
    key = re.sub(r"[\s,{}\\]", "-", key)
    fields = {
        "title": paper["title"],
        "author": " and ".join(json.loads(paper["authors_json"])),
        "year": paper["year"],
        "journal": paper["pub"],
        "doi": doi,
    }
    for field in ("volume", "issue", "page", "eid"):
        value = snapshot.get(field) or metadata.get(field)
        fields[{"page": "pages", "issue": "number"}.get(field, field)] = (
            ", ".join(fulltext.list_value(value)) if isinstance(value, list) else value
        )
    if arxiv_id:
        fields.update(eprint=arxiv_id, archivePrefix="arXiv")
    fields["url"] = (
        "https://ui.adsabs.harvard.edu/abs/" + quote(paper["bibcode"], safe="")
        if paper["bibcode"]
        else "https://doi.org/" + quote(doi, safe="/")
        if doi
        else "https://arxiv.org/abs/" + quote(arxiv_id, safe="/")
    )
    entry_type = "article" if paper["pub"] and paper["doctype"] != "eprint" else "misc"
    body = ",\n".join(
        f"  {name} = {{{'{' + bibtex_escape(value) + '}' if name == 'title' else bibtex_escape(value)}}}"
        for name, value in fields.items()
        if value is not None and value != ""
    )
    return {
        "paper_id": paper_id,
        "citekey": key,
        "source": "stored-metadata",
        "bibtex": f"% Generated from stored metadata; verify journal details for submission.\n@{entry_type}{{{key},\n{body}\n}}\n",
        "fetched_at": None,
    }


def cache_ads_citation(connection, paper_id: int, token: str):
    paper = connection.execute(
        "SELECT bibcode FROM papers WHERE id = ?", (paper_id,)
    ).fetchone()
    if not paper or not paper["bibcode"]:
        return citation_for_paper(connection, paper_id)
    response = ads_api.request_api(
        "GET", "/export/bibtex/" + quote(paper["bibcode"], safe=""), token
    )
    text = response.body.decode("utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        text = payload.get("export", "")
    matches = re.findall(r"(?m)^\s*@\w+\s*\{\s*([^,\s]+)\s*,", text)
    if len(matches) != 1 or matches[0] != paper["bibcode"]:
        raise db().LiteratureError(
            "ADS citation response does not identify the requested bibcode.", 2
        )
    with connection:
        connection.execute(
            "INSERT INTO citations VALUES (?, ?, ?, ?, ?) ON CONFLICT(paper_id) DO UPDATE SET "
            "citekey=excluded.citekey, bibtex=excluded.bibtex, source=excluded.source, fetched_at=excluded.fetched_at",
            (paper_id, matches[0], text, "ads", fulltext.utc_now()),
        )
    return citation_for_paper(connection, paper_id)


def export_citations(connection, paper_ids) -> str:
    entries = [
        citation_for_paper(connection, paper_id)
        for paper_id in dict.fromkeys(paper_ids)
    ]
    if len({entry["citekey"] for entry in entries}) != len(entries):
        raise db().LiteratureError(
            "Selected citations contain duplicate keys. Refresh their ADS citations.", 2
        )
    return "\n".join(entry["bibtex"].strip() for entry in entries) + (
        "\n" if entries else ""
    )


def import_ads_citations(connection, text: str) -> dict:
    """Cache an unedited ADS BibTeX export after checking every record identity."""
    matches = list(re.finditer(r"(?m)^\s*@\w+\s*\{\s*([^,\s]+)\s*,", text))
    if not matches:
        raise db().LiteratureError("The ADS export contains no BibTeX entries.", 2)
    prepared = []
    seen = set()
    for index, match in enumerate(matches):
        key = match.group(1)
        paper = db().find_paper_by_identifier(connection, key)
        if paper is None or paper["bibcode"] != key or key in seen:
            raise db().LiteratureError(
                f"ADS citation does not match one current library bibcode: {key}", 2
            )
        seen.add(key)
        entry = text[
            match.start() : matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        ].strip()
        if not entry.endswith("}"):
            raise db().LiteratureError(f"Incomplete BibTeX entry: {key}", 2)
        depth = 0
        escaped = False
        for char in entry:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth < 0:
                    break
        if depth != 0:
            raise db().LiteratureError(f"Unbalanced BibTeX entry: {key}", 2)
        prepared.append((paper["id"], key, entry + "\n", "ads", fulltext.utc_now()))
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT INTO citations VALUES (?, ?, ?, ?, ?) ON CONFLICT(paper_id) DO UPDATE SET "
            "citekey=excluded.citekey, bibtex=excluded.bibtex, source=excluded.source, fetched_at=excluded.fetched_at",
            prepared,
        )
    return {"status": "cached", "count": len(prepared), "source": "ads"}


def record_version_label(connection, version_id: int, manifest: dict):
    selected = manifest.get("selected") or {}
    for value in (
        selected.get("final_url"),
        (selected.get("candidate") or {}).get("url"),
    ):
        arxiv_id = fulltext.arxiv_id_from_value(str(value or ""))
        if arxiv_id and re.search(r"v\d+$", arxiv_id):
            connection.execute(
                "INSERT OR IGNORE INTO version_labels VALUES (?, ?)",
                (version_id, arxiv_id.casefold()),
            )


def add_parser_commands(subparsers):
    capture = subparsers.add_parser(
        "capture", help="store an ADS result JSON with pending source-based summaries"
    )
    capture.add_argument("--results", required=True)
    capture.add_argument("--query", default="imported search results")
    capture.add_argument("--collection", action="append", default=[])
    capture.add_argument("--role", choices=WRITING_ROLES, action="append", default=[])
    pending = subparsers.add_parser(
        "pending", help="list source snapshots that need agent-authored summaries"
    )
    pending.add_argument("--run-id", type=ads_api.positive_int)
    pending.add_argument("--limit", type=ads_api.positive_int, default=50)
    pending.add_argument("--offset", type=ads_api.nonnegative_int, default=0)
    check = subparsers.add_parser(
        "check", help="check summary and topic classification completion"
    )
    check.add_argument("--run-id", type=ads_api.positive_int)
    reading = subparsers.add_parser(
        "reading-check", help="verify full reading, artifact integrity, and topics for a refined list"
    )
    reading.add_argument("identifiers", nargs="*")
    reading.add_argument("--identifiers-file", help="UTF-8 file with one exact paper identifier per line")
    organize = subparsers.add_parser(
        "organize", help="apply a reviewed batch of topic classifications and tags"
    )
    organize.add_argument("--annotations", required=True)
    import_cites = subparsers.add_parser(
        "import-citations",
        help="cache an unedited ADS BibTeX export for existing papers",
    )
    import_cites.add_argument("--bibtex", required=True)
    summaries = subparsers.add_parser(
        "summarize",
        help="save a batch of agent-authored abstract or metadata summaries",
    )
    summaries.add_argument("--summaries", required=True)
    annotate = subparsers.add_parser(
        "annotate",
        help="add collection memberships, tags, writing roles, and personal notes",
    )
    annotate.add_argument("identifier")
    annotate.add_argument("--collection", action="append", default=[])
    annotate.add_argument("--tag", action="append", default=[])
    annotate.add_argument("--role", action="append", choices=WRITING_ROLES, default=[])
    annotate.add_argument("--note", default="")
    collections = subparsers.add_parser(
        "collections", help="show the nested personal collection tree"
    )
    collections.add_argument("--create")
    collections.add_argument("--description", default="")
    runs = subparsers.add_parser(
        "runs", help="show persisted search scope and summary completion"
    )
    runs.add_argument("--limit", type=ads_api.positive_int, default=20)
    cites = subparsers.add_parser(
        "citations", help="export cached BibTeX or fetch official ADS entries"
    )
    cites.add_argument("identifiers", nargs="*")
    cites.add_argument("--collection")
    cites.add_argument("--all", action="store_true")
    cites.add_argument("--fetch", action="store_true")
    cites.add_argument("--output")
    serve = subparsers.add_parser(
        "serve", help="browse the personal library on localhost"
    )
    serve.add_argument("--port", type=ads_api.nonnegative_int, default=8765)


def execute_command(args, connection, fts5, library_dir, environ, stdin):
    library = db()
    if args.command == "capture":
        payload = library.load_json(args.results, stdin)
        if isinstance(payload, dict) and "response" not in payload:
            records = payload.get("results", [payload])
            if isinstance(records, list):
                payload = {"response": {"numFound": len(records), "docs": records}}
        return capture_search(
            connection,
            fts5,
            payload,
            query=args.query,
            parameters={"source": "import"},
            collections=args.collection,
            roles=args.role,
        )
    if args.command == "pending":
        return pending_summaries(
            connection, run_id=args.run_id, limit=args.limit, offset=args.offset
        )
    if args.command == "summarize":
        return summarize(connection, library.load_json(args.summaries, stdin))
    if args.command == "check":
        return completion_report(connection, run_id=args.run_id)
    if args.command == "reading-check":
        identifiers = list(args.identifiers)
        if args.identifiers_file:
            identifiers.extend(
                line.strip()
                for line in Path(args.identifiers_file).read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            )
        return reading_completion_report(connection, identifiers)
    if args.command == "organize":
        return organize_batch(connection, library.load_json(args.annotations, stdin))
    if args.command == "import-citations":
        return import_ads_citations(
            connection, Path(args.bibtex).read_text(encoding="utf-8-sig")
        )
    if args.command == "annotate":
        paper = library.find_paper_by_identifier(connection, args.identifier)
        if paper is None:
            raise library.LiteratureError(
                "Capture this paper before adding annotations.", 2
            )
        with connection:
            annotate_paper(
                connection,
                paper["id"],
                collections=args.collection,
                tags=args.tag,
                roles=args.role,
                note=args.note,
            )
        return {
            "status": "annotated",
            "paper_id": paper["id"],
            **paper_organization(connection, paper["id"]),
        }
    if args.command == "collections":
        if args.create:
            with connection:
                add_collection(connection, args.create, args.description)
        return collection_tree(connection)
    if args.command == "runs":
        rows = connection.execute(
            "SELECT r.*, COUNT(h.paper_id) AS captured, SUM(CASE WHEN b.summary = '' THEN 1 ELSE 0 END) AS pending "
            "FROM search_runs r LEFT JOIN search_hits h ON h.run_id = r.id LEFT JOIN briefs b ON b.id = h.brief_id "
            "GROUP BY r.id ORDER BY r.id DESC LIMIT ?",
            (args.limit,),
        )
        return {"results": [dict(row) for row in rows]}
    if args.command == "citations":
        if sum((bool(args.identifiers), bool(args.collection), args.all)) != 1:
            raise library.LiteratureError(
                "Select identifiers, --collection, or --all for citation export.", 2
            )
        if args.identifiers:
            papers = [
                library.find_paper_by_identifier(connection, value)
                for value in args.identifiers
            ]
            if any(paper is None for paper in papers):
                raise library.LiteratureError(
                    "Every selected paper must exist in the local library.", 2
                )
            paper_ids = [paper["id"] for paper in papers]
        else:
            paper_ids = [
                row[0]
                for row in connection.execute("SELECT id FROM papers ORDER BY id")
                if matches_organization(connection, row[0], collection=args.collection)
            ]
        if args.fetch:
            token = ads_api.resolve_token(environ)
            for paper_id in dict.fromkeys(paper_ids):
                cached = connection.execute(
                    "SELECT 1 FROM citations c JOIN papers p ON p.id = c.paper_id WHERE c.paper_id = ? AND c.source = ? AND c.citekey = p.bibcode",
                    (paper_id, "ads"),
                ).fetchone()
                if not cached:
                    cache_ads_citation(connection, paper_id, token)
        text = export_citations(connection, paper_ids)
        if args.output:
            output = Path(args.output).expanduser().resolve()
            if library.path_is_within(output, library_dir):
                raise library.LiteratureError(
                    "Citation output must be outside the managed library.", 2
                )
            fulltext.atomic_write_text(output, text)
            return {
                "status": "exported",
                "count": len(set(paper_ids)),
                "path": str(output),
            }
        return text
    raise library.LiteratureError("Unsupported catalog command.", 2)
