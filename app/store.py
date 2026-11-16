from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "fixtures" / "synthetic.db"


class SyntheticStore:
    def __init__(self, path: Path = DB_PATH) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as con:
            self._create_tables(con)
            if self._is_empty(con):
                self._seed(con)

    def conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._path)
        con.row_factory = sqlite3.Row
        return con

    def _create_tables(self, con: sqlite3.Connection) -> None:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, name TEXT, email TEXT,
                department TEXT, role TEXT,
                is_mfa_enabled INTEGER DEFAULT 1,
                password_locked INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY, created_at TEXT,
                requester_id TEXT, title TEXT,
                status TEXT, priority TEXT
            );
            CREATE TABLE IF NOT EXISTS kb_articles (
                id TEXT PRIMARY KEY, title TEXT, body TEXT, tags TEXT
            );
            CREATE TABLE IF NOT EXISTS service_logs (
                id TEXT PRIMARY KEY, ts TEXT, service TEXT,
                level TEXT, message TEXT
            );
            CREATE TABLE IF NOT EXISTS service_state (
                service TEXT PRIMARY KEY, status TEXT, last_restart TEXT
            );
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id TEXT, resource TEXT, role TEXT
            );
        """)

    def _is_empty(self, con: sqlite3.Connection) -> bool:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

    def _seed(self, con: sqlite3.Connection) -> None:
        now = datetime.now(timezone.utc).isoformat()
        users = [
            ("u001", "Alice Chen",  "alice@acme.corp", "Engineering", "user",  1, 0),
            ("u002", "Bob Patel",   "bob@acme.corp",   "Finance",     "admin", 1, 0),
            ("u003", "Carol Wu",    "carol@acme.corp", "Finance",     "user",  1, 1),
            ("u004", "Dan Kim",     "dan@acme.corp",   "IT",          "admin", 1, 0),
            ("u005", "Eve Torres",  "eve@acme.corp",   "Sales",       "user",  0, 0),
        ]
        con.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?)", users)
        tickets = [
            ("t001", now, "u003", "Password reset request",    "closed",   "high"),
            ("t002", now, "u001", "VPN keeps dropping",         "open",     "medium"),
            ("t003", now, "u002", "Checkout timeouts in prod",  "open",     "critical"),
        ]
        con.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?)", tickets)
        kb = [
            (
                "kb001", "VPN Setup Guide",
                "Connect using GlobalProtect. Download from it.acme.corp/vpn. Use your SSO credentials."
                " For Error 809 check your firewall.",
                "vpn,network,setup",
            ),
            (
                "kb002", "Password Reset Procedure",
                "Go to accounts.acme.corp/reset. Enter your email. Check your phone for the OTP."
                " If locked out call the IT helpdesk at x5500.",
                "password,auth,reset,locked",
            ),
            (
                "kb003", "MFA Enrollment",
                "Download Microsoft Authenticator. Go to mfa.acme.corp. Scan the QR code."
                " Use the 6-digit code to verify.",
                "mfa,auth,2fa",
            ),
            (
                "kb004", "Service Outage Procedure",
                "Check the status page at status.acme.corp. For P1 outages page the on-call team"
                " via PagerDuty. Create a ticket and add the incident channel.",
                "outage,incident,escalation",
            ),
        ]
        con.executemany("INSERT INTO kb_articles VALUES (?,?,?,?)", kb)
        logs = [
            (str(uuid.uuid4()), now, "vpn-gateway",  "ERROR", "Connection timeout for user alice"),
            (str(uuid.uuid4()), now, "vpn-gateway",  "ERROR", "Connection timeout for user carol"),
            (str(uuid.uuid4()), now, "vpn-gateway",  "WARN",  "High retry rate on port 443"),
            (str(uuid.uuid4()), now, "auth-service", "INFO",  "Password reset completed for u003"),
            (str(uuid.uuid4()), now, "auth-service", "WARN",  "Failed login attempt: bob@acme.corp"),
            (str(uuid.uuid4()), now, "checkout-api", "ERROR", "DB connection pool exhausted"),
            (str(uuid.uuid4()), now, "checkout-api", "ERROR", "Timeout on order POST /orders (5042ms)"),
            (str(uuid.uuid4()), now, "checkout-api", "ERROR", "Timeout on order POST /orders (4891ms)"),
            (str(uuid.uuid4()), now, "checkout-api", "WARN",  "P95 latency > 3000ms"),
            (str(uuid.uuid4()), now, "auth-service", "INFO",  "MFA enrollment completed for u005"),
        ]
        con.executemany("INSERT INTO service_logs VALUES (?,?,?,?,?)", logs)
        services = [
            ("vpn-gateway",  "degraded", now),
            ("auth-service", "running",  now),
            ("checkout-api", "degraded", now),
        ]
        con.executemany("INSERT INTO service_state VALUES (?,?,?)", services)
        roles = [
            ("u002", "finance-db", "read"),
            ("u004", "finance-db", "admin"),
        ]
        con.executemany("INSERT INTO user_roles VALUES (?,?,?)", roles)


store = SyntheticStore()
