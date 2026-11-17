from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "fixtures" / "synthetic.db"
TABLES = ("users", "tickets", "kb_articles", "service_logs", "service_state", "user_roles")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SyntheticStore:
    """Synthetic directory, knowledge base and ticket queue. Reseeded on every start."""

    def __init__(self, path: Path = DB_PATH) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.reset()

    def conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._path)
        con.row_factory = sqlite3.Row
        return con

    def reset(self) -> None:
        with self.conn() as con:
            for table in TABLES:
                con.execute(f"DROP TABLE IF EXISTS {table}")
            self._create_tables(con)
            self._seed(con)

    # ---- reads and writes used by the tools ----

    def get_user(self, identifier: str) -> dict[str, Any] | None:
        ident = identifier.strip().lower()
        with self.conn() as con:
            row = con.execute(
                "SELECT * FROM users WHERE LOWER(id)=? OR LOWER(name)=? OR LOWER(email)=?",
                (ident, ident, ident),
            ).fetchone()
        return dict(row) if row else None

    def kb_titles(self) -> list[str]:
        with self.conn() as con:
            return [r["title"] for r in con.execute("SELECT title FROM kb_articles ORDER BY id").fetchall()]

    def search_kb(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        words = {w.lower().strip(".,?!'\"") for w in query.split() if len(w) > 2}
        with self.conn() as con:
            rows = con.execute("SELECT id, title, body, tags FROM kb_articles").fetchall()
        scored = []
        for row in rows:
            title, tags = row["title"].lower(), row["tags"].lower()
            body = row["body"].lower()
            score = sum(3 for w in words if w in title or w in tags) + sum(1 for w in words if w in body)
            if score:
                scored.append((score, dict(row)))
        scored.sort(key=lambda s: s[0], reverse=True)
        return [a for _, a in scored[:limit]]

    def unlock_account(self, user_id: str) -> bool:
        with self.conn() as con:
            row = con.execute("SELECT password_locked FROM users WHERE id=?", (user_id,)).fetchone()
            if row is None:
                raise KeyError(user_id)
            was_locked = bool(row["password_locked"])
            con.execute("UPDATE users SET password_locked=0 WHERE id=?", (user_id,))
        return was_locked

    def recent_open_ticket(self, requester_id: str, title: str, minutes: int = 10) -> dict[str, Any] | None:
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        with self.conn() as con:
            row = con.execute(
                "SELECT * FROM tickets WHERE requester_id=? AND LOWER(title)=? AND status='open' AND created_at>=?",
                (requester_id, title.strip().lower(), since),
            ).fetchone()
        return dict(row) if row else None

    def add_ticket(self, **fields: Any) -> dict[str, Any]:
        ticket = {"id": f"t{uuid.uuid4().hex[:6]}", "created_at": _now(), "status": "open", **fields}
        cols = ", ".join(ticket)
        marks = ", ".join("?" for _ in ticket)
        with self.conn() as con:
            con.execute(f"INSERT INTO tickets ({cols}) VALUES ({marks})", tuple(ticket.values()))
        return ticket

    # ---- schema and seed ----

    def _create_tables(self, con: sqlite3.Connection) -> None:
        con.executescript("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY, name TEXT, email TEXT,
                department TEXT, role TEXT,
                is_mfa_enabled INTEGER DEFAULT 1,
                password_locked INTEGER DEFAULT 0
            );
            CREATE TABLE tickets (
                id TEXT PRIMARY KEY, created_at TEXT, requester_id TEXT,
                title TEXT, details TEXT, status TEXT, priority TEXT,
                category TEXT, queue TEXT, created_by TEXT, run_id TEXT
            );
            CREATE TABLE kb_articles (
                id TEXT PRIMARY KEY, title TEXT, body TEXT, tags TEXT
            );
            CREATE TABLE service_logs (
                id TEXT PRIMARY KEY, ts TEXT, service TEXT, level TEXT, message TEXT
            );
            CREATE TABLE service_state (
                service TEXT PRIMARY KEY, status TEXT, last_restart TEXT
            );
            CREATE TABLE user_roles (
                user_id TEXT, resource TEXT, role TEXT
            );
        """)

    def _seed(self, con: sqlite3.Connection) -> None:
        now = _now()
        con.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?)", [
            ("u001", "Alice Chen", "alice@acme.corp", "Engineering", "user", 1, 0),
            ("u002", "Bob Patel", "bob@acme.corp", "Finance", "admin", 1, 0),
            ("u003", "Carol Wu", "carol@acme.corp", "Finance", "user", 1, 1),
            ("u004", "Dan Kim", "dan@acme.corp", "IT", "admin", 1, 0),
            ("u005", "Eve Torres", "eve@acme.corp", "Sales", "user", 0, 0),
            ("u006", "John Reyes", "john@acme.corp", "Operations", "manager", 1, 0),
        ])
        con.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
            ("t001", now, "u003", "Password reset request", "Locked out after travel.", "closed", "high",
             "password", "Identity and Access", "u003", None),
            ("t002", now, "u001", "VPN keeps dropping", "Drops every 10 minutes on home WiFi.", "open", "medium",
             "network", "Network", "u001", None),
            ("t003", now, "u002", "Checkout timeouts in prod", "Orders time out after 5 seconds.", "open", "critical",
             "software", "Applications", "u002", None),
        ])
        con.executemany("INSERT INTO kb_articles VALUES (?,?,?,?)", [
            ("kb001", "VPN Setup Guide",
             "Connect using GlobalProtect. Download it from it.acme.corp/vpn and sign in with your SSO credentials. "
             "For Error 809 check that your firewall allows UDP 500 and 4500. If the VPN drops, switch off WiFi "
             "power saving and try a wired or phone hotspot connection.",
             "vpn,network,setup,wifi,dropping"),
            ("kb002", "Password Reset Procedure",
             "Go to accounts.acme.corp/reset and enter your work email. A one-time code is sent to your enrolled "
             "authenticator. If your account is locked, the reset also unlocks it. If you cannot receive the code, "
             "call the IT helpdesk on x5500.",
             "password,auth,reset,locked,lockout,signin"),
            ("kb003", "MFA Enrollment",
             "Install Microsoft Authenticator, open mfa.acme.corp, scan the QR code and enter the 6-digit code to "
             "verify. Without MFA enrolled, password resets must go through the helpdesk.",
             "mfa,auth,2fa,authenticator"),
            ("kb004", "Service Outage Procedure",
             "Check status.acme.corp first. For P1 outages page the on-call team in PagerDuty, create a ticket and "
             "add the incident channel.",
             "outage,incident,escalation,down"),
            ("kb005", "Request Access to a Folder or App",
             "Access is granted by the data owner, not by IT. Open the access portal at access.acme.corp, pick the "
             "resource and give a business reason. Most requests are decided in one business day. IT can raise the "
             "request for you with a ticket.",
             "access,permission,folder,application,request,shared,drive"),
            ("kb006", "Laptop Repair and Replacement",
             "Do not try to repair a damaged laptop. Raise a ticket for End-user devices with the asset tag and a "
             "photo. A loaner is available at the service desk the same day and replacements ship in three business "
             "days.",
             "laptop,hardware,screen,cracked,replacement,repair,device,broken"),
            ("kb007", "Office Apps Crash on Open",
             "Start the app in safe mode (hold Ctrl while opening). Disable add-ins one at a time, then run Quick "
             "Repair from Settings, Apps. If a single file crashes the app, open it from the web version and save "
             "a copy.",
             "excel,word,outlook,office,crash,crashes,software,application"),
            ("kb008", "Shared Drive Will Not Open",
             "Confirm the VPN is connected, then remap the drive from File Explorer. If several people are affected "
             "check status.acme.corp, because it is usually a file server issue and needs a ticket for Applications.",
             "shared,drive,network,files,sales,team,open"),
        ])
        con.executemany("INSERT INTO service_logs VALUES (?,?,?,?,?)", [
            (str(uuid.uuid4()), now, "vpn-gateway", "ERROR", "Connection timeout for user alice"),
            (str(uuid.uuid4()), now, "vpn-gateway", "ERROR", "Connection timeout for user carol"),
            (str(uuid.uuid4()), now, "vpn-gateway", "WARN", "High retry rate on port 443"),
            (str(uuid.uuid4()), now, "auth-service", "INFO", "Password reset completed for u003"),
            (str(uuid.uuid4()), now, "auth-service", "WARN", "Failed login attempt: bob@acme.corp"),
            (str(uuid.uuid4()), now, "checkout-api", "ERROR", "DB connection pool exhausted"),
            (str(uuid.uuid4()), now, "checkout-api", "ERROR", "Timeout on order POST /orders (5042ms)"),
            (str(uuid.uuid4()), now, "checkout-api", "WARN", "P95 latency > 3000ms"),
        ])
        con.executemany("INSERT INTO service_state VALUES (?,?,?)", [
            ("vpn-gateway", "degraded", now),
            ("auth-service", "running", now),
            ("checkout-api", "degraded", now),
        ])
        con.executemany("INSERT INTO user_roles VALUES (?,?,?)", [
            ("u002", "finance-db", "read"),
            ("u004", "finance-db", "admin"),
        ])


store = SyntheticStore()
