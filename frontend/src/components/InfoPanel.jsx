import { Database, Lightbulb, MessageSquareHeart, Rocket, ShieldAlert, Sigma, Store, Sun, Trees } from 'lucide-react'

const n = (v) => (v ?? 0).toLocaleString('pl-PL')

export default function InfoPanel({ meta }) {
  const d = meta?.dataset
  const w = meta?.weights ?? { L: 0.3, A: 0.22, I: 0.2, E: 0.16, U: 0.12 }
  const factors = [
    { k: 'L', title: 'Oświetlenie', text: 'Po zmroku: czy ulica jest oświetlona. W dzień – światło słoneczne (z pozycji Słońca, z płynnym zmierzchem).' },
    { k: 'A', title: 'Ruch i otwarte lokale', text: 'Sklepy, bary, apteki, stacje otwarte o wybranej godzinie w promieniu 45 m + typowy ruch na ulicy.' },
    { k: 'I', title: 'Brak zgłoszeń', text: 'Zgłoszenia ważone porą dnia, świeżością i odległością od trasy.' },
    { k: 'E', title: 'Otoczenie', text: 'Parki, łąki, lasy, pustostany, bulwary, przejścia podziemne – ryzyko rośnie po zmroku.' },
    { k: 'U', title: 'Opinie użytkowniczek', text: 'Średnia bayesowska ocen odcinka z ankiet – osobno dla dnia i nocy.' },
  ]

  return (
    <>
      <div className="panel-card">
        <div className="panel-title">
          <Sigma size={18} /> Jak liczymy wskaźnik?
        </div>
        <p className="panel-sub">Każdy odcinek ulicy dostaje wynik 0–100, przeliczany dla wybranej daty i godziny.</p>
        <div className="formula">
          S = 100 · ({w.L}·L + {w.A}·A + {w.I}·I + {w.E}·E + {w.U}·U)
        </div>
        <ul className="factor-list">
          {factors.map((f) => (
            <li key={f.k}>
              <span className="factor-key">{f.k}</span>
              <span>
                <b>{f.title}</b>
                {f.text}
              </span>
              <span className="factor-w">{Math.round(w[f.k] * 100)}%</span>
            </li>
          ))}
        </ul>
        <p className="panel-sub" style={{ marginTop: 12, marginBottom: 0 }}>
          <b>Wynik trasy</b> = 65% średniej + 35% najsłabszych fragmentów (10. percentyl) – trasa jest tak bezpieczna, jak jej najciemniejszy
          zaułek. Trasy alternatywne wyznacza algorytm Dijkstry z kosztem <i>długość · (1 + λ·(1−S)²)</i>.
        </p>
      </div>

      <div className="panel-card">
        <div className="panel-title">
          <Database size={18} /> Skąd dane?
        </div>
        <p className="panel-sub">Prototyp działa na prawdziwej sieci ulic centrum Krakowa. Część źródeł jest symulowana.</p>
        <div className="source-list">
          <div className="source">
            <span className="s-ico">
              <Lightbulb size={17} />
            </span>
            <div>
              <b>
                OpenStreetMap – oświetlenie <span className="tag real">prawdziwe</span>
              </b>
              <small>
                {n(d?.segmentsWithOsmLighting)} odcinków z tagiem <code>lit</code>, {n(d?.streetLamps)} zmapowanych latarni. Docelowo: rejestry
                oświetlenia miast (np. ZDMK).
              </small>
            </div>
          </div>
          <div className="source">
            <span className="s-ico">
              <Store size={17} />
            </span>
            <div>
              <b>
                OSM – lokale i godziny otwarcia <span className="tag real">prawdziwe</span>
              </b>
              <small>
                {n(d?.venues)} lokali, {n(d?.venuesWithOsmHours)} z godzinami z OSM (reszta – typowe dla kategorii). Docelowo: Google Places API.
              </small>
            </div>
          </div>
          <div className="source">
            <span className="s-ico">
              <Trees size={17} />
            </span>
            <div>
              <b>
                OSM – parki, lasy, pustostany <span className="tag real">prawdziwe</span>
              </b>
              <small>Poligony landuse/leisure, bulwary nad Wisłą, przejścia podziemne.</small>
            </div>
          </div>
          <div className="source">
            <span className="s-ico">
              <ShieldAlert size={17} />
            </span>
            <div>
              <b>
                Krajowa Mapa Zagrożeń Bezpieczeństwa <span className="tag sim">symulacja</span>
              </b>
              <small>{n(d?.policeIncidents)} zgłoszeń w kategoriach KMZB. Docelowo: współpraca z Policją / dane publiczne KMZB.</small>
            </div>
          </div>
          <div className="source">
            <span className="s-ico">
              <MessageSquareHeart size={17} />
            </span>
            <div>
              <b>
                Zgłoszenia i ankiety użytkowniczek <span className="tag live">na żywo</span>
              </b>
              <small>
                {n(d?.userIncidents)} zgłoszeń, {n(d?.ratings)} ocen dla {n(d?.rated_segments)} odcinków (historia symulowana, nowe zapisywane w
                bazie i od razu wpływają na trasy).
              </small>
            </div>
          </div>
          <div className="source">
            <span className="s-ico">
              <Sun size={17} />
            </span>
            <div>
              <b>
                Wschód i zachód Słońca <span className="tag calc">obliczane</span>
              </b>
              <small>Algorytm NOAA – wysokość Słońca dla dowolnej daty i godziny.</small>
            </div>
          </div>
        </div>
      </div>

      <div className="panel-card">
        <div className="panel-title">
          <Rocket size={18} /> Co dalej?
        </div>
        <ul className="roadmap">
          <li>Integracja z KMZB, miejskimi rejestrami oświetlenia i Google Places</li>
          <li>„Bezpieczne punkty” – lokale-partnerzy, w których można przeczekać</li>
          <li>Wspólny powrót – dopasowanie kobiet idących w tę samą stronę</li>
          <li>Tryb dyskretny na zegarku i powiadomienie przy zejściu z trasy</li>
          <li>Raporty dla miast: gdzie brakuje latarni wg zgłoszeń kobiet</li>
        </ul>
      </div>
    </>
  )
}
