"""SQLite-backed persistence for the UI's per-battery history.

The dashboard keeps its live history in memory (see app.py), which is lost
on every container restart. This mirrors each reading to a SQLite file on
a volume so history survives restarts, while enforcing the same retention
window (HISTORY_HOURS) so the cache never grows past what the UI actually
shows.
"""
import json
import pathlib
import sqlite3


class HistoryStore:
    def __init__(self, path: pathlib.Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only ever touched from the MQTT network-loop thread (writes/prune) and
        # the main thread (one-time load at startup, before that loop starts).
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                stack TEXT NOT NULL,
                addr INTEGER NOT NULL,
                ts TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_history_ts ON history(ts)")
        self.conn.commit()

    def append(self, stack: str, addr: int, ts_iso: str, payload: dict):
        self.conn.execute(
            "INSERT INTO history (stack, addr, ts, payload) VALUES (?, ?, ?, ?)",
            (stack, addr, ts_iso, json.dumps(payload)),
        )

    def prune(self, cutoff_iso: str):
        """Delete rows older than the retention window. ISO-8601 UTC timestamps
        sort lexically the same as chronologically, so a plain string
        comparison is enough."""
        self.conn.execute("DELETE FROM history WHERE ts < ?", (cutoff_iso,))

    def commit(self):
        self.conn.commit()

    def clear_all(self):
        self.conn.execute("DELETE FROM history")
        self.conn.commit()

    def load_recent(self, cutoff_iso: str):
        """Return {(stack, addr): [(ts_iso, payload_dict), ...]} for rows at or
        after cutoff, ordered oldest first."""
        cur = self.conn.execute(
            "SELECT stack, addr, ts, payload FROM history WHERE ts >= ? ORDER BY ts ASC",
            (cutoff_iso,),
        )
        result = {}
        for stack, addr, ts, payload in cur.fetchall():
            result.setdefault((stack, addr), []).append((ts, json.loads(payload)))
        return result
