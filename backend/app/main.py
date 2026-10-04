"""API prototypu Jej Trasa.

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .city import City
from .demo_data import KMZB_CATEGORIES, PLACES, SCENARIOS, USER_CATEGORIES
from .engine import WEIGHTS, Engine, parse_time
from .storage import Store

app = FastAPI(title="Jej Trasa API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

_t = time.perf_counter()
city = City()
store = Store()
engine = Engine(city, store)
print(f"[jej-trasa] dane załadowane: {len(city.edges)} odcinków, {len(city.pois)} lokali, "
      f"{len(engine.incidents)} zgłoszeń ({time.perf_counter() - _t:.1f}s)")


class Point(BaseModel):
    lat: float
    lon: float


class RouteRequest(BaseModel):
    origin: Point
    destination: Point
    time: str | None = None


class SurveyRequest(BaseModel):
    edges: list[int]
    time: str | None = None
    overall: Literal[0, 1] | None = None
    feltSafe: int | None = Field(default=None, ge=1, le=5)
    lighting: Literal[0, 1] | None = None
    venues: Literal[0, 1] | None = None
    comment: str | None = Field(default=None, max_length=1000)
    weight: float = Field(default=1.0, ge=1, le=50)  # tryb prezentacji: jedna opinia "waży" jak wiele


class ReportRequest(BaseModel):
    lat: float
    lon: float
    category: str
    time: str | None = None


@app.get("/api/meta")
def meta():
    return {
        "city": "Kraków",
        "bbox": city.bbox,
        "places": PLACES,
        "scenarios": SCENARIOS,
        "reportCategories": [{"id": k, "label": v[0]} for k, v in USER_CATEGORIES.items()],
        "policeCategories": [{"id": k, "label": v[0]} for k, v in KMZB_CATEGORIES.items()],
        "weights": WEIGHTS,
        "dataset": {
            "segments": len(city.edges),
            "segmentsWithOsmLighting": sum(1 for e in city.edges if e.lit_src == "osm"),
            "segmentsWithLamps": sum(1 for e in city.edges if e.lit_src == "lamps"),
            "streetLamps": city.meta.get("lamps"),
            "venues": len(city.pois),
            "venuesWithOsmHours": sum(1 for p in city.pois if p["src"] == "osm"),
            "incidents": len(engine.incidents),
            "policeIncidents": sum(1 for i in engine.incidents if i["source"] == "kmzb"),
            "userIncidents": sum(1 for i in engine.incidents if i["source"] == "user"),
            **store.stats(),
            "source": city.meta.get("source"),
        },
    }


@app.get("/api/context")
def context(time: str | None = None):
    return engine.context(parse_time(time))


@app.post("/api/routes")
def routes(req: RouteRequest):
    for p in (req.origin, req.destination):
        if not city.contains(p.lat, p.lon):
            raise HTTPException(400, "Punkt poza obszarem prototypu (centrum Krakowa)")
    return engine.plan((req.origin.lat, req.origin.lon), (req.destination.lat, req.destination.lon), parse_time(req.time))


@app.get("/api/network")
def network():
    """Geometria wszystkich odcinków (pobierana raz) - do warstwy 'mapa bezpieczeństwa'."""
    return {"edges": engine.network()}


@app.get("/api/scores")
def scores(time: str | None = None):
    sc, _ = engine.scores(parse_time(time))
    return {"context": engine.context(parse_time(time)), "scores": [round(s) for s in sc]}


@app.get("/api/incidents")
def incidents():
    return [{k: i[k] for k in ("lat", "lon", "label", "source", "date", "hour", "status")} for i in engine.incidents]


@app.post("/api/survey")
def survey(req: SurveyRequest):
    when = parse_time(req.time)
    edges = [e for e in dict.fromkeys(req.edges) if 0 <= e < len(city.edges)]
    if not edges:
        raise HTTPException(400, "Brak odcinków trasy")
    ctx = engine.context(when)
    before, _ = engine.scores(when)
    before_avg = _avg(before, edges)
    sid = store.add_survey(
        route_time=when, period=ctx["period"], edges=edges, overall=req.overall, felt_safe=req.feltSafe,
        lighting=req.lighting, venues=req.venues, comment=(req.comment or "").strip() or None, weight=req.weight,
    )
    after, _ = engine.scores(when)
    return {
        "id": sid,
        "segmentsUpdated": len(edges),
        "period": ctx["period"],
        "scoreBefore": round(before_avg, 1),
        "scoreAfter": round(_avg(after, edges), 1),
    }


@app.post("/api/reports")
def report(req: ReportRequest):
    if req.category not in USER_CATEGORIES:
        raise HTTPException(400, "Nieznana kategoria")
    inc = engine.add_report(req.lat, req.lon, req.category, parse_time(req.time))
    return {k: inc[k] for k in ("lat", "lon", "label", "source", "date", "hour", "status")}


@app.get("/api/comments")
def comments():
    return store.recent_comments()


def _avg(scores: list[float], edges: list[int]) -> float:
    total = sum(city.edges[e].length for e in edges)
    return sum(scores[e] * city.edges[e].length for e in edges) / total if total else 0


# zbudowany frontend (npm run build) serwowany z tego samego serwera
# (Windows potrafi mieć w rejestrze .js = text/plain, co blokuje moduły ES)
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
