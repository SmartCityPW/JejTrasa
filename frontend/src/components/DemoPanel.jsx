import { CalendarDays, Clapperboard, Layers, Moon, RotateCcw, Sun, Sunrise, Sunset, Wand2 } from 'lucide-react'
import logoFull from '../assets/logo-full.png'
import { Switch } from './ui'
import { minutesOf, nowRounded, timeOf, withTime } from '../utils'

function toMin(hhmm) {
  if (!hhmm) return null
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

function skyGradient(ctx) {
  const night = '#22104a'
  if (!ctx?.sunrise) return `linear-gradient(90deg, ${night}, #fde68a, ${night})`
  const p = (m) => `${((m / 1440) * 100).toFixed(2)}%`
  const dawn = toMin(ctx.dawn)
  const rise = toMin(ctx.sunrise)
  const set = toMin(ctx.sunset)
  const dusk = toMin(ctx.dusk)
  return `linear-gradient(90deg, ${night} 0%, ${night} ${p(dawn)}, #f0a6ca ${p(rise)}, #fde9a8 ${p(rise + 50)}, #dcecff ${p(
    (rise + set) / 2,
  )}, #fde9a8 ${p(set - 50)}, #f0a6ca ${p(set)}, ${night} ${p(dusk)}, ${night} 100%)`
}

export default function DemoPanel({ meta, time, setTime, ctx, activeScenario, onScenario, layers, setLayers, boost, setBoost }) {
  const minutes = minutesOf(time)
  const setMinutes = (m) => {
    const h = String(Math.floor(m / 60)).padStart(2, '0')
    const mm = String(m % 60).padStart(2, '0')
    setTime(withTime(time, `${h}:${mm}`))
  }

  return (
    <>
      <div className="panel-card brand-block">
        <img src={logoFull} alt="Jej Trasa" />
        <p className="tagline">
          Nawigacja piesza, która wybiera trasę <b>bezpieczną o tej konkretnej porze</b> – na podstawie oświetlenia ulic, otwartych lokali,
          zgłoszeń zagrożeń i opinii innych kobiet.
        </p>
      </div>

      <div className="panel-card">
        <div className="panel-title">
          <Clapperboard size={18} /> Scenariusze demo
        </div>
        <p className="panel-sub">Ta sama trasa w dzień i w nocy – zobacz, jak zmienia się rekomendacja.</p>
        {meta?.scenarios.map((sc) => (
          <div key={sc.id} className={`scenario ${activeScenario?.id === sc.id ? 'active' : ''}`}>
            <h4>{sc.title}</h4>
            <p>{sc.story}</p>
            <div className="scenario-times">
              {sc.times.map((t) => {
                const isNight = toMin(t) < 360 || toMin(t) > 1140
                const selected = activeScenario?.id === sc.id && timeOf(time) === t
                return (
                  <button key={t} className={`time-btn ${isNight ? 'night' : ''} ${selected ? 'selected' : ''}`} onClick={() => onScenario(sc, t)}>
                    {isNight ? <Moon size={14} /> : <Sun size={14} />} {t}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="panel-card">
        <div className="panel-title">
          <Wand2 size={18} /> Wehikuł czasu
        </div>
        <p className="panel-sub">Przesuń godzinę – wskaźniki i trasy przeliczą się na żywo (pozycja Słońca, godziny otwarcia).</p>
        <div className="clock-big">
          <strong>{timeOf(time)}</strong>
          {ctx && (
            <span className={`phase-pill ${ctx.phase}`}>
              {ctx.phase === 'day' ? <Sun size={13} /> : <Moon size={13} />} {ctx.phaseLabel}
            </span>
          )}
        </div>
        <div className="sky-slider">
          <div className="sky-track" style={{ background: skyGradient(ctx) }} />
          <input type="range" min={0} max={1435} step={15} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
        </div>
        <div className="sky-labels">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
        {ctx && (
          <div className="sun-row">
            <span>
              <Sunrise size={14} /> {ctx.sunrise}
            </span>
            <span>
              <Sunset size={14} /> {ctx.sunset}
            </span>
            <span>
              <Moon size={14} /> zmrok {ctx.dusk}
            </span>
          </div>
        )}
        <div className="date-row">
          <CalendarDays size={16} color="#7c3aed" />
          <input type="date" value={time.slice(0, 10)} onChange={(e) => e.target.value && setTime(`${e.target.value}T${timeOf(time)}`)} />
          <button className="ghost-btn" onClick={() => setTime(nowRounded())}>
            <RotateCcw size={14} /> Teraz
          </button>
        </div>
      </div>

      <div className="panel-card">
        <div className="panel-title">
          <Layers size={18} /> Warstwy mapy
        </div>
        <div className="toggle-row" onClick={() => setLayers((l) => ({ ...l, heat: !l.heat }))}>
          <div className="t-text">
            <b>Mapa bezpieczeństwa</b>
            <small>Wskaźnik dla każdego z {meta?.dataset.segments.toLocaleString('pl-PL') ?? '…'} odcinków ulic</small>
            {layers.heat && (
              <div className="legend">
                <i style={{ background: '#E11D48' }} />
                <i style={{ background: '#F97316' }} />
                <i style={{ background: '#F5A524' }} />
                <i style={{ background: '#C4A2F7' }} />
                <i style={{ background: '#8B5CF6' }} />
                <i style={{ background: '#5B21B6' }} />
                <span style={{ marginLeft: 4 }}>ryzyko → bezpiecznie</span>
              </div>
            )}
          </div>
          <Switch on={layers.heat} />
        </div>
        <div className="toggle-row" onClick={() => setLayers((l) => ({ ...l, incidents: !l.incidents }))}>
          <div className="t-text">
            <b>Zgłoszenia zagrożeń</b>
            <small>KMZB (bordowe) i od użytkowniczek (pomarańczowe)</small>
          </div>
          <Switch on={layers.incidents} />
        </div>
        <div className="toggle-row" onClick={() => setBoost((b) => !b)}>
          <div className="t-text">
            <b>Tryb prezentacji opinii</b>
            <small>Jedna ankieta liczy się jak 20 – efekt widać od razu</small>
          </div>
          <Switch on={boost} />
        </div>
      </div>
    </>
  )
}
