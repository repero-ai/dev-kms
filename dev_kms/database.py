"""Small SQLite persistence layer; wrapping keys are intentionally stored locally."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class KeyRecord:
    key_id: str
    key_version: int
    wrapping_key: bytes
    created_at: str
    active: bool


class KeyAlreadyExistsError(Exception):
    pass


class KeyStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY,
                    key_id TEXT NOT NULL UNIQUE,
                    key_version INTEGER NOT NULL,
                    wrapping_key BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0, 1))
                )
                """
            )

    def create(self, key_id: str, wrapping_key: bytes) -> KeyRecord:
        created_at = datetime.now(UTC).isoformat()
        try:
            with self._connection() as connection:
                connection.execute(
                    """INSERT INTO keys (key_id, key_version, wrapping_key, created_at, active)
                    VALUES (?, 1, ?, ?, 1)""",
                    (key_id, wrapping_key, created_at),
                )
        except sqlite3.IntegrityError as error:
            raise KeyAlreadyExistsError(key_id) from error
        return KeyRecord(key_id, 1, wrapping_key, created_at, True)

    def get(self, key_id: str) -> KeyRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT key_id, key_version, wrapping_key, created_at, active
                FROM keys WHERE key_id = ?""",
                (key_id,),
            ).fetchone()
        return self._record(row) if row else None

    def list(self) -> list[KeyRecord]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT key_id, key_version, wrapping_key, created_at, active
                FROM keys ORDER BY key_id"""
            ).fetchall()
        return [self._record(row) for row in rows]

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> KeyRecord:
        return KeyRecord(
            key_id=row["key_id"],
            key_version=row["key_version"],
            wrapping_key=row["wrapping_key"],
            created_at=row["created_at"],
            active=bool(row["active"]),
        )
