"""Durable scheduler claims and runs. A failed/crashed claim is never replayed silently."""

import contextlib
import fcntl
import json
import sqlite3
from pathlib import Path
from .config import json_write


@contextlib.contextmanager
def profile_lock(state: Path):
    state.mkdir(parents=True, exist_ok=True)
    with (state / "writer.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "profile is busy; another writer holds the lock"
            ) from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Store:
    def __init__(self, state):
        state.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(state / "runs.db", timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS runs(
            id TEXT PRIMARY KEY, job TEXT NOT NULL, started TEXT NOT NULL,
            finished TEXT, status TEXT NOT NULL, detail TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS claims(job TEXT, slot TEXT, PRIMARY KEY(job,slot));
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def claim(self, job, slot):
        try:
            with self.db:
                self.db.execute("INSERT INTO claims VALUES(?,?)", (job, slot))
            return True
        except sqlite3.IntegrityError:
            return False

    def start(self, run, job, at):
        with self.db:
            self.db.execute(
                "INSERT INTO runs VALUES(?,?,?,NULL,?,?)",
                (run, job, at, "running", "{}"),
            )

    def finish(self, run, at, status, detail):
        with self.db:
            self.db.execute(
                "UPDATE runs SET finished=?,status=?,detail=? WHERE id=?",
                (at, status, json.dumps(detail), run),
            )

    def latest(self, job):
        row = self.db.execute(
            "SELECT id,started,finished,status,detail FROM runs WHERE job=? ORDER BY started DESC,rowid DESC LIMIT 1",
            (job,),
        ).fetchone()
        return (
            dict(zip(("id", "started", "finished", "status", "detail"), row))
            if row
            else None
        )

    def get_meta(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, value))

    def view(self, cfg):
        rows = []
        for job in cfg.jobs:
            latest = self.latest(job["name"])
            rows.append(
                {
                    "id": job["id"],
                    "name": job["name"],
                    "enabled": job["enabled"],
                    "schedule": {"kind": "cron", "expr": job["schedule"]},
                    "state": "scheduled" if job["enabled"] else "paused",
                    "last_status": (
                        "ok"
                        if latest["status"] in ("ok", "skipped")
                        else latest["status"]
                    )
                    if latest
                    else None,
                    "last_run_at": latest["finished"] if latest else None,
                    "last_error": latest["detail"]
                    if latest and latest["status"] == "error"
                    else None,
                }
            )
        json_write(cfg.state / "jobs-view.json", {"jobs": rows})
