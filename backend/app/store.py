from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from app.schemas import RunRecord, UploadRecord


class Repository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path, check_same_thread=False)

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS uploads (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
            )

    def save_upload(self, upload: UploadRecord) -> None:
        payload = upload.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO uploads (id, payload) VALUES (?, ?)",
                (upload.id, payload),
            )

    def get_upload(self, upload_id: str) -> UploadRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM uploads WHERE id = ?", (upload_id,)
            ).fetchone()
        if not row:
            return None
        return UploadRecord.model_validate(json.loads(row[0]))

    def save_run(self, run: RunRecord) -> None:
        payload = run.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO runs (id, payload, created_at) VALUES (?, ?, ?)",
                (run.id, payload, run.created_at.isoformat()),
            )

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        return RunRecord.model_validate(json.loads(row[0]))

    def list_runs(self) -> list[RunRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [RunRecord.model_validate(json.loads(row[0])) for row in rows]
