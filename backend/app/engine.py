"""Silnik Jej Trasy: wskaźnik bezpieczeństwa odcinków i wyznaczanie tras.

Wskaźnik bezpieczeństwa odcinka (0-100) w chwili t:

    S = 100 · (0.30·L + 0.22·A + 0.20·I + 0.16·E + 0.12·U)

    L - oświetlenie: d + (1-d)·lit,  d = poziom światła dziennego z wysokości Słońca,
        lit = tag OSM `lit` / latarnie / estymacja, korygowane ocenami użytkowniczek
    A - aktywność: otwarte lokale w promieniu 45 m (godziny otwarcia!) + typowy ruch na danym typie ulicy o tej porze
    I - brak zagrożeń: exp(-0.55·P), P = Σ waga · dopasowanie do pory · świeżość · bliskość zgłoszeń (KMZB + użytkowniczki)
    E - otoczenie: 1 - ryzyko terenu (las, park, łąka, pustostan, bulwar, przejście podziemne) wzmacniane po zmroku
    U - opinie: średnia bayesowska ocen odcinka z ankiet po trasie (osobno dzień / noc)

Wynik trasy: 0.65 · średnia ważona długością + 0.35 · 10. percentyl (najsłabsze fragmenty).
Koszt krawędzi przy wyznaczaniu trasy: długość · (1 + λ·(1 - S/100)²) [+ kara za odcinki S < 45 w trybie "najbezpieczniejsza"].
"""

from __future__ import annotations

import heapq
import math
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from .city import City, Edge
from .demo_data import KMZB_CATEGORIES, USER_CATEGORIES, generate_incidents, seed_feedback
from .storage import Store
from .sun import daylight_factor, sun_times

TZ = ZoneInfo("Europe/Warsaw")
WALK_SPEED = 1.3  # m/s ≈ 4.7 km/h
INCIDENT_RADIUS = 60.0

WEIGHTS = {"L": 0.30, "A": 0.22, "I": 0.20, "E": 0.16, "U": 0.12}

STREET_BASE = {
    "primary": 1.0, "primary_link": 0.8, "secondary": 1.0, "secondary_link": 0.8, "trunk": 0.8, "trunk_link": 0.6,
    "tertiary": 0.85, "tertiary_link": 0.7, "pedestrian": 0.95, "living_street": 0.5, "residential": 0.5,
    "unclassified": 0.4, "service": 0.3, "footway": 0.4, "cycleway": 0.35, "steps": 0.3, "corridor": 0.6,
    "path": 0.15, "track": 0.1,
}

# Ruch pieszy w ciągu doby (0 = pusto, 1 = szczyt)
HOURLY_ACTIVITY = [0.35, 0.28, 0.2, 0.12, 0.1, 0.15, 0.35, 0.7, 0.85, 0.85, 0.9, 0.95,
                   1.0, 1.0, 0.95, 0.95, 1.0, 1.0, 0.95, 0.85, 0.7, 0.6, 0.5, 0.42]

ENV_LABELS = {
    "forest": "Las / zarośla", "park": "Park", "meadow": "Otwarta łąka", "vacant": "Pustostan / nieużytek",
    "cemetery": "Cmentarz", "allotments": "Ogródki działkowe", "riverbank": "Bulwar nad rzeką",
    "underpass": "Przejście podziemne", "passage": "Przejście bramą",
}

MODES = [
    {"id": "safest", "label": "Najbezpieczniejsza", "lambda": 14.0, "hard": True},
    {"id": "balanced", "label": "Zrównoważona", "lambda": 5.0, "hard": False},
    {"id": "fastest", "label": "Najszybsza", "lambda": 0.0, "hard": False},
]


def to_local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)


def level(score: float) -> dict:
    if score >= 75:
        return {"id": "safe", "label": "Bezpieczna"}
    if score >= 55:
        return {"id": "moderate", "label": "Umiarkowana"}
    return {"id": "risky", "label": "Ryzykowna"}


def poi_open(poi: dict, dt: datetime) -> tuple[bool, int | None]:
    """Czy lokal jest otwarty + minuta zamknięcia (względem północy dnia dt; może być > 1440)."""
    m = dt.hour * 60 + dt.minute
    wd = dt.weekday()
    for a, b in poi["hours"][wd]:
        if a <= m < b:
            return True, b
    for a, b in poi["hours"][(wd - 1) % 7]:
        if b > 1440 and m + 1440 < b:
            return True, b - 1440
    return False, None


