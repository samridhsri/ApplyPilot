"""ApplyPilot Dashboard Backend Server.

Lightweight, dependency-free HTTP API server built with Python's standard library
http.server. Provides REST APIs for the React dashboard and serves static assets.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from applypilot.config import APP_DIR, DB_PATH, load_env, read_text_safe
from applypilot.database import get_connection, get_stats, init_db

log = logging.getLogger(__name__)

# Base path for built static assets
DASHBOARD_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"


class DashboardAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for ApplyPilot REST API and frontend assets."""

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._send_json({"error": message}, status=status)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # API routing
        if path == "/api/stats":
            self.handle_get_stats()
        elif path == "/api/jobs":
            self.handle_get_jobs(query)
        elif path == "/api/job":
            self.handle_get_job(query)
        elif path == "/api/sites":
            self.handle_get_sites()
        elif path.startswith("/api/"):
            self._send_error("API endpoint not found", HTTPStatus.NOT_FOUND)
        else:
            # Static file serving
            self.handle_serve_static(path)

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Read JSON body
        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            raw_body = self.rfile.read(content_length)
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except Exception as e:
                self._send_error(f"Invalid JSON body: {e}")
                return

        if path == "/api/jobs/status":
            self.handle_update_status(body)
        elif path == "/api/jobs/reset-all-scores":
            self.handle_reset_all_scores()
        else:
            self._send_error("API endpoint not found", HTTPStatus.NOT_FOUND)

    # ── Handlers ──────────────────────────────────────────────────────────

    def handle_get_stats(self) -> None:
        conn = get_connection()
        stats = get_stats(conn=conn)

        # Additional detailed breakdowns
        try:
            site_breakdown = conn.execute("""
                SELECT site, COUNT(*) as count,
                       SUM(CASE WHEN fit_score >= 7 THEN 1 ELSE 0 END) as high_fit,
                       SUM(CASE WHEN applied_at IS NOT NULL THEN 1 ELSE 0 END) as applied
                FROM jobs
                GROUP BY site
                ORDER BY count DESC
            """).fetchall()

            status_breakdown = conn.execute("""
                SELECT 
                    SUM(CASE WHEN applied_at IS NOT NULL THEN 1 ELSE 0 END) as applied,
                    SUM(CASE WHEN apply_status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN tailored_resume_path IS NOT NULL AND applied_at IS NULL THEN 1 ELSE 0 END) as ready_to_apply,
                    SUM(CASE WHEN fit_score >= 7 AND tailored_resume_path IS NULL THEN 1 ELSE 0 END) as eligible_for_tailor,
                    SUM(CASE WHEN fit_score IS NOT NULL THEN 1 ELSE 0 END) as scored,
                    SUM(CASE WHEN fit_score IS NULL THEN 1 ELSE 0 END) as unscored
                FROM jobs
            """).fetchone()

            stats["sites"] = [
                {"site": r["site"] or "Unknown", "count": r["count"], "high_fit": r["high_fit"], "applied": r["applied"]}
                for r in site_breakdown
            ]
            stats["status_counts"] = dict(status_breakdown) if status_breakdown else {}
        except Exception as e:
            log.exception("Error getting detailed stats: %s", e)

        self._send_json(stats)

    def handle_get_sites(self) -> None:
        conn = get_connection()
        rows = conn.execute("SELECT DISTINCT site FROM jobs WHERE site IS NOT NULL AND site != '' ORDER BY site ASC").fetchall()
        sites = [r[0] for r in rows]
        self._send_json({"sites": sites})

    def handle_get_jobs(self, query: dict[str, list[str]]) -> None:
        search = query.get("search", [""])[0].strip()
        site = query.get("site", [""])[0].strip()
        status_filter = query.get("status", ["all"])[0].strip()
        min_score = query.get("min_score", [""])[0]
        max_score = query.get("max_score", [""])[0]
        sort_by = query.get("sort_by", ["score"])[0].strip()
        order = query.get("order", ["desc"])[0].strip().lower()
        if order not in ("asc", "desc"):
            order = "desc"

        page = max(1, int(query.get("page", ["1"])[0]))
        limit = max(1, min(500, int(query.get("limit", ["100"])[0])))
        offset = (page - 1) * limit

        where_clauses = ["1=1"]
        params = []

        if search:
            search_param = f"%{search}%"
            where_clauses.append(
                "(title LIKE ? OR site LIKE ? OR location LIKE ? OR description LIKE ? OR score_reasoning LIKE ?)"
            )
            params.extend([search_param, search_param, search_param, search_param, search_param])

        if site and site != "all":
            where_clauses.append("site = ?")
            params.append(site)

        if min_score:
            try:
                where_clauses.append("fit_score >= ?")
                params.append(int(min_score))
            except ValueError:
                pass

        if max_score:
            try:
                where_clauses.append("fit_score <= ?")
                params.append(int(max_score))
            except ValueError:
                pass

        # Status filter logic
        if status_filter == "applied":
            where_clauses.append("applied_at IS NOT NULL")
        elif status_filter == "ready":
            where_clauses.append("tailored_resume_path IS NOT NULL AND applied_at IS NULL")
        elif status_filter == "tailored":
            where_clauses.append("tailored_resume_path IS NOT NULL")
        elif status_filter == "high_fit":
            where_clauses.append("fit_score >= 7")
        elif status_filter == "failed":
            where_clauses.append("apply_status = 'failed'")
        elif status_filter == "unscored":
            where_clauses.append("fit_score IS NULL")

        where_sql = " AND ".join(where_clauses)

        # Sorting column mapping
        sort_col_map = {
            "score": "fit_score",
            "date": "discovered_at",
            "title": "title",
            "site": "site",
            "applied": "applied_at",
        }
        sort_col = sort_col_map.get(sort_by, "fit_score")
        
        # When sorting by score desc, put nulls last
        if sort_col == "fit_score" and order == "desc":
            order_by = "CASE WHEN fit_score IS NULL THEN 1 ELSE 0 END, fit_score DESC, discovered_at DESC"
        elif sort_col == "fit_score" and order == "asc":
            order_by = "CASE WHEN fit_score IS NULL THEN 0 ELSE 1 END, fit_score ASC, discovered_at DESC"
        else:
            order_by = f"{sort_col} {order.upper()}, discovered_at DESC"

        conn = get_connection()

        # Count total matching
        count_sql = f"SELECT COUNT(*) FROM jobs WHERE {where_sql}"
        total_count = conn.execute(count_sql, params).fetchone()[0]

        # Fetch page items
        query_sql = f"""
            SELECT url, title, salary, description, location, site, strategy,
                   discovered_at, full_description, application_url, detail_error,
                   fit_score, score_reasoning, scored_at, tailored_resume_path,
                   tailored_at, cover_letter_path, cover_letter_at, applied_at,
                   apply_status, apply_error, apply_attempts
            FROM jobs
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, params + [limit, offset]).fetchall()
        jobs = [dict(r) for r in rows]

        self._send_json({
            "jobs": jobs,
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit,
        })

    def handle_get_job(self, query: dict[str, list[str]]) -> None:
        url = query.get("url", [""])[0]
        if not url:
            self._send_error("Missing job url parameter")
            return

        conn = get_connection()
        row = conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
        if not row:
            self._send_error("Job not found", HTTPStatus.NOT_FOUND)
            return

        job = dict(row)

        # Read tailored resume text if available
        resume_content = None
        if job.get("tailored_resume_path"):
            txt_path = Path(job["tailored_resume_path"]).with_suffix(".txt")
            if txt_path.exists():
                try:
                    resume_content = read_text_safe(txt_path)
                except Exception as e:
                    resume_content = f"Error reading resume: {e}"

        # Read cover letter text if available
        cover_content = None
        if job.get("cover_letter_path"):
            cl_path = Path(job["cover_letter_path"])
            cl_txt = cl_path.with_suffix(".txt")
            if cl_txt.exists():
                try:
                    cover_content = read_text_safe(cl_txt)
                except Exception as e:
                    cover_content = f"Error reading cover letter: {e}"

        job["tailored_resume_text"] = resume_content
        job["cover_letter_text"] = cover_content

        self._send_json(job)

    def handle_update_status(self, body: dict[str, Any]) -> None:
        url = body.get("url")
        status = body.get("status")  # 'applied', 'failed', 'reset', 'pending'
        reason = body.get("reason", "")

        if not url or not status:
            self._send_error("Missing url or status parameter")
            return

        conn = get_connection()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        if status == "applied":
            conn.execute(
                "UPDATE jobs SET applied_at = ?, apply_status = 'applied', apply_error = NULL WHERE url = ?",
                (now, url),
            )
        elif status == "failed":
            conn.execute(
                "UPDATE jobs SET apply_status = 'failed', apply_error = ? WHERE url = ?",
                (reason or "Manual marked as failed", url),
            )
        elif status in ("reset", "pending"):
            conn.execute(
                "UPDATE jobs SET applied_at = NULL, apply_status = NULL, apply_error = NULL, apply_attempts = 0 WHERE url = ?",
                (url,),
            )
        elif status == "reset_score":
            conn.execute(
                "UPDATE jobs SET fit_score = NULL, score_reasoning = NULL, scored_at = NULL WHERE url = ?",
                (url,),
            )

        conn.commit()
        self._send_json({"status": "ok", "url": url, "updated_to": status})

    def handle_reset_all_scores(self) -> None:
        conn = get_connection()
        count = conn.execute("UPDATE jobs SET fit_score = NULL, score_reasoning = NULL, scored_at = NULL").rowcount
        conn.commit()
        self._send_json({"status": "ok", "reset_count": count})

    def handle_serve_static(self, path: str) -> None:
        if not DASHBOARD_DIST_DIR.exists():
            msg = """<!DOCTYPE html>
