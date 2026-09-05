"""Read-only localhost interface for the personal literature library."""

from __future__ import annotations

import json
import re
import socket
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import fulltext
import library_catalog
import literature_db

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "library"


class LibraryHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR allows two servers to bind the same listening port.
    # Exclusive binding makes launcher ownership and collision handling reliable.
    allow_reuse_address = not hasattr(socket, "SO_EXCLUSIVEADDRUSE")

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(library_dir: Path, port: int = 8765) -> ThreadingHTTPServer:
    if not 0 <= port <= 65535:
        raise literature_db.LiteratureError("Port must be between 0 and 65535.", 2)
    # Fail early for an incompatible existing library. A fresh install can browse
    # an empty library without creating a database.
    connection, _fts = literature_db.connect_library_readonly(
        library_dir, allow_missing=True
    )
    connection.close()

    class Handler(BaseHTTPRequestHandler):
        server_version = "NASA-ADS-Library"

        def log_message(self, _format, *_args):
            return

        def send_content(
            self, body: bytes, content_type: str, status=200, filename=None
        ):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
            if filename:
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, payload, status=200):
            self.send_content(
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
                status,
            )

        def do_GET(self):
            authority = f"127.0.0.1:{self.server.server_port}"
            allowed = {authority, f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "") not in allowed:
                self.send_json({"error": "Localhost access is required."}, 403)
                return
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + value for value in allowed}:
                self.send_json({"error": "Cross-origin access is disabled."}, 403)
                return
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.send_json({"error": "Cross-site access is disabled."}, 403)
                return
            url = urlsplit(self.path)
            files = {
                "/": ("index.html", "text/html"),
                "/app.js": ("app.js", "text/javascript"),
                "/style.css": ("style.css", "text/css"),
            }
            if url.path in files:
                filename, content_type = files[url.path]
                self.send_content(
                    (ASSETS / filename).read_bytes(), content_type + "; charset=utf-8"
                )
                return
            connection = None
            try:
                params = parse_qs(url.query, max_num_fields=30)

                def value(key, default=None):
                    items = params.get(key, [default])
                    if len(items) != 1:
                        raise ValueError("Each parameter accepts one value.")
                    return items[0]

                def integer(key, default, maximum=1000000000):
                    result = int(value(key, str(default)))
                    if not 0 <= result <= maximum:
                        raise ValueError("Parameter is outside its permitted range.")
                    return result

                connection, fts5 = literature_db.connect_library_readonly(
                    library_dir, allow_missing=True
                )
                if url.path == "/api/papers":
                    query = value("query", "")
                    if len(query) > 1000:
                        raise ValueError("Search query is too long.")
                    scope = value("scope", "all")
                    if scope not in literature_db.SCOPE_COLUMNS:
                        raise ValueError("Unknown search scope.")
                    result = library_catalog.browse(
                        connection,
                        fts5,
                        query=query,
                        scope=scope,
                        collection=value("collection"),
                        role=value("role"),
                        tag=value("tag"),
                        status=value("status"),
                        limit=max(1, integer("limit", 30, 100)),
                        offset=integer("offset", 0),
                        sort=value("sort", "year-desc"),
                        year_from=integer("year_from", 0, 9999) or None,
                        year_to=integer("year_to", 0, 9999) or None,
                        uncategorized=value("uncategorized", "0") == "1",
                    )
                elif url.path == "/api/collections":
                    result = library_catalog.collection_tree(connection)
                elif url.path == "/api/stats":
                    result = literature_db.library_stats(connection, fts5, library_dir)
                    result["pending_summaries"] = library_catalog.pending_summaries(
                        connection, limit=1
                    )["count"]
                    result["uncategorized"] = library_catalog.completion_report(
                        connection
                    )["uncategorized"]
                    result["roles"] = {
                        row[0]: row[1]
                        for row in connection.execute(
                            "SELECT role, COUNT(*) FROM paper_roles GROUP BY role"
                        )
                    }
                    result["year_range"] = list(
                        connection.execute(
                            "SELECT MIN(year), MAX(year) FROM papers"
                        ).fetchone()
                    )
                    result["read_only"] = True
                elif url.path == "/api/paper":
                    paper = connection.execute(
                        "SELECT * FROM papers WHERE id = ?", (integer("id", 0),)
                    ).fetchone()
                    if paper is None:
                        self.send_json({"error": "Paper not found."}, 404)
                        return
                    identifier = (
                        paper["bibcode"] or paper["canonical_key"].split(":", 1)[1]
                    )
                    result = literature_db.show_paper(
                        connection, identifier, include_fulltext=False
                    )
                    preferred = literature_db.preferred_version(connection, paper["id"])
                    result["preferred_version_id"] = (
                        preferred["id"] if preferred else None
                    )
                elif url.path == "/api/citations":
                    raw_ids = value("ids", "")
                    if value("view") == "filtered" and not raw_ids:
                        query = value("query", "")
                        scope = value("scope", "all")
                        if (
                            len(query) > 1000
                            or scope not in literature_db.SCOPE_COLUMNS
                        ):
                            raise ValueError("Invalid citation search scope.")
                        selected = library_catalog.browse(
                            connection,
                            fts5,
                            query=query,
                            scope=scope,
                            collection=value("collection"),
                            role=value("role"),
                            tag=value("tag"),
                            status=value("status"),
                            limit=2001,
                            year_from=integer("year_from", 0, 9999) or None,
                            year_to=integer("year_to", 0, 9999) or None,
                            uncategorized=value("uncategorized", "0") == "1",
                        )
                        if not 1 <= selected["count"] <= 2000:
                            raise ValueError(
                                "Select between 1 and 2000 papers for export."
                            )
                        raw_ids = ",".join(
                            str(item["paper_id"]) for item in selected["results"]
                        )
                    if not re.fullmatch(r"\d+(?:,\d+){0,1999}", raw_ids):
                        raise ValueError("Select 1-2000 paper IDs.")
                    ids = [int(item) for item in raw_ids.split(",")]
                    body = library_catalog.export_citations(connection, ids).encode(
                        "utf-8"
                    )
                    self.send_content(
                        body, "text/plain; charset=utf-8", filename="literature.bib"
                    )
                    return
                elif url.path == "/api/artifact":
                    version = connection.execute(
                        "SELECT * FROM versions WHERE id = ?", (integer("version", 0),)
                    ).fetchone()
                    kind = value("kind", "text")
                    if version is None or kind not in {"text", "article"}:
                        raise ValueError(
                            "Choose an existing article version and artifact kind."
                        )
                    path_value = (
                        version["text_path"]
                        if kind == "text"
                        else version["artifact_path"]
                    )
                    path = Path(path_value or "")
                    if (
                        not path_value
                        or not literature_db.path_is_within(
                            path, library_dir / "objects"
                        )
                        or not path.is_file()
                    ):
                        raise ValueError("Stored artifact is unavailable.")
                    expected = (
                        version["text_sha256"] if kind == "text" else version["sha256"]
                    )
                    if fulltext.sha256_file(path) != expected:
                        raise ValueError(
                            "Stored artifact failed integrity verification."
                        )
                    extension = ".txt" if kind == "text" else path.suffix
                    content_type = (
                        "application/pdf"
                        if extension == ".pdf"
                        else "text/plain; charset=utf-8"
                    )
                    self.send_content(
                        path.read_bytes(),
                        content_type,
                        filename=f"article-{version['id']}{extension}",
                    )
                    return
                else:
                    self.send_json({"error": "Page not found."}, 404)
                    return
                self.send_json(result)
            except (
                ValueError,
                literature_db.LiteratureError,
                fulltext.FullTextError,
            ) as exc:
                self.send_json({"error": str(exc)}, 400)
            except (sqlite3.Error, OSError):
                self.send_json(
                    {
                        "error": "The local library is unavailable. Run the library audit for details."
                    },
                    503,
                )
            finally:
                if connection is not None:
                    connection.close()

    server = LibraryHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve(library_dir: Path, port: int, stdout):
    server = make_server(library_dir, port)
    stdout.write(
        literature_db.pretty_json(
            {
                "status": "serving",
                "url": f"http://127.0.0.1:{server.server_port}",
                "library_dir": str(library_dir),
                "read_only": True,
            }
        )
    )
    stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
