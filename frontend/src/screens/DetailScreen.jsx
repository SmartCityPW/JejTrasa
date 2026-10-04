import {
  AlertTriangle,
  ArrowLeft,
  Lightbulb,
  MessageSquareHeart,
  Navigation,
  ShieldAlert,
  Store,
  Trees,
} from 'lucide-react'
import { ScoreRing } from '../components/ui'
import { LEVEL_COLORS, fmtDistance, fmtMinutes, levelOf, pct, plural } from '../utils'

const FACTOR_HINT = {
  L: 'OSM: tag lit + latarnie',
  A: 'godziny otwarcia + ruch',
  I: 'KMZB + zgłoszenia',
  E: 'parki, łąki, pustostany',
  U: 'ankiety po trasie',
}

const VENUE_PRIORITY = ['police', 'hospital', 'fuel', 'convenience', 'pharmacy', 'bar', 'fast_food', 'restaurant', 'hotel']

export default function DetailScreen({ route, ctx, onBack, onStart }) {
  const night = ctx?.phase !== 'day'
  const lvl = levelOf(route.score)
  const zones = route.zones.filter((z) => z.kind !== 'passage')
  const venues = [...route.venues.list].sort((a, b) => {
    const pa = VENUE_PRIORITY.indexOf(a.cat)
    const pb = VENUE_PRIORITY.indexOf(b.cat)
    return (pa < 0 ? 99 : pa) - (pb < 0 ? 99 : pb)
  })

  return (
    <>
      <div className="screen-top">
        <button className="glass icon-btn" onClick={onBack}>
          <ArrowLeft size={20} />
        </button>
        <div className="glass trip-summary">
          <b>{route.label}</b>
          <small>
            {fmtMinutes(route.duration)} · {fmtDistance(route.distance)}
          </small>
        </div>
      </div>

      <div className="sheet" style={{ maxHeight: '64%' }}>
        <div className="grip" />
        <div className="sheet-scroll">
          <div className="detail-hero">
            <ScoreRing score={route.score} size={88} stroke={9} />
            <div>
              <span className="eyebrow">Wskaźnik bezpieczeństwa</span>
              <h2>{lvl.label} trasa</h2>
              <span className={`level-pill ${lvl.id}`}>
                {night ? `o tej porze (${ctx?.phaseLabel?.toLowerCase()})` : 'w ciągu dnia'}
              </span>
            </div>
          </div>

          <div className="factor-bars">
            {route.factors.map((f) => (
              <div key={f.key} className="fbar">
                <span className="lbl">
                  {f.label}
                  <small>{FACTOR_HINT[f.key]}</small>
                </span>
                <span className="v">{Math.round(f.value * 100)}</span>
                <div className="track">
                  <i style={{ width: `${f.value * 100}%`, background: LEVEL_COLORS[levelOf(f.value * 100).id] }} />
                </div>
              </div>
            ))}
          </div>

          {route.weakest && route.weakest.score < 60 && (
            <div className="info-card" style={{ borderColor: '#fecdd3', background: '#fff7f9' }}>
              <div className="ic-head">
                <span className="ic-ico bad">
                  <AlertTriangle size={18} />
                </span>
                <div>
                  <h4>Najsłabszy fragment: {route.weakest.name}</h4>
                  <small>{route.weakest.reasons.join(', ') || 'niższy wskaźnik niż reszta trasy'}</small>
                </div>
                <span className="ic-big" style={{ color: 'var(--rose)' }}>
                  {route.weakest.score}
                </span>
              </div>
            </div>
          )}

          <div className="info-card">
            <div className="ic-head">
              <span className={`ic-ico ${night && route.lighting.litShare < 0.85 ? 'warn' : ''}`}>
                <Lightbulb size={18} />
              </span>
              <div>
                <h4>Oświetlenie</h4>
                <small>{night ? 'Po zmroku – kluczowy czynnik' : 'Teraz jest jasno – ważne po zmroku'}</small>
              </div>
              <span className="ic-big">{pct(route.lighting.litShare)}</span>
            </div>
            <div className="ic-body">
              {route.lighting.unlitMeters > 0
                ? `${fmtDistance(route.lighting.unlitMeters)} trasy prowadzi słabo oświetlonymi odcinkami.`
                : 'Cała trasa prowadzi oświetlonymi ulicami.'}{' '}
              Dla {pct(route.lighting.verifiedShare)} trasy oświetlenie potwierdzają dane OpenStreetMap (tag <code>lit</code> lub
              zmapowane latarnie).
            </div>
          </div>

          <div className="info-card">
            <div className="ic-head">
              <span className="ic-ico">
                <Store size={18} />
              </span>
              <div>
                <h4>Otwarte lokale po drodze</h4>
                <small>
                  W promieniu 45 m od trasy · {route.venues.closed} {plural(route.venues.closed, 'zamknięty', 'zamknięte', 'zamkniętych')}
                </small>
              </div>
              <span className="ic-big">{route.venues.open}</span>
            </div>
            {venues.length > 0 ? (
              <ul className="venue-list">
                {venues.slice(0, 5).map((v, i) => (
                  <li key={i}>
                    <span className="vn">
                      {v.name}
                      <small>{v.label}</small>
                    </span>
                    <span className="until">do {v.until}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="ic-body">Na tej trasie o tej porze nie ma otwartych lokali – nie będzie gdzie się schronić.</div>
            )}
          </div>

          <div className="info-card">
            <div className="ic-head">
              <span className={`ic-ico ${route.incidents.total > 6 ? 'bad' : route.incidents.total > 0 ? 'warn' : ''}`}>
                <ShieldAlert size={18} />
              </span>
              <div>
                <h4>Zgłoszenia zagrożeń</h4>
                <small>Ostatnie 6 miesięcy, do 45 m od trasy</small>
              </div>
              <span className="ic-big">{route.incidents.total}</span>
            </div>
            <div className="split-stat">
              <div>
                <b>{route.incidents.police}</b>
                <small>Krajowa Mapa Zagrożeń (Policja)</small>
              </div>
              <div>
                <b>{route.incidents.users}</b>
                <small>od użytkowniczek aplikacji</small>
              </div>
            </div>
            {route.incidents.categories.length > 0 && (
              <div className="cat-list">
                {route.incidents.categories.slice(0, 4).map((c) => (
                  <span key={c.label} className="mini-chip warn">
                    {c.label} · {c.count}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="info-card">
            <div className="ic-head">
              <span className={`ic-ico ${zones.length && night ? 'bad' : ''}`}>
                <Trees size={18} />
              </span>
              <div>
                <h4>Otoczenie</h4>
                <small>Parki, łąki, pustostany, przejścia podziemne</small>
              </div>
            </div>
            <div className="ic-body">
              {zones.length === 0 ? (
                'Trasa omija tereny zielone, nieużytki i przejścia podziemne.'
              ) : (
                <div className="cat-list" style={{ marginTop: 0 }}>
                  {zones.map((z) => (
                    <span key={z.label + z.name} className={`mini-chip ${night ? 'bad' : ''}`}>
                      {z.name ? `${z.name} (${z.label.toLowerCase()})` : z.label} · {fmtDistance(z.length)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="info-card">
            <div className="ic-head">
              <span className="ic-ico">
                <MessageSquareHeart size={18} />
              </span>
              <div>
                <h4>Opinie innych kobiet</h4>
                <small>Oceny odcinków tej trasy {night ? 'po zmroku' : 'w ciągu dnia'}</small>
              </div>
              <span className="ic-big">{route.feedback.avg != null ? `${Math.round(route.feedback.avg * 100)}%` : '–'}</span>
            </div>
            <div className="ic-body">
              {route.feedback.count > 0
                ? `${route.feedback.count} ${plural(route.feedback.count, 'ocena', 'oceny', 'ocen')} odcinków – średnio ${Math.round(
                    route.feedback.avg * 100,
                  )}% poczucia bezpieczeństwa.`
                : 'Nikt jeszcze nie ocenił tych odcinków o tej porze – bądź pierwsza!'}
            </div>
          </div>

          <div className="sticky-cta">
            <button className="cta" style={{ marginTop: 0 }} onClick={onStart}>
              <Navigation size={18} /> Rozpocznij trasę
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
