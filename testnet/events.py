"""Hash-chained operational event log for MOSAIC testnet."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ccd_nexus.crypto import digest


class EventLogError(ValueError):
    pass


class EventLog:
    def __init__(self, path: str | Path, network_id: str, software_version: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.network_id = network_id
        self.software_version = software_version
        self._last_hash = "GENESIS"
        if self.path.exists():
            for event in self.read():
                self._last_hash = event["event_hash"]

    def append(self, kind: str, node_id: str, **payload: Any) -> dict:
        if not kind or not node_id:
            raise EventLogError("event kind and node_id are required")
        event = {
            "protocol": "MOSAIC/TESTNET-EVENT/v1",
            "network_id": self.network_id,
            "software_version": self.software_version,
            "wall_time": time.time(),
            "kind": kind,
            "node_id": node_id,
            "previous_event_hash": self._last_hash,
            "payload": payload,
        }
        event["event_id"] = digest(event)
        event["event_hash"] = digest({"event": event, "previous_event_hash": self._last_hash})
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        self._last_hash = event["event_hash"]
        return event

    def read(self) -> list[dict]:
        events = []
        if not self.path.exists():
            return events
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events

    def verify(self) -> bool:
        previous = "GENESIS"
        for event in self.read():
            if event.get("previous_event_hash") != previous:
                return False
            event_hash = event.get("event_hash")
            copy = dict(event)
            copy.pop("event_hash", None)
            if event_hash != digest({"event": copy, "previous_event_hash": previous}):
                return False
            previous = event_hash
        return True

    @property
    def last_hash(self) -> str:
        return self._last_hash
