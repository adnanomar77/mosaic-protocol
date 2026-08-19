"""Durable SQLite WAL storage with versioning, snapshots and safe event pruning."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable


class StorageError(RuntimeError):
    pass


class DurableStore:
    """Durable store with explicit FULL synchronous policy and recoverable schema."""

    CURRENT_SCHEMA_VERSION = 2

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._create_or_migrate()

    def _create_or_migrate(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mosaic_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mosaic_objects (
                kind TEXT NOT NULL,
                object_key TEXT NOT NULL,
                payload TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (kind, object_key)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mosaic_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_kind TEXT NOT NULL,
                object_key TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mosaic_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                base_event_seq INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        row = self.conn.execute("SELECT value FROM mosaic_meta WHERE key='schema_version'").fetchone()
        version = int(row[0]) if row else 1
        if version > self.CURRENT_SCHEMA_VERSION:
            raise StorageError(f"unsupported future storage schema: {version}")
        if version < self.CURRENT_SCHEMA_VERSION:
            self._migrate(version, self.CURRENT_SCHEMA_VERSION)
        self.conn.execute(
            "INSERT INTO mosaic_meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(self.CURRENT_SCHEMA_VERSION),),
        )
        self.conn.commit()

    def _migrate(self, from_version: int, to_version: int) -> None:
        """Apply additive migrations only; destructive migrations require a new version."""
        if from_version <= 1 < to_version:
            # v2 adds meta and snapshots; both tables are created above and existing
            # object/event rows remain valid and replayable.
            return
        raise StorageError(f"no migration path from schema {from_version} to {to_version}")

    @property
    def schema_version(self) -> int:
        row = self.conn.execute("SELECT value FROM mosaic_meta WHERE key='schema_version'").fetchone()
        return int(row[0]) if row else 0

    def put(self, kind: str, object_key: str, payload: dict, *, event: bool = True) -> None:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                """
                INSERT INTO mosaic_objects(kind, object_key, payload, version)
                VALUES(?, ?, ?, 1)
                ON CONFLICT(kind, object_key) DO UPDATE SET
                    payload=excluded.payload,
                    version=mosaic_objects.version + 1,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (kind, object_key, encoded),
            )
            if event:
                self.conn.execute(
                    "INSERT INTO mosaic_events(event_kind, object_key, payload) VALUES(?, ?, ?)",
                    (kind, object_key, encoded),
                )
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            raise StorageError(str(exc)) from exc

    def get(self, kind: str, object_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT payload FROM mosaic_objects WHERE kind=? AND object_key=?",
            (kind, object_key),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def items(self, kind: str) -> Iterable[tuple[str, dict]]:
        rows = self.conn.execute(
            "SELECT object_key, payload FROM mosaic_objects WHERE kind=? ORDER BY object_key",
            (kind,),
        ).fetchall()
        for object_key, payload in rows:
            yield object_key, json.loads(payload)

    def create_snapshot(self, snapshot_id: str, payload: dict, base_event_seq: int | None = None) -> None:
        if not snapshot_id:
            raise StorageError("snapshot id cannot be empty")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        latest = int(self.conn.execute("SELECT COALESCE(MAX(seq), 0) FROM mosaic_events").fetchone()[0])
        base = latest if base_event_seq is None else base_event_seq
        if base < 0 or base > latest:
            raise StorageError("snapshot base event sequence is invalid")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                "INSERT OR REPLACE INTO mosaic_snapshots(snapshot_id, base_event_seq, payload) VALUES(?, ?, ?)",
                (snapshot_id, base, encoded),
            )
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            raise StorageError(str(exc)) from exc

    def get_snapshot(self, snapshot_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT base_event_seq, payload FROM mosaic_snapshots WHERE snapshot_id=?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return {"snapshot_id": snapshot_id, "base_event_seq": int(row[0]), "payload": json.loads(row[1])}

    def snapshots(self) -> Iterable[dict]:
        rows = self.conn.execute(
            "SELECT snapshot_id, base_event_seq, payload FROM mosaic_snapshots ORDER BY snapshot_id"
        ).fetchall()
        for snapshot_id, base_event_seq, payload in rows:
            yield {
                "snapshot_id": snapshot_id,
                "base_event_seq": int(base_event_seq),
                "payload": json.loads(payload),
            }

    def prune_events_before(self, sequence: int, retain_event_kinds: Iterable[str] = ()) -> int:
        if sequence < 0:
            raise StorageError("event sequence cannot be negative")
        retained = tuple(sorted(set(retain_event_kinds)))
        if retained:
            placeholders = ",".join("?" for _ in retained)
            query = f"DELETE FROM mosaic_events WHERE seq < ? AND event_kind NOT IN ({placeholders})"
            params = (sequence, *retained)
        else:
            query = "DELETE FROM mosaic_events WHERE seq < ?"
            params = (sequence,)
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            cursor = self.conn.execute(query, params)
            self.conn.commit()
            return int(cursor.rowcount)
        except Exception as exc:
            self.conn.rollback()
            raise StorageError(str(exc)) from exc

    def event_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM mosaic_events").fetchone()[0])

    def wal_checkpoint(self) -> tuple[int, int, int]:
        row = self.conn.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
        return tuple(int(item) for item in row)

    def checkpoint(self) -> None:
        self.wal_checkpoint()

    def integrity_check(self) -> bool:
        row = self.conn.execute("PRAGMA integrity_check").fetchone()
        return row == ("ok",) and self.schema_version == self.CURRENT_SCHEMA_VERSION

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    def __enter__(self) -> "DurableStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