def fmt_minute(m: int | None) -> str | None:
    if m is None:
        return None
    if m >= 1440 and m % 1440 == 0:
        return "24:00"
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


class Engine:
    def __init__(self, city: City, store: Store):
        self.city = city
        self.store = store
        self.lock = threading.Lock()
        self.now = datetime.now(TZ)
        self.center = ((city.bbox[0] + city.bbox[2]) / 2, (city.bbox[1] + city.bbox[3]) / 2)

        if not store.is_seeded():
            store.seed(seed_feedback(city))
        store.load()

        self.incidents: list[dict] = generate_incidents(city, self.now)
        for inc in self.incidents:
            self._index_incident(inc)
        for r in store.reports():
            self._add_report_incident(r)
        self._cache: dict = {}

    # ------------------------------------------------------------------ incydenty

    def _index_incident(self, inc: dict):
        inc["_d"] = datetime.fromisoformat(inc["date"]).date()
        for eid, d in self.city.edges_near(inc["lat"], inc["lon"], INCIDENT_RADIUS):
            self.city.edges[eid].incidents.append((inc["id"], d))

    def _add_report_incident(self, r: dict) -> dict:
        label, weight = USER_CATEGORIES.get(r["cat"], ("Zgłoszenie", 0.6))
        inc = {
            "id": len(self.incidents), "source": "user", "cat": r["cat"], "label": label, "weight": weight,
            "lat": r["lat"], "lon": r["lon"], "hour": r["hour"], "date": r["created_at"], "status": "nowe zgłoszenie",
            "fresh": True,
        }
        self.incidents.append(inc)
        self._index_incident(inc)
        return inc

    def add_report(self, lat: float, lon: float, cat: str, when: datetime) -> dict:
        with self.lock:
            r = self.store.add_report(lat, lon, cat, when.hour)
            inc = self._add_report_incident(r)
            self._cache.clear()
        return inc

    # ------------------------------------------------------------------ kontekst czasu

    def context(self, dt: datetime) -> dict:
        dt = to_local(dt)
        d = daylight_factor(dt, *self.center)
        st = sun_times(dt, *self.center)
        phase = "day" if d >= 0.999 else ("night" if d <= 0.001 else "twilight")
        return {
            "time": dt.isoformat(timespec="minutes"), "daylight": round(d, 3), "phase": phase,
            "phaseLabel": {"day": "Dzień", "twilight": "Zmierzch", "night": "Noc"}[phase],
            "period": "day" if d >= 0.5 else "night",
            "activity": HOURLY_ACTIVITY[dt.hour],
            **{k: (v.strftime("%H:%M") if v else None) for k, v in st.items()},
        }

    # ------------------------------------------------------------------ wskaźnik odcinka

    def edge_factors(self, e: Edge, dt: datetime, d: float, period: str) -> dict:
        agg = self.store.ratings[period].get(e.id)

        # oceny użytkowniczek korygują dane OSM - jedna opinia przesuwa wartość o ~1/9
        lit = e.lit
        if agg and agg.ln > 0:
            lit = (lit * 8 + agg.ls) / (8 + agg.ln)
        L = d + (1 - d) * lit

        open_w = 0.0
        for pi in e.pois:
            poi = self.city.pois[pi]
            if poi_open(poi, dt)[0]:
                open_w += poi["w"]
        poi_term = 1 - math.exp(-open_w / 2.0)
        base = STREET_BASE.get(e.hw, 0.3)
        if e.env in ("park", "meadow", "riverbank"):
            base = 0.6 * d + 0.08 * (1 - d)  # w dzień parki tętnią życiem, nocą pustoszeją
        A = 0.6 * poi_term + 0.4 * base * HOURLY_ACTIVITY[dt.hour]
        if agg and agg.vn > 0:
            A = (A * 8 + agg.vs) / (8 + agg.vn)

        P = 0.0
        for idx, dist in e.incidents:
            inc = self.incidents[idx]
            dh = abs(dt.hour - inc["hour"])
            dh = min(dh, 24 - dh)
            timefit = 0.3 + 0.7 * math.exp(-(dh ** 2) / 18)
            days = abs((dt.date() - inc["_d"]).days)
            recency = math.exp(-days / 120)
            P += inc["weight"] * timefit * recency / (1 + dist / 25)
        I = math.exp(-0.55 * P)

        risk = e.env_risk
        if e.env == "cemetery":
            risk = 0.2 * d + 1.0 * (1 - d)  # nocą zamknięty i pusty
        E = 1 - risk * (0.3 + 0.7 * (1 - d))

        U = ((agg.s if agg else 0) + 3 * 0.65) / ((agg.n if agg else 0) + 3)

        f = {"L": L, "A": A, "I": I, "E": E, "U": U}
        f["S"] = 100 * sum(WEIGHTS[k] * f[k] for k in WEIGHTS)
        f["P"] = P
        f["lit"] = lit
        f["openW"] = open_w
        return f

    def scores(self, dt: datetime) -> tuple[list[float], dict]:
        dt = to_local(dt)
        key = (dt.strftime("%Y%m%d%H") + str(dt.minute // 5), self.store.version, len(self.incidents))
        with self.lock:
            hit = self._cache.get(key)
            if hit:
                return hit
            d = daylight_factor(dt, *self.center)
            period = "day" if d >= 0.5 else "night"
            sc = [self.edge_factors(e, dt, d, period)["S"] for e in self.city.edges]
            if len(self._cache) > 40:
                self._cache.clear()
            self._cache[key] = (sc, {"d": d, "period": period})
            return sc, {"d": d, "period": period}

    # ------------------------------------------------------------------ trasowanie

    def _dijkstra(self, src: int, dst: int, cost: list[float]) -> list[tuple[int, int]] | None:
        dist = {src: 0.0}
        prev: dict[int, tuple[int, int]] = {}
        goal = self.city.nodes[dst]
        heap = [(0.0, src)]
        done = set()
        while heap:
            du, u = heapq.heappop(heap)
            if u in done:
                continue
            done.add(u)
            if u == dst:
                break
            for v, eid in self.city.adj[u]:
                nd = du + cost[eid]
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prev[v] = (u, eid)
                    heapq.heappush(heap, (nd, v))
        if dst not in prev and src != dst:
            return None
        path = []
        n = dst
        while n != src:
            u, eid = prev[n]
            path.append((eid, u))
            n = u
        path.reverse()
        return path  # [(edge_id, węzeł startowy)]

    def plan(self, a: tuple[float, float], b: tuple[float, float], dt: datetime) -> dict:
        dt = to_local(dt)
        src, dst = self.city.nearest_node(*a), self.city.nearest_node(*b)
        scores, info = self.scores(dt)
        d = info["d"]

        found = []
        for mode in MODES:
            lam = mode["lambda"]
            cost = []
            for e, s in zip(self.city.edges, scores):
                r = 1 - s / 100
                c = e.length * (1 + lam * r * r)
                if mode["hard"] and s < 45:
                    c *= 1 + (45 - s) / 12
                cost.append(c)
            path = self._dijkstra(src, dst, cost)
            if path is None:
                continue
            ids = [eid for eid, _ in path]
            dup = None
            length = sum(self.city.edges[i].length for i in ids)
            mean = sum(scores[i] * self.city.edges[i].length for i in ids) / max(length, 1)
            for f in found:
                near_same = abs(f["length"] - length) < 0.05 * length and abs(f["mean"] - mean) < 2.5
                if near_same or _similarity(self.city, f["edges"], ids) > 0.85:
                    dup = f
                    break
            if dup:
                dup["modes"].append(mode["id"])
                continue
            found.append({"modes": [mode["id"]], "edges": ids, "path": path, "length": length, "mean": mean})

        routes = [self._summarize(f, scores, dt, d, info["period"]) for f in found]
        fastest = min(routes, key=lambda r: r["distance"])
        for r in routes:
            r["compare"] = self._compare(r, fastest)
        # rekomendacja: jeśli najszybsza jest bezpieczna, a zysk z nadkładania drogi niewielki - wybierz najszybszą
        safest = max(routes, key=lambda r: r["score"])
        rec = safest
        if fastest["score"] >= 75 and safest["score"] - fastest["score"] < 6:
            rec = fastest
        for r in routes:
            r["recommended"] = r is rec
            r["label"] = _label(r["modes"])
        routes.sort(key=lambda r: (not r["recommended"], -r["score"]))
        return {"context": self.context(dt), "routes": routes}

    # ------------------------------------------------------------------ podsumowanie trasy

    def _summarize(self, found: dict, scores: list[float], dt: datetime, d: float, period: str) -> dict:
        city = self.city
        coords: list[list[float]] = []
        segments = []
        steps = []
        total = 0.0
        weighted = 0.0
        lit_len = verified_len = unlit_len = 0.0
        env_len: dict[tuple, float] = {}
        poi_ids: dict[int, float] = {}
        inc_ids: set[int] = set()
        rating_n = 0.0
        rating_s = 0.0
        weakest = None
        per_edge = []

        for eid, start in found["path"]:
            e = city.edges[eid]
            geom = e.geom if start == e.u else e.geom[::-1]
            f = self.edge_factors(e, dt, d, period)
            s = scores[eid]
            per_edge.append((e, s))
            if coords and coords[-1] == geom[0]:
                coords.extend(geom[1:])
            else:
                coords.extend(geom)
            band = _band(s)
            if segments and segments[-1]["band"] == band:
                segments[-1]["coords"].extend(geom[1:])
                segments[-1]["len"] += e.length
                segments[-1]["_sw"] += s * e.length
            else:
                segments.append({"band": band, "coords": list(geom), "len": e.length, "_sw": s * e.length})

            name = e.name or (e.env_name if e.env else None) or _hw_label(e.hw)
            if steps and steps[-1]["name"] == name:
                st = steps[-1]
                st["end"] = round(total + e.length, 1)
                st["_sw"] += s * e.length
                st["_len"] += e.length
                st["minScore"] = min(st["minScore"], round(s))
                st["openPois"] += sum(1 for pi in e.pois if poi_open(city.pois[pi], dt)[0])
                st["incidents"] += len(e.incidents)
            else:
                steps.append({
                    "name": name, "start": round(total, 1), "end": round(total + e.length, 1), "_sw": s * e.length,
                    "_len": e.length, "minScore": round(s), "lit": round(f["lit"], 2), "env": e.env,
                    "envLabel": ENV_LABELS.get(e.env), "openPois": sum(1 for pi in e.pois if poi_open(city.pois[pi], dt)[0]),
                    "incidents": len(e.incidents),
                })

            total += e.length
            weighted += s * e.length
            if f["lit"] >= 0.6:
                lit_len += e.length
            if f["lit"] < 0.4:
                unlit_len += e.length
            if e.lit_src in ("osm", "lamps"):
                verified_len += e.length
            if e.env:
                k = (e.env, e.env_name)
                env_len[k] = env_len.get(k, 0) + e.length
            for pi in e.pois:
                poi_ids[pi] = 1
            for idx, dist in e.incidents:
                if dist <= 45:
                    inc_ids.add(idx)
            agg = self.store.ratings[period].get(eid)
            if agg:
                rating_n += agg.n
                rating_s += agg.s
            if e.length > 12 and (weakest is None or s < weakest[1]):
                weakest = (e, s, f)

        for sgm in segments:
            sgm["score"] = round(sgm.pop("_sw") / sgm["len"])
            sgm["len"] = round(sgm["len"])
        for st in steps:
            st["score"] = round(st.pop("_sw") / st.pop("_len"))

        mean = weighted / total if total else 0
        p10 = _percentile(per_edge, 0.1)
        score = round(0.65 * mean + 0.35 * p10)  # trasa jest tak bezpieczna, jak jej najsłabszy fragment

        open_pois, closed = [], 0
        for pi in poi_ids:
            p = city.pois[pi]
            is_open, until = poi_open(p, dt)
            if is_open:
                open_pois.append({
                    "name": p["name"], "label": p["label"], "cat": p["cat"], "lat": p["lat"], "lon": p["lon"],
                    "until": fmt_minute(until), "hoursSource": p["src"],
                })
            else:
                closed += 1
        open_pois.sort(key=lambda p: (p["cat"] not in ("police", "hospital", "fuel", "convenience", "pharmacy"), p["name"]))

        incs = [self.incidents[i] for i in sorted(inc_ids)]
        cat_counts: dict[str, int] = {}
        for inc in incs:
            cat_counts[inc["label"]] = cat_counts.get(inc["label"], 0) + 1

        zones = [
            {"kind": k[0], "label": ENV_LABELS.get(k[0], k[0]), "name": k[1], "length": round(v)}
            for k, v in sorted(env_len.items(), key=lambda kv: -kv[1]) if v >= 25
        ]

        weak = None
        if weakest:
            e, s, f = weakest
            reasons = []
            if f["lit"] < 0.4 and d < 0.5:
                reasons.append("słabe oświetlenie")
            if e.env:
                reasons.append(ENV_LABELS.get(e.env, e.env).lower())
            if f["P"] > 0.8:
                reasons.append("zgłoszenia zagrożeń w pobliżu")
            if f["openW"] == 0 and d < 0.5:
                reasons.append("brak otwartych lokali")
            weak = {"name": e.name or e.env_name or _hw_label(e.hw), "score": round(s), "reasons": reasons,
                    "lat": e.mid[0], "lon": e.mid[1]}

        factors = self._route_factors(per_edge, dt, d, period)

        return {
            "id": found["modes"][0],
            "modes": found["modes"],
            "edges": found["edges"],
            "coords": coords,
            "segments": segments,
            "steps": steps,
            "distance": round(total),
            "duration": round(total / WALK_SPEED / 60),
            "score": score,
            "level": level(score),
            "factors": factors,
            "lighting": {
                "litShare": round(lit_len / total, 3) if total else 0,
                "unlitMeters": round(unlit_len),
                "verifiedShare": round(verified_len / total, 3) if total else 0,
                "daylight": round(d, 3),
            },
            "venues": {"open": len(open_pois), "closed": closed, "list": open_pois[:60]},
            "incidents": {
                "total": len(incs),
                "police": sum(1 for i in incs if i["source"] == "kmzb"),
                "users": sum(1 for i in incs if i["source"] == "user"),
                "categories": sorted(({"label": k, "count": v} for k, v in cat_counts.items()), key=lambda c: -c["count"]),
                "list": [{k: i[k] for k in ("lat", "lon", "label", "source", "date", "hour", "status")} for i in incs[:80]],
            },
            "zones": zones,
            "feedback": {"count": round(rating_n), "avg": round(rating_s / rating_n, 3) if rating_n else None},
            "weakest": weak,
        }

    def _route_factors(self, per_edge, dt, d, period) -> list[dict]:
        acc = {k: 0.0 for k in WEIGHTS}
        total = 0.0
        for e, _ in per_edge:
            f = self.edge_factors(e, dt, d, period)
            for k in WEIGHTS:
                acc[k] += f[k] * e.length
            total += e.length
        labels = {
            "L": "Oświetlenie", "A": "Ruch i otwarte lokale", "I": "Brak zgłoszeń zagrożeń",
            "E": "Bezpieczne otoczenie", "U": "Opinie użytkowniczek",
        }
        return [
            {"key": k, "label": labels[k], "value": round(acc[k] / total, 3) if total else 0, "weight": WEIGHTS[k]}
            for k in WEIGHTS
        ]

    def _compare(self, r: dict, fastest: dict) -> dict:
        names_fast = {z["name"] or z["label"] for z in fastest["zones"] if z["kind"] not in ("passage",)}
        names_this = {z["name"] or z["label"] for z in r["zones"]}
        return {
            "extraMinutes": r["duration"] - fastest["duration"],
            "extraMeters": r["distance"] - fastest["distance"],
            "avoidedUnlit": max(0, fastest["lighting"]["unlitMeters"] - r["lighting"]["unlitMeters"]),
            "avoidedIncidents": max(0, fastest["incidents"]["total"] - r["incidents"]["total"]),
            "avoidedZones": sorted(names_fast - names_this),
            "extraOpenVenues": r["venues"]["open"] - fastest["venues"]["open"],
            "scoreGain": r["score"] - fastest["score"],
        }

    # ------------------------------------------------------------------ mapa bezpieczeństwa

    def network(self) -> list[list[list[float]]]:
        return [e.geom for e in self.city.edges]


def _similarity(city: City, a: list[int], b: list[int]) -> float:
    sa, sb = set(a), set(b)
    inter = sum(city.edges[i].length for i in sa & sb)
    union = sum(city.edges[i].length for i in sa | sb)
    return inter / union if union else 1.0


def _percentile(per_edge, q: float) -> float:
    items = sorted(per_edge, key=lambda t: t[1])
    total = sum(e.length for e, _ in items)
    acc = 0.0
    for e, s in items:
        acc += e.length
        if acc >= total * q:
            return s
    return items[-1][1] if items else 0


def _band(s: float) -> str:
    if s >= 75:
        return "safe"
    if s >= 55:
        return "moderate"
    return "risky"


def _label(modes: list[str]) -> str:
    if "safest" in modes and "fastest" in modes:
        return "Najbezpieczniejsza i najszybsza"
    if "safest" in modes:
        return "Najbezpieczniejsza"
    if "fastest" in modes:
        return "Najszybsza"
    return "Zrównoważona"


def _hw_label(hw: str) -> str:
    return {
        "footway": "Chodnik / alejka", "path": "Ścieżka", "steps": "Schody", "cycleway": "Ścieżka pieszo-rowerowa",
        "service": "Droga dojazdowa", "track": "Droga gruntowa", "pedestrian": "Deptak", "corridor": "Pasaż",
    }.get(hw, "Ulica")


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(TZ)
    return to_local(datetime.fromisoformat(value))
