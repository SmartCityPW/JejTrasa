import { AlertTriangle, ArrowLeft, ChevronRight, Lightbulb, Moon, Navigation, ShieldAlert, Sparkles, Store, Sun, Trees } from 'lucide-react'
import { ScoreRing, Spinner } from '../components/ui'
import { fmtDistance, fmtMinutes, pct, plural, timeOf } from '../utils'

function minutesUntil(from, hhmm) {
  if (!hhmm) return null
  const [h, m] = hhmm.split(':').map(Number)
  const [fh, fm] = timeOf(from).split(':').map(Number)
  return h * 60 + m - (fh * 60 + fm)
}

export function ContextBanner({ ctx, time }) {
  if (!ctx) return null
  if (ctx.phase === 'day') {
    const left = minutesUntil(time, ctx.sunset)
    return (
      <div className="context-banner day">
        <Sun size={20} />
        <span>
          Jest jasno{left > 0 ? ` – do zachodu słońca ${fmtMinutes(left)}` : ''}. W dzień liczą się głównie zgłoszenia i ruch na ulicach.
        </span>
      </div>
    )
  }
  return (
    <div className={`context-banner ${ctx.phase}`}>
      <Moon size={20} />
      <span>
        {ctx.phase === 'twilight' ? 'Zapada zmrok' : `Po zmroku (zachód ${ctx.sunset})`} – trasy uwzględniają oświetlenie ulic i lokale otwarte o{' '}
        {timeOf(time)}.
      </span>
    </div>
  )
}

function compareText(r) {
  const c = r.compare
  if (!c || (c.extraMeters <= 0 && c.scoreGain <= 0)) return null
  const parts = []
  if (c.avoidedZones.length) parts.push(`omija: ${c.avoidedZones.slice(0, 2).join(', ')}`)
  if (c.avoidedUnlit > 40) parts.push(`${fmtDistance(c.avoidedUnlit)} mniej po ciemku`)
  if (c.avoidedIncidents > 0) parts.push(`${c.avoidedIncidents} ${plural(c.avoidedIncidents, 'zgłoszenie', 'zgłoszenia', 'zgłoszeń')} mniej`)
  if (c.extraOpenVenues > 2) parts.push(`+${c.extraOpenVenues} otwartych lokali`)
  if (!parts.length) return null
  const time = c.extraMinutes > 0 ? `+${c.extraMinutes} min, ale ` : ''
  return time + parts.join(' · ')
}

export function RouteChips({ route, ctx }) {
  const night = ctx?.phase !== 'day'
  const zones = route.zones.filter((z) => z.kind !== 'passage')
  return (
    <div className="mini-chips">
      {night ? (
        <span className={`mini-chip ${route.lighting.litShare < 0.85 ? 'warn' : ''}`}>
          <Lightbulb size={12} /> {pct(route.lighting.litShare)} oświetlona
        </span>
      ) : (
        <span className="mini-chip">
          <Sun size={12} /> światło dzienne
        </span>
      )}
      <span className="mini-chip">
        <Store size={12} /> {route.venues.open} {plural(route.venues.open, 'otwarty lokal', 'otwarte lokale', 'otwartych lokali')}
      </span>
      {route.incidents.total > 0 && (
        <span className={`mini-chip ${route.incidents.total > 6 ? 'bad' : 'warn'}`}>
          <ShieldAlert size={12} /> {route.incidents.total} {plural(route.incidents.total, 'zgłoszenie', 'zgłoszenia', 'zgłoszeń')}
        </span>
      )}
      {zones.slice(0, 1).map((z) => (
        <span key={z.label + z.name} className={`mini-chip ${night ? 'bad' : ''}`}>
          <Trees size={12} /> {z.name ?? z.label} · {fmtDistance(z.length)}
        </span>
      ))}
    </div>
  )
}

export default function RoutesScreen({ origin, destination, time, ctx, plan, loading, error, selectedId, onSelect, onBack, onDetails, onStart }) {
  return (
    <>
      <div className="screen-top">
        <button className="glass icon-btn" onClick={onBack}>
          <ArrowLeft size={20} />
        </button>
        <div className="glass trip-summary">
          <b>
            {origin?.name} → {destination?.name}
          </b>
          <small>
            {ctx?.phase === 'day' ? <Sun size={12} /> : <Moon size={12} />} {timeOf(time)} · pieszo
          </small>
        </div>
      </div>

      <div className="sheet" style={{ maxHeight: '58%' }}>
        <div className="grip" />
        <div className="sheet-scroll">
          {loading && !plan && <Spinner>Analizuję oświetlenie, lokale i zgłoszenia…</Spinner>}
          {error && <div className="error-box">{error}</div>}
          {plan && (
            <>
              <ContextBanner ctx={ctx} time={time} />
              {plan.routes.length === 1 && (
                <div className="context-banner day" style={{ background: 'var(--v-50)', color: 'var(--v-800)' }}>
                  <Sparkles size={18} />
                  <span>Najszybsza trasa jest też najbezpieczniejsza – nie musisz nadkładać drogi.</span>
                </div>
              )}
              {plan.routes.map((r) => {
                const cmp = compareText(r)
                return (
                  <div
                    key={r.id}
                    role="button"
                    tabIndex={0}
                    className={`route-card ${r.id === selectedId ? 'selected' : ''}`}
                    onClick={() => onSelect(r.id)}
                  >
                    <ScoreRing score={r.score} size={60} stroke={6} />
                    <div>
                      <div className="rc-head">
                        <b>{r.label}</b>
                        {r.recommended && <span className="badge-rec">Polecana</span>}
                      </div>
                      <div className="rc-meta">
                        {fmtMinutes(r.duration)}
                        <span>•</span>
                        {fmtDistance(r.distance)}
                        <span>•</span>
                        <span style={{ color: 'inherit', margin: 0 }}>{r.level.label}</span>
                      </div>
                      <RouteChips route={r} ctx={ctx} />
                      {cmp && (
                        <div className="rc-compare">
                          <Sparkles size={13} /> {cmp}
                        </div>
                      )}
                      {r.weakest && r.weakest.score < 50 && ctx?.phase !== 'day' && (
                        <div className="rc-compare" style={{ color: '#be123c' }}>
                          <AlertTriangle size={13} /> Słaby punkt: {r.weakest.name} ({r.weakest.score}/100)
                        </div>
                      )}
                      {r.id === selectedId && (
                        <div className="cta-row" style={{ marginTop: 12 }}>
                          <button
                            className="cta secondary"
                            style={{ padding: '11px 12px', fontSize: 13.5 }}
                            onClick={(e) => {
                              e.stopPropagation()
                              onDetails(r.id)
                            }}
                          >
                            Szczegóły <ChevronRight size={16} />
                          </button>
                          <button
                            className="cta"
                            style={{ padding: '11px 12px', fontSize: 13.5 }}
                            onClick={(e) => {
                              e.stopPropagation()
                              onStart(r.id)
                            }}
                          >
                            <Navigation size={16} /> Start
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </>
          )}
        </div>
      </div>
    </>
  )
}
