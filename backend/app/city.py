"""Graf pieszy miasta wczytany z data/city.json.gz (zbudowanego z OpenStreetMap)."""

from __future__ import annotations

import gzip
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "city.json.gz"

M_PER_DEG_LAT = 111_320.0


@dataclass
class Edge:
    id: int
    u: int
    v: int
    length: float
    hw: str
    name: str | None
    lit: float
    lit_src: str
    env: str | None
    env_risk: float
    env_name: str | None
    pois: list[int]
    geom: list[list[float]]
    incidents: list[tuple[int, float]] = field(default_factory=list)  # (indeks zdarzenia, odległość m)

    @property
    def mid(self) -> list[float]:
        return self.geom[len(self.geom) // 2]


class City:
    def __init__(self, path: Path = DATA_FILE):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            raw = json.load(f)
        self.bbox = raw["bbox"]
        self.meta = raw["meta"]
        self.nodes: list[list[float]] = raw["nodes"]
        self.pois: list[dict] = raw["pois"]
        self.edges: list[Edge] = [
            Edge(i, e["u"], e["v"], e["len"], e["hw"], e["name"], e["lit"], e["litSrc"], e["env"],
                 e["envRisk"], e["envName"], e["pois"], e["g"])
            for i, e in enumerate(raw["edges"])
        ]
        lat0 = math.radians((self.bbox[0] + self.bbox[2]) / 2)
        self.m_per_deg_lon = M_PER_DEG_LAT * math.cos(lat0)

        self.adj: dict[int, list[tuple[int, int]]] = defaultdict(list)  # węzeł -> [(sąsiad, krawędź)]
        for e in self.edges:
            self.adj[e.u].append((e.v, e.id))
            self.adj[e.v].append((e.u, e.id))
        self.main_component = self._largest_component()

        self.edge_grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.cell = 80.0
        for e in self.edges:
            keys = {self._key(*self.xy(*p)) for p in e.geom}
            for k in keys:
                self.edge_grid[k].append(e.id)

    # ------------------------------------------------------------------ geo

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        return (lon - self.bbox[1]) * self.m_per_deg_lon, (lat - self.bbox[0]) * M_PER_DEG_LAT

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return int(x // self.cell), int(y // self.cell)

    def dist(self, a, b) -> float:
        ax, ay = self.xy(*a)
        bx, by = self.xy(*b)
        return math.hypot(ax - bx, ay - by)

    def dist_to_edge(self, lat: float, lon: float, edge: Edge) -> float:
        px, py = self.xy(lat, lon)
        best = float("inf")
        pts = [self.xy(*p) for p in edge.geom]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            d2 = dx * dx + dy * dy
            t = 0.0 if d2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / d2))
            best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
        return best

    def edges_near(self, lat: float, lon: float, radius: float) -> list[tuple[int, float]]:
        x, y = self.xy(lat, lon)
        r = int(math.ceil(radius / self.cell))
        ci, cj = self._key(x, y)
        seen: set[int] = set()
        out = []
        for i in range(ci - r, ci + r + 1):
            for j in range(cj - r, cj + r + 1):
                for eid in self.edge_grid.get((i, j), ()):
                    if eid in seen:
                        continue
                    seen.add(eid)
                    d = self.dist_to_edge(lat, lon, self.edges[eid])
                    if d <= radius:
                        out.append((eid, d))
        return out

    def nearest_node(self, lat: float, lon: float) -> int:
        for radius in (60, 150, 400, 1500):
            cands = [eid for eid, _ in sorted(self.edges_near(lat, lon, radius), key=lambda t: t[1])]
            for eid in cands:
                e = self.edges[eid]
                if e.u in self.main_component:
                    du = self.dist((lat, lon), self.nodes[e.u])
                    dv = self.dist((lat, lon), self.nodes[e.v])
                    return e.u if du <= dv else e.v
        raise ValueError("Punkt poza obszarem demo")

    def contains(self, lat: float, lon: float) -> bool:
        s, w, n, e = self.bbox
        return s <= lat <= n and w <= lon <= e

    # ------------------------------------------------------------------ graph

    def _largest_component(self) -> set[int]:
        seen: set[int] = set()
        best: set[int] = set()
        for start in list(self.adj):
            if start in seen:
                continue
            comp = {start}
            stack = [start]
            while stack:
                n = stack.pop()
                for m, _ in self.adj[n]:
                    if m not in comp:
                        comp.add(m)
                        stack.append(m)
            seen |= comp
            if len(comp) > len(best):
                best = comp
        return best
