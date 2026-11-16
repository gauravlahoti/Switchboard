from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.store import store

ALLOW_LIST = [
    "search_kb",
    "lookup_user",
    "create_ticket",
    "reset_password",
    "query_logs",
    "restart_service",
    "grant_access",
]
RISKY_TOOLS = {"restart_service", "grant_access"}


def search_kb(query: str) -> list[dict]:
    words = [w.lower() for w in query.split() if len(w) > 2]
    with store.conn() as con:
        rows = con.execute("SELECT id, title, body, tags FROM kb_articles").fetchall()
    results = []
    for row in rows:
        text = f"{row['title']} {row['body']} {row['tags']}".lower()
        if any(w in text for w in words):
            results.append({
                "id": row["id"],
                "title": row["title"],
                "snippet": row["body"][:200],
                "tags": row["tags"],
            })
    return results[:3]


def lookup_user(identifier: str) -> dict | None:
    ident = identifier.lower()
    with store.conn() as con:
        row = con.execute(
            "SELECT * FROM users WHERE LOWER(id)=? OR LOWER(name)=? OR LOWER(email)=?",
            (ident, ident, ident),
        ).fetchone()
    return dict(row) if row else None


def create_ticket(requester_id: str, title: str, priority: str = "medium") -> dict:
    tid = f"t{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat()
    with store.conn() as con:
        con.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?)",
            (tid, now, requester_id, title, "open", priority),
        )
    return {"id": tid, "requester_id": requester_id, "title": title, "status": "open", "priority": priority}


def reset_password(user_id: str) -> dict:
    with store.conn() as con:
        con.execute("UPDATE users SET password_locked=0 WHERE id=?", (user_id,))
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise ValueError(f"User {user_id!r} not found")
    return dict(row)


def query_logs(
    service: str | None = None, level: str | None = None, limit: int = 20
) -> list[dict]:
    sql = "SELECT * FROM service_logs WHERE 1=1"
    params: list[Any] = []
    if service:
        sql += " AND LOWER(service)=?"
        params.append(service.lower())
    if level:
        sql += " AND UPPER(level)=?"
        params.append(level.upper())
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(min(limit, 100))
    with store.conn() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def restart_service(service: str) -> dict:
    raise RuntimeError(
        "restart_service is disabled until the sprint-2 safety gate."
        " Register the tool but never call it in sprint 1."
    )


def grant_access(user_id: str, resource: str, role: str) -> dict:
    raise RuntimeError(
        "grant_access is disabled until the sprint-2 safety gate."
        " Register the tool but never call it in sprint 1."
    )


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in ALLOW_LIST:
        raise ValueError(f"Tool {name!r} is not in the allow-list")
    dispatch = {
        "search_kb":       lambda a: search_kb(**a),
        "lookup_user":     lambda a: lookup_user(**a),
        "create_ticket":   lambda a: create_ticket(**a),
        "reset_password":  lambda a: reset_password(**a),
        "query_logs":      lambda a: query_logs(**a),
        "restart_service": lambda a: restart_service(**a),
        "grant_access":    lambda a: grant_access(**a),
    }
    result = dispatch[name](arguments)
    return {"tool": name, "result": result}
