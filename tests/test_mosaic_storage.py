from mosaic.storage import DurableStore


def test_durable_store_survives_reopen(tmp_path):
    path = tmp_path / "mosaic.sqlite"
    with DurableStore(path) as store:
        store.put("seal", "asset", {"version": 0, "state_root": "genesis"})
        store.put("capsule", "c1", {"predecessor": "asset", "attempt": 0})
        assert store.event_count() == 2
        assert store.integrity_check()
    with DurableStore(path) as reopened:
        assert reopened.get("seal", "asset")["state_root"] == "genesis"
        assert reopened.get("capsule", "c1")["attempt"] == 0
        assert reopened.event_count() == 2
        assert reopened.integrity_check()


def test_updates_are_idempotent_at_object_key(tmp_path):
    path = tmp_path / "mosaic.sqlite"
    with DurableStore(path) as store:
        store.put("seal", "asset", {"version": 0})
        store.put("seal", "asset", {"version": 1})
        assert list(store.items("seal")) == [("asset", {"version": 1})]
        assert store.event_count() == 2
