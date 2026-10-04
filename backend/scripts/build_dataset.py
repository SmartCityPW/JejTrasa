"""Buduje zwarty zbiór danych miasta (data/city.json.gz) z surowych kafli OSM.

Wynik zawiera:
  * graf pieszy (krawędzie między skrzyżowaniami, z geometrią),
  * oświetlenie krawędzi (tag `lit`, latarnie `highway=street_lamp`, a gdy brak - estymacja z typu drogi),
  * typ otoczenia (park, las, łąka, pustostan, ogródki, bulwar, przejście podziemne),
  * lokale/obiekty z godzinami otwarcia (parsowane z `opening_hours` lub domyślne dla kategorii),
  * listę lokali w pobliżu każdej krawędzi.

    python scripts/build_dataset.py
"""

from __future__ import annotations

import gzip
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "city.json.gz"

BBOX = (50.0450, 19.9000, 50.0720, 19.9560)

WALKABLE = {
    "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link",
    "unclassified", "residential", "living_street", "pedestrian", "footway", "path", "steps",
    "service", "track", "cycleway", "trunk", "trunk_link", "corridor",
}

# --------------------------------------------------------------------------- geo helpers

R_EARTH = 6371000.0
LAT0 = math.radians((BBOX[0] + BBOX[2]) / 2)
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * math.cos(LAT0)


def xy(lat: float, lon: float) -> tuple[float, float]:
    return (lon - BBOX[1]) * M_PER_DEG_LON, (lat - BBOX[0]) * M_PER_DEG_LAT


def dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = xy(*a)
    bx, by = xy(*b)
    return math.hypot(ax - bx, ay - by)


def point_seg_dist(p, a, b) -> float:
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def point_polyline_dist(p, pts_xy) -> float:
    return min(point_seg_dist(p, pts_xy[i], pts_xy[i + 1]) for i in range(len(pts_xy) - 1))


def point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def ring_area(ring) -> float:
    s = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