<html>
<head><title>ApplyPilot Dashboard</title><style>body{background:#090d16;color:#e2e8f0;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column}a{color:#38bdf8}</style></head>
<body>
  <h1>ApplyPilot React Dashboard Backend Running</h1>
  <p>The frontend bundle was not found in <code>dashboard/dist</code>.</p>
  <p>Run <code>npm run dev</code> inside the <code>dashboard</code> directory to develop or <code>npm run build</code> to bundle.</p>
</body>
</html>"""
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg.encode("utf-8"))
            return

        rel_path = path.lstrip("/") or "index.html"
        file_path = (DASHBOARD_DIST_DIR / rel_path).resolve()

        if not str(file_path).startswith(str(DASHBOARD_DIST_DIR)):
            self._send_error("Forbidden", HTTPStatus.FORBIDDEN)
            return

        if not file_path.exists() or file_path.is_dir():
            file_path = DASHBOARD_DIST_DIR / "index.html"

        if not file_path.exists():
            self._send_error("File not found", HTTPStatus.NOT_FOUND)
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        try:
            content = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error(f"Error reading file: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def run_server(port: int = 8000, host: str = "127.0.0.1") -> None:
    """Start the ApplyPilot Dashboard server."""
    load_env()
    init_db()

    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, DashboardAPIHandler)
    log.info("ApplyPilot Dashboard server running at http://%s:%d", host, port)
    print(f"\n  [ApplyPilot React Dashboard] running at: http://{host}:{port}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping dashboard server...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
