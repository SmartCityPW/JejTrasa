# Jej Trasa

**Nawigacja piesza, która wybiera trasę bezpieczną o tej konkretnej porze.**

Najkrótsza droga przez park to w południe przyjemny spacer, a o 23:00 ciemna, pusta alejka. Jej Trasa wylicza
**wskaźnik bezpieczeństwa (0–100) dla każdego odcinka ulicy w zależności od godziny**. Bierze pod uwagę oświetlenie,
lokale otwarte o danej porze, zgłoszenia zagrożeń, otoczenie (parki, łąki, pustostany) i opinie innych kobiet.
Następnie proponuje trasy alternatywne i pokazuje, ile bezpieczeństwa daje każda dodatkowa minuta drogi.

> Prototyp na hackathon. Działa na **prawdziwej sieci ulic centrum Krakowa z OpenStreetMap** (oświetlenie, latarnie,
> godziny otwarcia, parki). Zgłoszenia z Krajowej Mapy Zagrożeń Bezpieczeństwa i historia opinii są **symulowane**.

## Funkcje

| Ekran | Co pokazuje |
|---|---|
| **Planowanie** | wybór startu i celu (lista miejsc lub punkt na mapie), godzina wyjścia, zachód słońca |
| **Propozycje tras** | do 3 tras (najbezpieczniejsza / zrównoważona / najszybsza) z wynikiem, czasem i porównaniem, np. „+11 min, ale omija Błonia, 580 m mniej po ciemku” |
| **Szczegóły bezpieczeństwa** | rozkład 5 czynników, % oświetlenia, otwarte lokale z godziną zamknięcia, zgłoszenia (KMZB i użytkowniczki), ryzykowne otoczenie, najsłabszy fragment trasy |
| **Nawigacja** | symulowany marsz po trasie, wskaźnik bieżącego odcinka, ostrzeżenia przed słabszymi fragmentami, udostępnianie lokalizacji zaufanym osobom, **SOS (przytrzymaj)**, zgłoszenie niebezpiecznego miejsca |
| **Ankieta po trasie** | kciuk w górę/w dół, poczucie bezpieczeństwa 1–5, oświetlenie, otwarte lokale, komentarz. Opinia **od razu zmienia wskaźnik** odcinków i kolejne trasy |

Na desktopie obok telefonu jest **panel demo** dla jury:
- **Scenariusze**: ta sama trasa w dzień i w nocy, jednym kliknięciem.
- **Wehikuł czasu**: suwak godziny i wybór daty. Trasy i mapa przeliczają się na żywo.
- **Mapa bezpieczeństwa**: wskaźnik dla wszystkich ~23 tys. odcinków ulic.
- **Tryb prezentacji opinii**: jedna ankieta liczy się jak 20, żeby efekt było widać od razu.

### Scenariusze demo

1. **AGH Kawiory → Salwator**: w dzień najkrótsza droga przez Błonia jest polecana. O 22:30 Błonia mają wynik ok. 50/100,
   a aplikacja proponuje obejście oświetlonymi ulicami (ok. 77/100).
2. **Plac Nowy → Akademik Żaczek o 2:00**: trasa omija zaułki z nocnymi zgłoszeniami zagrożeń (15 → 4 zgłoszenia, +2 min).
3. **Dworzec → Wawel o 23:45**: najszybsza droga przez Planty kontra oświetlone ulice Starego Miasta.

## Wskaźnik bezpieczeństwa

```
S = 100 · (0.30·L + 0.22·A + 0.20·I + 0.16·E + 0.12·U)
```

