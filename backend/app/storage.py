"""Trwałe dane aplikacji (SQLite): ankiety po trasie, oceny odcinków, zgłoszenia użytkowniczek."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "data" / "jejtrasa.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS surveys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    route_time TEXT NOT NULL,
    period TEXT NOT NULL,
    edges TEXT NOT NULL,
    overall INTEGER,           -- 1 = kciuk w górę, 0 = w dół
    felt_safe INTEGER,         -- 1..5
    lighting INTEGER,          -- 1 dobre, 0 złe, NULL brak odpowiedzi
    venues INTEGER,            -- 1 otwarte, 0 zamknięte, NULL brak odpowiedzi
    comment TEXT
);
CREATE TABLE IF NOT EXISTS edge_ratings (
    edge_id INTEGER NOT NULL,
    period TEXT NOT NULL,      -- 'day' | 'night'
    safety REAL NOT NULL,      -- 0..1
    lighting REAL,             -- 0..1
    venues REAL,               -- 0..1
    source TEXT NOT NULL,      -- 'seed' | 'survey'
    weight REAL NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_edge_ratings ON edge_ratings(edge_id);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    cat TEXT NOT NULL,
    hour INTEGER NOT NULL
);
"""


class Agg:
    __slots__ = ("s", "n", "ls", "ln", "vs", "vn")

    def __init__(self):
        self.s = self.n = self.ls = self.ln = self.vs = self.vn = 0.0

    def add(self, safety, lighting, venues, w=1.0):
        self.s += safety * w
        self.n += w
        if lighting is not None:
            self.ls += lighting * w
            self.ln += w
        if venues is not None:
            self.vs += venues * w
            self.vn += w


class Store:
    def __init__(self, path: Path = DB_FILE):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        self.ratings: dict[str, dict[int, Agg]] = {"day": defaultdict(Agg), "night": defaultdict(Agg)}
        self.version = 0

    def is_seeded(self) -> bool:
        return self.db.execute("SELECT 1 FROM edge_ratings WHERE source='seed' LIMIT 1").fetchone() is not None

    def seed(self, rows):
        with self.lock, self.db:
            self.db.executemany(
                "INSERT INTO edge_ratings(edge_id, period, safety, lighting, venues, source) VALUES (?,?,?,?,?,'seed')",
                rows,
            )

    def load(self):
        for eid, period, s, lv, vv, w in self.db.execute(
            "SELECT edge_id, period, safety, lighting, venues, weight FROM edge_ratings"
        ):
            self.ratings[period][eid].add(s, lv, vv, w)
        self.version += 1

    # ------------------------------------------------------------------ ankiety

    def add_survey(self, *, route_time: datetime, period: str, edges: list[int], overall: int | None,
                   felt_safe: int | None, lighting: int | None, venues: int | None, comment: str | None,
                   weight: float) -> int:
        parts = []
        if overall is not None:
            parts.append(float(overall))
        if felt_safe is not None:
            parts.append((felt_safe - 1) / 4)
        safety = sum(parts) / len(parts) if parts else 0.5
        lv = None if lighting is None else float(lighting)
        vv = None if venues is None else float(venues)
        with self.lock, self.db:
            cur = self.db.execute(
                "INSERT INTO surveys(created_at, route_time, period, edges, overall, felt_safe, lighting, venues, comment)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), route_time.isoformat(), period, json.dumps(edges),
                 overall, felt_safe, lighting, venues, comment),
            )
            self.db.executemany(
                "INSERT INTO edge_ratings(edge_id, period, safety, lighting, venues, source, weight) VALUES (?,?,?,?,?,'survey',?)",
                [(eid, period, safety, lv, vv, weight) for eid in edges],
            )
            for eid in edges:
                self.ratings[period][eid].add(safety, lv, vv, weight)
            self.version += 1
            return cur.lastrowid

    def recent_comments(self, limit: int = 20) -> list[dict]:
        rows = self.db.execute(
            "SELECT created_at, route_time, overall, felt_safe, lighting, venues, comment FROM surveys "
            "ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        keys = ["created_at", "route_time", "overall", "felt_safe", "lighting", "venues", "comment"]
        return [dict(zip(keys, r)) for r in rows]

    # ------------------------------------------------------------------ zgłoszenia

    def add_report(self, lat: float, lon: float, cat: str, hour: int) -> dict:
        created = datetime.now().isoformat(timespec="minutes")
        with self.lock, self.db:
            cur = self.db.execute("INSERT INTO reports(created_at, lat, lon, cat, hour) VALUES (?,?,?,?,?)",
                                  (created, lat, lon, cat, hour))
            self.version += 1
        return {"id": cur.lastrowid, "created_at": created, "lat": lat, "lon": lon, "cat": cat, "hour": hour}

    def reports(self) -> list[dict]:
        rows = self.db.execute("SELECT id, created_at, lat, lon, cat, hour FROM reports").fetchall()
        return [dict(zip(["id", "created_at", "lat", "lon", "cat", "hour"], r)) for r in rows]

    def stats(self) -> dict:
        q = self.db.execute
        return {
            "surveys": q("SELECT COUNT(*) FROM surveys").fetchone()[0],
            "ratings": q("SELECT COUNT(*) FROM edge_ratings").fetchone()[0],
            "rated_segments": q("SELECT COUNT(DISTINCT edge_id) FROM edge_ratings").fetchone()[0],
            "reports": q("SELECT COUNT(*) FROM reports").fetchone()[0],
        }
