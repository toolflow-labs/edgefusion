from datetime import datetime
import threading
import time

from .config import flatten_configured_entities
from . import io_http, io_modbus


def default_readers():
    return {
        "modbus": io_modbus.read_fields,
        "http": io_http.read_fields,
    }


def collect_once(config, readers=None):
    readers = readers or default_readers()
    snapshots = []

    for entity in flatten_configured_entities(config):
        protocol = str(entity.get("protocol", "modbus")).lower()
        reader = readers.get(protocol)
        if not reader:
            values = {}
            errors = [f"unsupported protocol: {protocol}"]
        else:
            values, errors = reader(entity.get("connection", {}), entity.get("telemetry", {}))

        snapshot = {
            "device_id": entity["id"],
            "device_type": entity.get("type", "unknown"),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "data": values,
            "errors": errors,
            "capabilities": entity.get("capabilities", {"writable_fields": []}),
        }
        if entity.get("parent_id"):
            snapshot["parent_id"] = entity["parent_id"]
        snapshots.append(snapshot)

    return snapshots


class CollectorLoop:
    def __init__(self, config, latest_state, readers=None):
        self.config = config
        self.latest_state = latest_state
        self.readers = readers
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def collect(self):
        snapshots = collect_once(self.config, self.readers)
        self.latest_state.update(snapshots)
        return snapshots

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def _run(self):
        interval = float(self.config.get("collect_interval", 5))
        while self.running:
            self.collect()
            self._stop_event.wait(interval)
