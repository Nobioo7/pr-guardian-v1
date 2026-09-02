import hashlib
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import get_settings


class ReviewState:
    def __init__(self, db_path: str | None = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.state_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS events (delivery_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at REAL NOT NULL)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS findings "
                "(fingerprint TEXT PRIMARY KEY, owner TEXT NOT NULL, repo TEXT NOT NULL, "
                "pull_number INTEGER NOT NULL, path TEXT NOT NULL, line INTEGER NOT NULL, body TEXT NOT NULL, updated_at REAL NOT NULL)"
            )

    def claim_delivery(self, delivery_id: str | None) -> bool:
        if not delivery_id:
            return True
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO events (delivery_id, status, updated_at) VALUES (?, ?, ?)",
                    (delivery_id, "processing", time.time()),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def complete_delivery(self, delivery_id: str | None) -> None:
        if not delivery_id:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE events SET status = ?, updated_at = ? WHERE delivery_id = ?",
                ("completed", time.time(), delivery_id),
            )

    def fingerprint(self, owner: str, repo: str, pull_number: int, finding: dict[str, Any]) -> str:
        raw = "|".join(
            [
                owner,
                repo,
                str(pull_number),
                str(finding.get("path", "")),
                str(finding.get("line", "")),
                str(finding.get("title", "")),
                str(finding.get("evidence", "")),
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def filter_new_findings(self, owner: str, repo: str, pull_number: int, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        new_findings: list[dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            for finding in findings:
                fingerprint = self.fingerprint(owner, repo, pull_number, finding)
                try:
                    conn.execute(
                        "INSERT INTO findings (fingerprint, owner, repo, pull_number, path, line, body, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            fingerprint,
                            owner,
                            repo,
                            pull_number,
                            finding.get("path", ""),
                            int(finding.get("line", 0)),
                            finding.get("body", ""),
                            time.time(),
                        ),
                    )
                    new_findings.append(finding)
                except sqlite3.IntegrityError:
                    continue
        return new_findings
