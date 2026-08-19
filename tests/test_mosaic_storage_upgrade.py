import sqlite3

from mosaic.storage import DurableStore


def test_storage_schema_version_snapshot_and_reopen(tmp_path):
    path = tmp_path / "versioned.sqlite"
    with DurableStore(path) as store:
        assert store.schema_version == DurableStore.CURRENT_SCHEMA_VERSION
        store.put("closure", "c1", {"state_root": "s1"})
        store.put("receipt", "r1", {"status": "ACCEPT"})
        store.create_snapshot("snap-1", {"current": "s1"})
        snapshot = store.get_snapshot("snap-1")
        assert snapshot["payload"] == {"current": "s1"}
        assert snapshot["base_event_seq"] == 2
        assert store.integrity_check()
    with DurableStore(path) as reopened:
        assert reopened.schema_version == 2
        assert reopened.get_snapshot("snap-1")["payload"] == {"current": "s1"}
        assert reopened.integrity_check()


def test_storage_pruning_preserves_protected_event_kinds(tmp_path):
    path = tmp_path / "prune.sqlite"
    with DurableStore(path) as store:
        store.put("receipt", "r1", {"n": 1})
        store.put("closure", "c1", {"n": 1})
        store.put("receipt", "r2", {"n": 2})
        assert store.event_count() == 3
        deleted = store.prune_events_before(3, retain_event_kinds=("closure",))
        assert deleted == 1
        assert store.event_count() == 2
        assert store.integrity_check()


def test_legacy_v1_tables_migrate_additively(tmp_path):
    path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE mosaic_objects (kind TEXT NOT NULL, object_key TEXT NOT NULL, payload TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(kind, object_key))"
    )
    connection.execute(
        "CREATE TABLE mosaic_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_kind TEXT NOT NULL, object_key TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.execute(
        "INSERT INTO mosaic_objects(kind, object_key, payload) VALUES('seal', 'asset', '{\"version\":0}')"
    )
    connection.commit()
    connection.close()
    with DurableStore(path) as store:
        assert store.schema_version == 2
        assert store.get("seal", "asset")["version"] == 0
        assert store.integrity_check()