| | Czynnik | Jak liczony |
|---|---|---|
| **L** | oświetlenie | `d + (1−d)·lit`. `d` to poziom światła dziennego z **wysokości Słońca** (płynnie w zmierzchu cywilnym −6°…+6°), `lit` pochodzi z tagu OSM `lit`, zmapowanych latarni albo estymacji z typu drogi i jest korygowane ankietami |
| **A** | ruch i otwarte lokale | lokale **otwarte o tej godzinie** w promieniu 45 m (sklep całodobowy, bar, apteka, stacja, policja…) + typowy ruch na danym typie ulicy o tej porze |
| **I** | brak zgłoszeń | `exp(−0.55·P)`, gdzie `P` to suma zgłoszeń ważonych kategorią, dopasowaniem do pory dnia, świeżością i odległością |
| **E** | otoczenie | 1 − ryzyko terenu (las, łąka, park, pustostan, bulwar, przejście podziemne); ryzyko rośnie po zmroku |
| **U** | opinie | średnia bayesowska ocen odcinka z ankiet, **osobno dla dnia i nocy** |

- **Wynik trasy** = 65% średniej ważonej długością + 35% 10. percentyla, czyli trasa jest tak bezpieczna, jak jej najsłabszy fragment.
- **Trasy alternatywne** wyznacza algorytm Dijkstry z kosztem `długość · (1 + λ·(1 − S/100)²)`, gdzie λ = 0 / 5 / 14.

Kod: [backend/app/engine.py](backend/app/engine.py).

## Źródła danych

| Źródło | W prototypie | Docelowo |
|---|---|---|
| Sieć ulic, oświetlenie (`lit`, latarnie), parki, lokale, godziny otwarcia | **OpenStreetMap, prawdziwe dane** (13,6 tys. odcinków z tagiem `lit`, 3,7 tys. latarni, ~4 tys. lokali) | + miejskie rejestry oświetlenia, Google Places |
| Zgłoszenia zagrożeń | symulowane w kategoriach **Krajowej Mapy Zagrożeń Bezpieczeństwa** | dane KMZB / współpraca z Policją |
| Zgłoszenia i ankiety użytkowniczek | historia symulowana; **nowe zapisywane w SQLite** i od razu uwzględniane | baza aplikacji |
| Wschód i zachód Słońca | **obliczane** (algorytm NOAA) | jw. |

## Uruchomienie

Wymagania: Python 3.11+, Node 20+.

```bash
# 1. Backend (API na http://127.0.0.1:8000)
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# 2. Frontend (w drugim terminalu, http://localhost:5173)
cd frontend
npm install
npm run dev
```

Inny wariant to jeden serwer: `npm run build` w `frontend/`, a potem sam backend serwuje aplikację pod http://127.0.0.1:8000.

Przy pierwszym starcie backend tworzy `backend/data/jejtrasa.db` z historycznymi (symulowanymi) ocenami. Żeby
zresetować demo, wystarczy usunąć ten plik.

### Odświeżenie danych OSM (opcjonalne)

`backend/data/city.json.gz` jest w repozytorium. Żeby zbudować go od nowa z aktualnej OpenStreetMap:

```bash
cd backend
python scripts/fetch_osm.py      # pobiera 16 kafli z api.openstreetmap.org (~120 MB, do data/raw/)
python scripts/build_dataset.py  # graf pieszy + oświetlenie + otoczenie + lokale -> data/city.json.gz
```

## Architektura

```
backend/   Python · FastAPI
  app/city.py        graf pieszy, indeks przestrzenny
  app/engine.py      wskaźnik bezpieczeństwa, trasowanie, podsumowania tras
  app/sun.py         pozycja Słońca (NOAA)
  app/demo_data.py   miejsca, scenariusze, symulowane zgłoszenia KMZB i opinie
  app/storage.py     SQLite: ankiety, oceny odcinków, zgłoszenia
  scripts/           pobieranie i przetwarzanie OSM
frontend/  React · Vite · Leaflet
  src/screens/       Planowanie, Trasy, Szczegóły, Nawigacja, Ankieta
  src/components/    mapa, panel demo, panel „jak to działa”
```

API: `GET /api/meta`, `GET /api/context`, `POST /api/routes`, `GET /api/network`, `GET /api/scores`,
`GET /api/incidents`, `POST /api/survey`, `POST /api/reports`.

---

Dane mapy © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL).
