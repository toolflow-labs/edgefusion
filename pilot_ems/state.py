from datetime import datetime


class LatestState:
    def __init__(self, site=None):
        self.site = site or {}
        self.snapshots = {}
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def update(self, snapshots):
        for snapshot in snapshots:
            self.snapshots[snapshot["device_id"]] = snapshot
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def all(self):
        return list(self.snapshots.values())

    def snapshot(self):
        return {
            "site": self.site,
            "timestamp": self.updated_at,
            "devices": self.all(),
        }