class Grid:
    """Prosty indeks przestrzenny (kubełki ~cell m)."""

    def __init__(self, cell: float = 100.0):
        self.cell = cell
        self.buckets: dict[tuple[int, int], list] = defaultdict(list)

    def _key(self, x, y):
        return int(x // self.cell), int(y // self.cell)

    def insert_bbox(self, item, minx, miny, maxx, maxy):
        for i in range(int(minx // self.cell), int(maxx // self.cell) + 1):
            for j in range(int(miny // self.cell), int(maxy // self.cell) + 1):
                self.buckets[(i, j)].append(item)

    def insert_point(self, item, x, y):
        self.buckets[self._key(x, y)].append(item)

    def query(self, x, y, radius=0.0):
        r = int(math.ceil(radius / self.cell))
        ci, cj = self._key(x, y)
        seen = set()
        for i in range(ci - r, ci + r + 1):
            for j in range(cj - r, cj + r + 1):
                for it in self.buckets.get((i, j), ()):
                    if id(it) not in seen:
                        seen.add(id(it))
                        yield it


# --------------------------------------------------------------------------- parse OSM

def parse_tiles():
    nodes: dict[int, tuple[float, float]] = {}
    node_tags: dict[int, dict] = {}
    ways: dict[int, dict] = {}
    relations: dict[int, dict] = {}
    files = sorted(RAW_DIR.glob("*.osm"))
    if not files:
        raise SystemExit("Brak danych w data/raw - uruchom najpierw scripts/fetch_osm.py")
    for f in files:
        for _, el in ET.iterparse(f, events=("end",)):
            tag = el.tag
            if tag == "node":
                nid = int(el.get("id"))
                nodes[nid] = (float(el.get("lat")), float(el.get("lon")))
                tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
                if tags:
                    node_tags[nid] = tags
                el.clear()
            elif tag == "way":
                wid = int(el.get("id"))
                if wid not in ways:
                    ways[wid] = {
                        "nodes": [int(nd.get("ref")) for nd in el.findall("nd")],
                        "tags": {t.get("k"): t.get("v") for t in el.findall("tag")},
                    }
                el.clear()
            elif tag == "relation":
                rid = int(el.get("id"))
                if rid not in relations:
                    relations[rid] = {
                        "members": [(m.get("type"), int(m.get("ref")), m.get("role")) for m in el.findall("member")],
                        "tags": {t.get("k"): t.get("v") for t in el.findall("tag")},
                    }
                el.clear()
        print(f"  {f.name}: nodes={len(nodes)} ways={len(ways)}")
    return nodes, node_tags, ways, relations


# --------------------------------------------------------------------------- areas

def env_kind(tags: dict) -> tuple[str, float] | None:
    """Zwraca (rodzaj otoczenia, bazowe ryzyko 0..1) dla poligonu."""
    lu, le, na = tags.get("landuse"), tags.get("leisure"), tags.get("natural")
    if na in ("wood", "scrub") or lu == "forest":
        return "forest", 1.0
    if lu in ("brownfield", "construction") or tags.get("building") == "ruins" or (
        tags.get("abandoned") == "yes" and "building" in tags
    ):
        return "vacant", 0.85
    if lu == "railway":
        return "vacant", 0.8
    if lu == "allotments":
        return "allotments", 0.8
    if lu in ("meadow", "grass") or na in ("grassland", "heath"):
        return "meadow", 0.75
    if lu == "cemetery":
        return "cemetery", 0.7
    if le in ("park", "nature_reserve"):
        return "park", 0.65
    if le == "garden":
        return "park", 0.4
    return None


def build_areas(nodes, ways, relations):
    areas = []

    def add(ring_ids, tags):
        kind = env_kind(tags)
        if not kind:
            return
        pts = [nodes[n] for n in ring_ids if n in nodes]
        if len(pts) < 4 or len(pts) < len(ring_ids) * 0.9:
            return
        ring = [xy(*p) for p in pts]
        area = ring_area(ring)
        # małe trawniki przy ulicach nie czynią trasy niebezpieczną
        if kind[0] == "meadow" and area < 8000:
            return
        if kind[0] == "park" and area < 1500:
            return
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        areas.append({
            "kind": kind[0], "risk": kind[1], "name": tags.get("name"), "ring": ring,
            "bbox": (min(xs), min(ys), max(xs), max(ys)), "area": area,
        })

    for w in ways.values():
        ids = w["nodes"]
        if len(ids) > 3 and ids[0] == ids[-1]:
            add(ids, w["tags"])

    for r in relations.values():
        if r["tags"].get("type") != "multipolygon" or not env_kind(r["tags"]):
            continue
        segs = [list(ways[ref]["nodes"]) for t, ref, role in r["members"]
                if t == "way" and role in ("outer", "") and ref in ways]
        for ring in join_rings(segs):
            add(ring, r["tags"])

    for ar in MANUAL_AREAS:
        ring = [xy(*p) for p in ar["ring"]]
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        areas.append({"kind": ar["kind"], "risk": ar["risk"], "name": ar["name"], "ring": ring,
                      "bbox": (min(xs), min(ys), max(xs), max(ys)), "area": ring_area(ring)})

    print(f"  obszary: {len(areas)}")
    return areas


# Uzupełnienia ręczne - obszary, których brakuje w pobranym wycinku OSM
MANUAL_AREAS = [
    {
        "name": "Błonia", "kind": "meadow", "risk": 0.75,
        "ring": [(50.0591, 19.9222), (50.0604, 19.9222), (50.0609, 19.9170), (50.0609, 19.9120), (50.0601, 19.9055),
                 (50.0592, 19.9048), (50.05687, 19.9065), (50.05766, 19.9120), (50.05852, 19.9180)],
    },
]


def join_rings(segs):
    rings = []
    segs = [s for s in segs if len(s) > 1]
    while segs:
        cur = segs.pop()
        changed = True
        while cur[0] != cur[-1] and changed:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur += s[1:]
                elif s[-1] == cur[-1]:
                    cur += s[::-1][1:]
                elif s[-1] == cur[0]:
                    cur = s[:-1] + cur
                elif s[0] == cur[0]:
                    cur = s[::-1][:-1] + cur
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        if cur[0] == cur[-1]:
            rings.append(cur)
    return rings


# --------------------------------------------------------------------------- opening hours

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

DEFAULT_HOURS = {
    # kategoria: (pn-pt, sob, niedz) w minutach; end > 1440 = po północy
    "convenience": ((360, 1380), (420, 1380), (600, 1320)),
    "supermarket": ((360, 1320), (420, 1320), None),
    "shop": ((600, 1140), (600, 900), None),
    "bar": ((960, 1560), (960, 1620), (960, 1440)),
    "nightclub": (None, (1320, 1740), None),
    "restaurant": ((720, 1320), (720, 1380), (720, 1320)),
    "cafe": ((480, 1200), (540, 1200), (540, 1140)),
    "fast_food": ((660, 1440), (660, 1560), (660, 1440)),
    "pharmacy": ((480, 1200), (540, 900), None),
    "fuel": ((0, 1440), (0, 1440), (0, 1440)),
    "police": ((0, 1440), (0, 1440), (0, 1440)),
    "hospital": ((0, 1440), (0, 1440), (0, 1440)),
    "hotel": ((0, 1440), (0, 1440), (0, 1440)),
    "culture": ((600, 1320), (600, 1380), (600, 1320)),
}

TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\+?$")


def parse_days(spec: str) -> list[int] | None:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            if a not in DAYS or b not in DAYS:
                return None
            i, j = DAYS.index(a), DAYS.index(b)
            out += [d % 7 for d in range(i, j + 1 if j >= i else j + 8)]
        elif part in DAYS:
            out.append(DAYS.index(part))
        else:
            return None
    return out


def parse_opening_hours(oh: str):
    """Uproszczony parser formatu OSM opening_hours. Zwraca 7 list przedziałów [od, do] w minutach."""
    oh = oh.strip()
    if oh in ("24/7", "Mo-Su 00:00-24:00", "00:00-24:00"):
        return [[[0, 1440]] for _ in range(7)]
    week: list[list] = [[] for _ in range(7)]
    any_rule = False
    for rule in oh.split(";"):
        rule = rule.strip()
        if not rule or rule.startswith("PH") or rule.startswith("SH"):
            continue
        m = re.match(r"^([A-Za-z,\- ]+?)\s+(.+)$", rule)
        if m and parse_days(m.group(1).replace(" ", "")) is not None:
            days = parse_days(m.group(1).replace(" ", ""))
            times = m.group(2).strip()
        elif re.match(r"^\d", rule):
            days, times = list(range(7)), rule
        else:
            return None
        if times in ("off", "closed"):
            for d in days:
                week[d] = []
            any_rule = True
            continue
        ranges = []
        for t in times.split(","):
            tm = TIME_RE.match(t.strip())
            if not tm:
                return None
            a = int(tm.group(1)) * 60 + int(tm.group(2))
            b = int(tm.group(3)) * 60 + int(tm.group(4))
            if b <= a:
                b += 1440
            ranges.append([a, b])
        for d in days:
            week[d] = ranges
        any_rule = True
    return week if any_rule else None


def default_hours(cat: str):
    wk, sat, sun = DEFAULT_HOURS.get(cat, DEFAULT_HOURS["shop"])
    return [[list(wk)] if wk else [] for _ in range(5)] + [[list(sat)] if sat else [], [list(sun)] if sun else []]


POI_LABELS = {
    "convenience": "Sklep spożywczy", "supermarket": "Supermarket", "shop": "Sklep", "bar": "Bar / pub",
    "nightclub": "Klub", "restaurant": "Restauracja", "cafe": "Kawiarnia", "fast_food": "Bistro",
    "pharmacy": "Apteka", "fuel": "Stacja paliw", "police": "Policja", "hospital": "Szpital",
    "hotel": "Hotel (recepcja)", "culture": "Kino / teatr",
}

POI_WEIGHT = {
    "convenience": 1.0, "supermarket": 0.9, "shop": 0.6, "bar": 1.0, "nightclub": 0.8, "restaurant": 0.9,
    "cafe": 0.7, "fast_food": 0.9, "pharmacy": 0.9, "fuel": 1.0, "police": 1.6, "hospital": 1.2,
    "hotel": 0.9, "culture": 0.7,
}


def poi_category(tags: dict) -> str | None:
    am, sh, tu = tags.get("amenity"), tags.get("shop"), tags.get("tourism")
    if am in ("bar", "pub", "biergarten"):
        return "bar"
    if am in ("restaurant", "cafe", "fast_food", "pharmacy", "fuel", "police", "hospital", "nightclub"):
        return am
    if am == "ice_cream":
        return "cafe"
    if am in ("cinema", "theatre"):
        return "culture"
    if tu in ("hotel", "hostel"):
        return "hotel"
    if sh in ("convenience", "alcohol", "kiosk"):
        return "convenience"
    if sh in ("supermarket",):
        return "supermarket"
    if sh and sh not in ("vacant", "no"):
        return "shop"
    return None


# --------------------------------------------------------------------------- lighting

def lit_value(tags: dict) -> tuple[float, str] | None:
    v = (tags.get("lit") or "").lower()
    if v in ("yes", "24/7", "automatic", "sunset-sunrise", "dusk-dawn"):
        return 1.0, "osm"
    if v in ("limited", "interval", "disused"):
        return 0.5, "osm"
    if v == "no":
        return 0.0, "osm"
    return None


def estimate_lit(hw: str, tags: dict, env: str | None) -> float:
    if tags.get("footway") in ("sidewalk", "crossing") or tags.get("sidewalk"):
        return 0.75
    if hw in ("primary", "primary_link", "secondary", "secondary_link", "trunk", "trunk_link", "tertiary", "tertiary_link"):
        return 0.85
    if hw in ("residential", "living_street", "pedestrian", "corridor"):
        return 0.7 if not env else 0.5
    if hw in ("unclassified", "service"):
        return 0.45 if not env else 0.3
    if hw in ("footway", "cycleway", "steps"):
        return 0.45 if not env else 0.2
    return 0.15  # path, track


# --------------------------------------------------------------------------- main build

def main():
    print("Wczytywanie kafli OSM...")
    nodes, node_tags, ways, relations = parse_tiles()

    s, w, n, e = BBOX

    def in_bbox(p):
        return s <= p[0] <= n and w <= p[1] <= e

    print("Obszary...")
    areas = build_areas(nodes, ways, relations)
    area_grid = Grid(150)
    for a in areas:
        area_grid.insert_bbox(a, *a["bbox"])

    river_lines = [
        (wy["tags"].get("name", ""), [xy(*nodes[i]) for i in wy["nodes"] if i in nodes])
        for wy in ways.values() if wy["tags"].get("waterway") == "river"
    ]
    river_lines = [(nm, pts) for nm, pts in river_lines if len(pts) > 1]

    lamps = [xy(*nodes[i]) for i, t in node_tags.items() if t.get("highway") == "street_lamp" and i in nodes]
    lamp_grid = Grid(50)
    for lx, ly in lamps:
        lamp_grid.insert_point((lx, ly), lx, ly)
    print(f"  latarnie: {len(lamps)}, rzeka: {len(river_lines)} odcinków")

    print("Graf pieszy...")
    walk = {wid: wy for wid, wy in ways.items()
            if wy["tags"].get("highway") in WALKABLE
            and wy["tags"].get("foot") not in ("no", "private")
            and wy["tags"].get("access") not in ("no", "private")
            and wy["tags"].get("service") not in ("driveway", "parking_aisle")
            and wy["tags"].get("area") != "yes"}
    usage = defaultdict(int)
    for wy in walk.values():
        ids = [i for i in wy["nodes"] if i in nodes]
        for i in ids:
            usage[i] += 1
        if ids:
            usage[ids[0]] += 1
            usage[ids[-1]] += 1

    node_index: dict[int, int] = {}
    graph_nodes: list[tuple[float, float]] = []

    def gid(osm_id):
        if osm_id not in node_index:
            node_index[osm_id] = len(graph_nodes)
            graph_nodes.append(nodes[osm_id])
        return node_index[osm_id]

    edges = []
    for wid, wy in walk.items():
        tags = wy["tags"]
        ids = [i for i in wy["nodes"] if i in nodes]
        if len(ids) < 2:
            continue
        start = 0
        for k in range(1, len(ids)):
            if usage[ids[k]] > 1 or k == len(ids) - 1:
                seg = ids[start:k + 1]
                start = k
                pts = [nodes[i] for i in seg]
                if not any(in_bbox(p) for p in pts):
                    continue
                length = sum(dist_m(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
                if length < 0.5:
                    continue
                edges.append({"u": gid(seg[0]), "v": gid(seg[-1]), "pts": pts, "len": length, "tags": tags})

    print(f"  krawędzie: {len(edges)}, węzły: {len(graph_nodes)}")

    print("POI...")
    pois = []
    seen_names = set()
    for src_id, tags, pos in (
        [(f"n{i}", t, nodes[i]) for i, t in node_tags.items() if i in nodes]
        + [(f"w{wid}", wy["tags"], centroid([nodes[i] for i in wy["nodes"] if i in nodes]))
           for wid, wy in ways.items() if poi_category(wy["tags"]) and "highway" not in wy["tags"]]
    ):
        cat = poi_category(tags)
        if not cat or not pos or not in_bbox(pos):
            continue
        key = (tags.get("name"), round(pos[0], 4), round(pos[1], 4))
        if key in seen_names:
            continue
        seen_names.add(key)
        hours = None
        src = "est"
        if tags.get("opening_hours"):
            hours = parse_opening_hours(tags["opening_hours"])
            src = "osm" if hours else "est"
        if not hours:
            hours = default_hours(cat)
        pois.append({
            "name": tags.get("name") or POI_LABELS[cat], "cat": cat, "label": POI_LABELS[cat],
            "lat": round(pos[0], 6), "lon": round(pos[1], 6), "hours": hours, "src": src,
            "w": POI_WEIGHT[cat], "oh": tags.get("opening_hours"),
        })
    poi_grid = Grid(60)
    for i, p in enumerate(pois):
        x, y = xy(p["lat"], p["lon"])
        poi_grid.insert_point(i, x, y)
    print(f"  POI: {len(pois)}")

    print("Cechy krawędzi...")
    out_edges = []
    stats = defaultdict(int)
    for ed in edges:
        tags, pts = ed["tags"], ed["pts"]
        hw = tags["highway"]
        pxy = [xy(*p) for p in pts]
        samples = [pxy[0], pxy[len(pxy) // 2], pxy[-1]]
        mid = midpoint(pxy)

        # otoczenie
        env, env_risk, env_name = None, 0.0, None
        is_sidewalk = tags.get("footway") in ("sidewalk", "crossing")
        if not is_sidewalk:
            best = None
            for a in area_grid.query(*mid):
                minx, miny, maxx, maxy = a["bbox"]
                if not (minx <= mid[0] <= maxx and miny <= mid[1] <= maxy):
                    continue
                hits = sum(point_in_ring(x, y, a["ring"]) for x, y in samples + [mid])
                if hits >= 2 and (best is None or a["risk"] > best["risk"]):
                    best = a
            if best:
                env, env_risk, env_name = best["kind"], best["risk"], best["name"]
                if hw in ("primary", "secondary", "tertiary", "trunk", "residential"):
                    env_risk *= 0.4  # ulica przez park to wciąż ulica
        if tags.get("tunnel") == "yes" or (tags.get("layer", "0").lstrip("-").isdigit() and int(tags.get("layer", "0")) < 0):
            if hw in ("footway", "path", "cycleway", "steps", "corridor"):
                env, env_risk, env_name = "underpass", 0.7, tags.get("name")
        elif tags.get("tunnel") == "building_passage" and env is None:
            env, env_risk, env_name = "passage", 0.35, tags.get("name")
        if env is None and hw in ("footway", "path", "cycleway", "track", "service") and river_lines:
            d_river, river = min((point_polyline_dist(mid, pts), nm) for nm, pts in river_lines)
            if d_river < (110 if river == "Wisła" else 40):
                env, env_risk = "riverbank", 0.6
                env_name = "Bulwary Wiślane" if river == "Wisła" else f"Brzeg rzeki {river}".strip()

        # oświetlenie
        lv = lit_value(tags)
        if lv:
            lit, lit_src = lv
        else:
            nearby = sum(1 for lp in lamp_grid.query(*mid, radius=60)
                         if point_polyline_dist(lp, pxy) < 22)
            if nearby:
                lit, lit_src = min(1.0, 0.6 + 0.15 * nearby * 50 / max(ed["len"], 50)), "lamps"
            else:
                lit, lit_src = estimate_lit(hw, tags, env), "est"
        stats[lit_src] += 1

        # lokale w pobliżu (<= 45 m)
        near = []
        for pi in poi_grid.query(*mid, radius=ed["len"] / 2 + 60):
            p = pois[pi]
            d = point_polyline_dist(xy(p["lat"], p["lon"]), pxy)
            if d <= 45:
                near.append(pi)

        out_edges.append({
            "u": ed["u"], "v": ed["v"], "len": round(ed["len"], 1), "hw": hw,
            "name": tags.get("name"), "lit": round(lit, 2), "litSrc": lit_src,
            "env": env, "envRisk": round(env_risk, 2), "envName": env_name,
            "pois": near, "g": [[round(a, 6), round(b, 6)] for a, b in pts],
        })
    print(f"  źródło oświetlenia: {dict(stats)}")
    env_stats = defaultdict(int)
    for oe in out_edges:
        env_stats[oe["env"]] += 1
    print(f"  otoczenie: {dict(env_stats)}")

    data = {
        "bbox": BBOX, "nodes": [[round(a, 6), round(b, 6)] for a, b in graph_nodes],
        "edges": out_edges, "pois": pois,
        "meta": {"source": "© OpenStreetMap contributors (ODbL)", "lamps": len(lamps), "areas": len(areas)},
    }
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Zapisano {OUT} ({OUT.stat().st_size // 1024} kB)")


def centroid(pts):
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def midpoint(pxy):
    return pxy[len(pxy) // 2] if len(pxy) > 2 else ((pxy[0][0] + pxy[-1][0]) / 2, (pxy[0][1] + pxy[-1][1]) / 2)


if __name__ == "__main__":
    main()
