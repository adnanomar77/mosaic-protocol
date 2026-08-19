from pathlib import Path

from testnet.events import EventLog


def test_event_log_is_hash_chained_and_tamper_evident(tmp_path):
    path = Path(tmp_path) / "events.jsonl"
    log = EventLog(path, "mosaic-testnet-0", "0.1.0")
    first = log.append("node_started", "w0", port=20300)
    log.append("config_upgrade_completed", "w0", upgrade_id="cfg-v2", status="config-only")
    assert first["previous_event_hash"] == "GENESIS"
    assert log.verify()
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace("node_started", "node_tampered")
    path.write_text("\n".join(lines) + "\n")
    assert not EventLog(path, "mosaic-testnet-0", "0.1.0").verify()
