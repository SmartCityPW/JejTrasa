"""Pobiera surowe dane OpenStreetMap (oficjalne API openstreetmap.org) dla obszaru demo.

Uruchamiane jednorazowo przy przygotowaniu prototypu - wynik (data/raw/*.osm)
jest wejściem dla build_dataset.py. Aplikacja w runtime NIE łączy się z OSM.

    python scripts/fetch_osm.py
"""

import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.openstreetmap.org/api/0.6/map?bbox={w},{s},{e},{n}"

# Stare Miasto, Planty, Błonia, Kazimierz, Bulwary Wiślane, okolice AGH i Dworca
BBOX = (50.0450, 19.9000, 50.0720, 19.9560)  # south, west, north, east
GRID = (4, 4)  # rows, cols - API ma limit 50k węzłów na zapytanie

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_tile(name: str, s: float, w: float, n: float, e: float, depth: int = 0) -> None:
    out = RAW_DIR / f"{name}.osm"
    if out.exists() and "--force" not in sys.argv:
        print(f"[skip] {out.name}")
        return
    url = API.format(s=f"{s:.5f}", w=f"{w:.5f}", n=f"{n:.5f}", e=f"{e:.5f}")
    req = urllib.request.Request(url, headers={"User-Agent": "JejTrasa-hackathon-prototype/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            out.write_bytes(resp.read())
        print(f"[ok] {out.name} ({out.stat().st_size // 1024} kB)", flush=True)
        time.sleep(1)  # bądźmy uprzejmi dla API OSM
    except urllib.error.HTTPError as exc:
        if exc.code == 400 and depth < 3:  # za dużo węzłów - dzielimy kafel na 4
            print(f"[split] {name}")
            ms, mw = (s + n) / 2, (w + e) / 2
            for i, (a, b, c, d) in enumerate([(s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)]):
                fetch_tile(f"{name}_{i}", a, b, c, d, depth + 1)
        else:
            raise


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    s, w, n, e = BBOX
    rows, cols = GRID
    dlat, dlon = (n - s) / rows, (e - w) / cols
    for r in range(rows):
        for c in range(cols):
            fetch_tile(f"tile_{r}_{c}", s + r * dlat, w + c * dlon, s + (r + 1) * dlat, w + (c + 1) * dlon)
