"""Thread-safe inventory state.

Tracks the set of unique scanned barcodes and the latest object count
reported by the camera, and exposes add/remove operations so the GUI can
always show whether the two numbers agree.
"""

import threading
from datetime import datetime


class Inventory:
    def __init__(self):
        self._lock = threading.Lock()
        self._scanned = {}          # barcode -> time first scanned (HH:MM:SS)
        self._object_count = 0      # most recent count reported by the camera
        self._log = []              # human-readable event log, oldest first

    # ---------------------------------------------------------- camera --
    def set_object_count(self, count: int):
        with self._lock:
            self._object_count = count

    # --------------------------------------------------------- scanner --
    def add_barcode(self, code: str):
        """Add a newly scanned barcode. No-op (with a log entry) if it is
        already present, since a barcode must not be scanned twice."""
        with self._lock:
            if code in self._scanned:
                self._log.append(f"Duplicate ignored: {code}")
                return False
            self._scanned[code] = datetime.now().strftime("%H:%M:%S")
            self._log.append(f"Added: {code}")
            return True

    def remove_barcode(self, code: str):
        """Remove a previously scanned barcode (e.g. an item was taken back
        off the belt/table). No-op if it was never scanned."""
        with self._lock:
            if code not in self._scanned:
                self._log.append(f"Cannot remove (not scanned): {code}")
                return False
            del self._scanned[code]
            self._log.append(f"Removed: {code}")
            return True

    def reset(self):
        with self._lock:
            self._scanned.clear()
            self._log.append("Inventory reset")

    # ------------------------------------------------- read-only view --
    def snapshot(self):
        with self._lock:
            return {
                "object_count": self._object_count,
                "scanned_count": len(self._scanned),
                "codes": list(self._scanned.items()),
                "log": list(self._log[-50:]),
                "match": self._object_count == len(self._scanned),
            }
