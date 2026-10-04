"""Dane demonstracyjne (symulowane).

W docelowym produkcie te dane pochodziłyby z:
  * Krajowej Mapy Zagrożeń Bezpieczeństwa (Policja) - zgłoszenia zagrożeń,
  * zgłoszeń użytkowniczek aplikacji,
  * historii ocen przebytych tras.
W prototypie generujemy je deterministycznie (stałe ziarno), z "gorącymi punktami"
w miejscach, które dobrze ilustrują działanie algorytmu (Błonia nocą, bulwary pod mostami itd.).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .city import City

PLACES = [
    {"id": "zaczek", "name": "Akademik Żaczek", "address": "al. 3 Maja 5", "lat": 50.05985, "lon": 19.92585, "icon": "home"},
    {"id": "agh", "name": "AGH – budynek A-0", "address": "al. Mickiewicza 30", "lat": 50.06455, "lon": 19.92335, "icon": "school"},
    {"id": "rynek", "name": "Rynek Główny", "address": "Stare Miasto", "lat": 50.06170, "lon": 19.93730, "icon": "landmark"},
    {"id": "dworzec", "name": "Dworzec Główny", "address": "pl. Jana Nowaka-Jeziorańskiego", "lat": 50.06680, "lon": 19.94570, "icon": "train"},
    {"id": "plac-nowy", "name": "Plac Nowy (Kazimierz)", "address": "Kazimierz", "lat": 50.05150, "lon": 19.94480, "icon": "music"},
    {"id": "wawel", "name": "Wawel", "address": "Wzgórze Wawelskie", "lat": 50.05430, "lon": 19.93690, "icon": "castle"},
    {"id": "salwator", "name": "Salwator – Norbertanki", "address": "ul. Tadeusza Kościuszki", "lat": 50.05400, "lon": 19.91190, "icon": "home"},
    {"id": "kawiory", "name": "AGH – Kawiory", "address": "ul. Kawiory", "lat": 50.06700, "lon": 19.91200, "icon": "school"},
    {"id": "muzeum", "name": "Muzeum Narodowe", "address": "al. 3 Maja 1", "lat": 50.06055, "lon": 19.92330, "icon": "museum"},
    {"id": "bagatela", "name": "Teatr Bagatela", "address": "ul. Karmelicka 6", "lat": 50.06325, "lon": 19.93285, "icon": "theater"},
    {"id": "podgorze", "name": "Rynek Podgórski", "address": "Podgórze", "lat": 50.04595, "lon": 19.95055, "icon": "map"},
    {"id": "jordan", "name": "Park Jordana – wejście", "address": "al. 3 Maja", "lat": 50.06250, "lon": 19.91690, "icon": "tree"},
    {"id": "debniki", "name": "Dębniki – Rynek Dębnicki", "address": "Dębniki", "lat": 50.05065, "lon": 19.92290, "icon": "home"},
]

SCENARIOS = [
    {
        "id": "blonia", "title": "Z zajęć na AGH do domu na Salwatorze",
        "story": "Najkrótsza droga prowadzi przez Błonia – w dzień to przyjemny spacer, po zmroku ciemna, pusta łąka.",
        "from": "kawiory", "to": "salwator", "times": ["14:00", "22:30"],
    },
    {
        "id": "kazimierz", "title": "Z Kazimierza do akademika po imprezie",
        "story": "O 2:00 w nocy aplikacja omija zaułki, w których kobiety i Policja zgłaszały nocne zagrożenia.",
        "from": "plac-nowy", "to": "zaczek", "times": ["13:00", "02:00"],
    },
    {
        "id": "dworzec", "title": "Z dworca na Wawel późnym wieczorem",
        "story": "Planty są piękne w dzień, ale nocą bezpieczniej iść oświetlonymi ulicami Starego Miasta.",
        "from": "dworzec", "to": "wawel", "times": ["15:00", "23:45"],
    },
]

KMZB_CATEGORIES = {
    "aggression": ("Grupowanie się osób zachowujących się agresywnie", 1.0),
    "drugs": ("Używanie środków odurzających", 0.85),
    "alcohol": ("Spożywanie alkoholu w miejscach niedozwolonych", 0.6),
    "nightlife": ("Miejsca niebezpiecznej działalności rozrywkowej", 0.6),
    "vandalism": ("Akty wandalizmu", 0.4),
    "lighting": ("Niewłaściwe oświetlenie", 0.35),
}

USER_CATEGORIES = {
    "following": ("Ktoś mnie śledził", 1.0),
    "harassment": ("Zaczepki / catcalling", 0.9),
    "group": ("Podejrzana grupa osób", 0.8),
    "unease": ("Czułam się tu niepewnie", 0.5),
    "dark": ("Brak lub zepsute oświetlenie", 0.45),
    "vacant": ("Pustostan / opuszczony teren", 0.5),
}

# (lat, lon, promień m, liczba KMZB, liczba zgłoszeń użytkowniczek, kategorie KMZB, kategorie user, udział nocnych)
HOTSPOTS = [
    (50.0590, 19.9120, 380, 26, 18, ["aggression", "alcohol", "drugs"], ["following", "unease", "dark"], 0.9),  # Błonia
    (50.0625, 19.9150, 220, 10, 8, ["alcohol", "drugs", "vandalism"], ["unease", "group"], 0.85),  # Park Jordana
    (50.0548, 19.9290, 200, 14, 12, ["aggression", "alcohol"], ["harassment", "group", "following"], 0.9),  # bulwary - Most Dębnicki
    (50.0498, 19.9420, 220, 12, 10, ["drugs", "alcohol", "aggression"], ["following", "harassment"], 0.9),  # bulwary - Most Grunwaldzki
    (50.0480, 19.9495, 180, 9, 7, ["alcohol", "nightlife"], ["harassment", "unease"], 0.85),  # Bernatka
    (50.0658, 19.9415, 150, 11, 9, ["aggression", "drugs", "alcohol"], ["harassment", "group", "following"], 0.8),  # Planty przy Dworcu
    (50.0663, 19.9462, 120, 8, 6, ["aggression", "vandalism"], ["group", "harassment"], 0.75),  # przejście podziemne Dworzec
    (50.0565, 19.9395, 140, 6, 5, ["alcohol", "drugs"], ["unease", "dark"], 0.85),  # Planty przy Wawelu
    (50.0518, 19.9475, 150, 9, 6, ["nightlife", "alcohol"], ["harassment"], 0.95),  # Kazimierz - Dajwór
    (50.0480, 19.9330, 200, 6, 5, ["vandalism", "lighting"], ["vacant", "unease"], 0.8),  # Dębniki - zaułki
]


def generate_incidents(city: City, now: datetime) -> list[dict]:
    rng = random.Random(2026)
    incidents: list[dict] = []

    def place_near(lat, lon, radius):
        cands = [eid for eid, _ in city.edges_near(lat, lon, radius)]
        if not cands:
            return lat, lon
        e = city.edges[rng.choice(cands)]
        p = rng.choice(e.geom)
        jitter = 8 / 111_320
        return p[0] + rng.uniform(-jitter, jitter), p[1] + rng.uniform(-jitter, jitter)

    def hour(night_share):
        if rng.random() < night_share:
            return rng.choice([21, 22, 23, 0, 0, 1, 1, 2, 2, 3, 4])
        return rng.randint(8, 20)

    def add(source, cat, lat, lon, night_share):
        cats = KMZB_CATEGORIES if source == "kmzb" else USER_CATEGORIES
        label, weight = cats[cat]
        days = int(rng.expovariate(1 / 45)) % 180
        h = hour(night_share)
        incidents.append({
            "id": len(incidents), "source": source, "cat": cat, "label": label, "weight": weight,
            "lat": round(lat, 6), "lon": round(lon, 6), "hour": h,
            "date": (now - timedelta(days=days)).replace(hour=h, minute=rng.randint(0, 59)).isoformat(timespec="minutes"),
            "status": "potwierdzone" if source == "kmzb" else "zgłoszenie",
        })

    for lat, lon, radius, n_k, n_u, kc, uc, night in HOTSPOTS:
        for _ in range(n_k):
            add("kmzb", rng.choice(kc), *place_near(lat, lon, radius), night)
        for _ in range(n_u):
            add("user", rng.choice(uc), *place_near(lat, lon, radius), night)

    # tło - rzadkie, drobne zdarzenia w całym obszarze
    s, w, n, e = city.bbox
    for _ in range(90):
        lat, lon = rng.uniform(s, n), rng.uniform(w, e)
        src = "kmzb" if rng.random() < 0.6 else "user"
        cat = rng.choice(["vandalism", "lighting", "alcohol"] if src == "kmzb" else ["unease", "dark", "harassment"])
        add(src, cat, *place_near(lat, lon, 120), 0.5)
    return incidents


def seed_feedback(city: City) -> list[tuple[int, str, float, float | None, float | None]]:
    """Historyczne oceny odcinków: (edge_id, pora 'day'/'night', ocena 0..1, oświetlenie, lokale)."""
    rng = random.Random(7)
    rows = []
    hot_edges: set[int] = set()
    for lat, lon, radius, *_ in HOTSPOTS:
        for eid, _ in city.edges_near(lat, lon, radius * 0.8):
            hot_edges.add(eid)
    for eid in hot_edges:
        e = city.edges[eid]
        if e.hw in ("primary", "secondary", "tertiary", "trunk"):
            continue
        for _ in range(rng.randint(2, 6)):
            rows.append((eid, "night", rng.uniform(0.05, 0.4), rng.uniform(0.0, 0.5) if e.lit < 0.8 else None, None))
        for _ in range(rng.randint(1, 3)):
            rows.append((eid, "day", rng.uniform(0.55, 0.9), None, None))
    good = [e for e in city.edges if e.lit >= 0.9 and e.hw in ("primary", "secondary", "tertiary", "pedestrian")
            and e.id not in hot_edges]
    for e in rng.sample(good, min(1800, len(good))):
        for _ in range(rng.randint(1, 4)):
            rows.append((e.id, "night", rng.uniform(0.65, 1.0), rng.uniform(0.7, 1.0), rng.uniform(0.5, 1.0) if e.pois else None))
            rows.append((e.id, "day", rng.uniform(0.75, 1.0), None, None))
    return rows
