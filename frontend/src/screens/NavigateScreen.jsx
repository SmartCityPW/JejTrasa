import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Ban,
  Check,
  EyeOff,
  Flag,
  Footprints,
  Lightbulb,
  LocateFixed,
  Megaphone,
  Pause,
  Phone,
  Play,
  Share2,
  ShieldAlert,
  Store,
  Trees,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react'
import { buildTrack, fmtDistance, haversine, pointAt, timeOf } from '../utils'

const WALK = 1.3 // m/s
const SPEEDS = [10, 30, 60]
const CONTACTS = [
  { name: 'Mama', color: '#7c3aed' },
  { name: 'Ola', color: '#e59a0b' },
]

const REPORT_ICONS = {
  following: Footprints,
  harassment: Megaphone,
  group: UsersRound,
  unease: EyeOff,
  dark: Lightbulb,
  vacant: Ban,
}

function addMinutes(iso, min) {
  const [h, m] = timeOf(iso).split(':').map(Number)
  const t = (h * 60 + m + Math.round(min)) % 1440
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}

function SosOverlay({ onClose, nearestVenue }) {
  const [count, setCount] = useState(3)
  const [stage, setStage] = useState(0)

  useEffect(() => {
    if (count > 0) {
      const t = setTimeout(() => setCount((c) => c - 1), 1000)
      return () => clearTimeout(t)
    }
    const t = setInterval(() => setStage((s) => Math.min(s + 1, 4)), 700)
    return () => clearInterval(t)
  }, [count])

  const steps = [
    { icon: Phone, text: 'Łączenie z numerem alarmowym 112 (symulacja)' },
    { icon: Share2, text: 'SMS z Twoją lokalizacją wysłany do: Mama, Ola' },
    { icon: Megaphone, text: 'Nagrywanie dźwięku i głośny alarm włączone' },
    {
      icon: Store,
      text: nearestVenue ? `Najbliższe otwarte miejsce: ${nearestVenue.name} (${fmtDistance(nearestVenue.d)})` : 'Szukam najbliższego otwartego miejsca…',
    },
  ]

  return (
    <div className="sos-screen">
      <div className="sos-pulse">{count > 0 ? <strong>{count}</strong> : <Phone size={56} />}</div>
      <h2>{count > 0 ? 'Wzywam pomoc…' : 'Pomoc jest w drodze'}</h2>
      <p>{count > 0 ? 'Za chwilę połączymy Cię z 112 i powiadomimy zaufane osoby.' : 'Zostań w oświetlonym miejscu. Jesteśmy z Tobą.'}</p>
      <div className="sos-steps">
        {steps.map((s, i) => (
          <div key={i} className={count > 0 || stage <= i ? 'pending' : ''}>
            {count === 0 && stage > i ? <Check size={18} /> : <s.icon size={18} />}
            {s.text}
          </div>
        ))}
      </div>
      <button className="sos-cancel" onClick={onClose}>
        {count > 0 ? 'Anuluj – to pomyłka' : 'Jestem bezpieczna – zakończ alarm'}
      </button>
    </div>
  )
}

function ReportSheet({ categories, onClose, onSubmit }) {
  const [cat, setCat] = useState(null)
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="grip" style={{ width: 40, height: 5, borderRadius: 3, background: 'var(--v-200)', margin: '0 auto 12px' }} />
        <h3>Zgłoś niebezpieczne miejsce</h3>
        <p className="lead">Zgłoszenie jest anonimowe i od razu wpływa na trasy innych kobiet w tej okolicy.</p>
        <div className="report-grid">
          {categories.map((c) => {
            const Icon = REPORT_ICONS[c.id] ?? Flag
            return (
              <button key={c.id} className={`report-opt ${cat === c.id ? 'selected' : ''}`} onClick={() => setCat(c.id)}>
                <Icon size={20} />
                {c.label}
              </button>
            )
          })}
        </div>
        <button className="cta" disabled={!cat} onClick={() => onSubmit(cat)}>
          <Flag size={17} /> Wyślij zgłoszenie
        </button>
      </div>
    </div>
  )
}

export default function NavigateScreen({ route, time, ctx, categories, onPosition, onArrive, onExit, onReport, following, setFollowing }) {
  const track = useMemo(() => buildTrack(route.coords), [route])
  const [dist, setDist] = useState(0)
  const [speed, setSpeed] = useState(30)
  const [paused, setPaused] = useState(false)
  const [sharing, setSharing] = useState(true)
  const [sos, setSos] = useState(false)
  const [reporting, setReporting] = useState(false)
  const [hold, setHold] = useState(0)
  const holdTimer = useRef(null)
  const arrived = useRef(false)

  // skala: długość geometrii vs długość z grafu (minimalne różnice)
  const scale = route.distance / (track.total || 1)
  const realDist = dist * scale

  useEffect(() => {
    if (paused || sos || reporting) return undefined
    const id = setInterval(() => {
      setDist((d) => Math.min(track.total, d + (WALK * speed * 0.25) / scale))
    }, 250)
    return () => clearInterval(id)
  }, [paused, sos, reporting, speed, track.total, scale])

  const { pos } = pointAt(track, dist)

  useEffect(() => {
    onPosition(pos)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pos[0], pos[1]])

  useEffect(() => {
    if (dist >= track.total && !arrived.current) {
      arrived.current = true
      setTimeout(onArrive, 600)
    }
  }, [dist, track.total, onArrive])

  const step = route.steps.find((s) => realDist >= s.start && realDist < s.end) ?? route.steps[route.steps.length - 1]
  const upcoming = route.steps.find(
    (s) => s.start > realDist && s.start - realDist < 160 && (s.score < 58 || (s.env && ctx?.phase !== 'day' && s.env !== 'passage')),
  )
  const currentRisky = step && step.score < 55

  const remaining = Math.max(0, route.distance - realDist)
  const eta = addMinutes(time, remaining / WALK / 60)
  const progress = Math.min(1, realDist / route.distance)

  const nearestVenue = useMemo(() => {
    let best = null
    for (const v of route.venues.list) {
      const d = haversine(pos, [v.lat, v.lon])
      if (!best || d < best.d) best = { ...v, d }
    }
    return best
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sos])

  const startHold = () => {
    const t0 = Date.now()
    holdTimer.current = setInterval(() => {
      const p = Math.min(1, (Date.now() - t0) / 1200)
      setHold(p)
      if (p >= 1) {
        clearInterval(holdTimer.current)
        setHold(0)
        setSos(true)
      }
    }, 30)
  }
  const endHold = () => {
    clearInterval(holdTimer.current)
    setHold(0)
  }

  const scoreBg = step?.score >= 75 ? 'rgba(196,181,253,0.25)' : step?.score >= 55 ? 'rgba(229,154,11,0.35)' : 'rgba(225,29,72,0.45)'

  return (
    <>
      <div className="nav-top">
        <div className="now">
          <div className="street">
            <small>Idziesz</small>
            <b>{step?.name}</b>
          </div>
          <div className="seg-score" style={{ background: scoreBg }}>
            <strong>{step?.score}</strong>
            <span>odcinek</span>
          </div>
        </div>
        <div className="facts">
          {ctx?.phase !== 'day' && (
            <span className="fact">
              <Lightbulb size={12} /> {step?.lit >= 0.6 ? 'oświetlone' : 'słabe światło'}
            </span>
          )}
          <span className="fact">
            <Store size={12} /> {step?.openPois ?? 0} otwarte
          </span>
          {step?.envLabel && step.env !== 'passage' && (
            <span className="fact">
              <Trees size={12} /> {step.envLabel}
            </span>
          )}
          {step?.incidents > 0 && (
            <span className="fact">
              <ShieldAlert size={12} /> {step.incidents} zgł.
            </span>
          )}
        </div>
        <div className="nav-progress">
          <i style={{ width: `${progress * 100}%` }} />
        </div>
        <div className="nav-eta">
          <span>Zostało {fmtDistance(remaining)}</span>
          <span>Dotrzesz ok. {eta}</span>
        </div>
      </div>

      {(upcoming || currentRisky) && (
        <div className={`nav-warning ${currentRisky ? 'bad' : ''}`} style={{ top: 228 }}>
          <AlertTriangle size={20} color={currentRisky ? '#e11d48' : '#e59a0b'} style={{ flexShrink: 0 }} />
          <div>
            {currentRisky ? (
              <>
                <b>Słabiej oceniany odcinek</b>
                Twoja lokalizacja jest udostępniana. Przytrzymaj SOS, jeśli poczujesz zagrożenie.
              </>
            ) : (
              <>
                <b>
                  Za {fmtDistance(upcoming.start - realDist)}: {upcoming.name}
                </b>
                {upcoming.envLabel ? `${upcoming.envLabel} – ` : ''}
                wskaźnik {upcoming.score}/100. Trzymaj się oświetlonej strony.
              </>
            )}
          </div>
        </div>
      )}

      <div className="nav-side" style={{ bottom: 200 }}>
        <button className="fab" onClick={() => setReporting(true)} title="Zgłoś niebezpieczne miejsce" aria-label="Zgłoś">
          <Flag size={20} />
        </button>
        <button className={`fab ${following ? 'active' : ''}`} onClick={() => setFollowing((f) => !f)} title="Śledź moją pozycję">
          <LocateFixed size={20} />
        </button>
      </div>

      <div className="nav-bottom">
        <div className="nav-bottom-row">
          <button className={`side-action ${sharing ? 'on' : ''}`} onClick={() => setSharing((s) => !s)}>
            <div className="avatars">
              {sharing ? (
                CONTACTS.map((c) => (
                  <span key={c.name} style={{ background: c.color }}>
                    {c.name[0]}
                  </span>
                ))
              ) : (
                <span style={{ background: '#c4b5fd' }}>
                  <UserRound size={13} />
                </span>
              )}
            </div>
            <b>{sharing ? 'Mama, Ola' : 'Udostępnij'}</b>
            <small>{sharing ? 'widzą Cię na mapie' : 'lokalizację'}</small>
          </button>
          <button
            className="sos-btn"
            onPointerDown={startHold}
            onPointerUp={endHold}
            onPointerLeave={endHold}
            onContextMenu={(e) => e.preventDefault()}
          >
            SOS
            <small>przytrzymaj</small>
            {hold > 0 && (
              <svg className="hold" viewBox="0 0 96 96" width="96" height="96">
                <circle cx="48" cy="48" r="45" fill="none" stroke="#fff" strokeWidth="4" strokeDasharray={283} strokeDashoffset={283 * (1 - hold)} strokeLinecap="round" />
              </svg>
            )}
          </button>
          <button className="side-action" onClick={onExit}>
            <span className="end-ico">
              <X size={16} />
            </span>
            <b>Zakończ</b>
            <small>trasę</small>
          </button>
        </div>
        {sharing && (
          <div className="checkin">
            <Share2 size={13} /> Jeśli nie dotrzesz do {addMinutes(time.slice(0, 11) + eta, 10)}, powiadomimy Mamę i Olę
          </div>
        )}
        <div className="sim-pill">
          Symulacja:
          <button className={paused ? '' : 'on'} onClick={() => setPaused((p) => !p)}>
            {paused ? <Play size={11} /> : <Pause size={11} />}
            {paused ? 'wznów' : 'pauza'}
          </button>
          {SPEEDS.map((s) => (
            <button key={s} className={speed === s ? 'on' : ''} onClick={() => setSpeed(s)}>
              ×{s}
            </button>
          ))}
          <button onClick={() => setDist(track.total)}>meta</button>
        </div>
      </div>

      {reporting && (
        <ReportSheet
          categories={categories}
          onClose={() => setReporting(false)}
          onSubmit={(cat) => {
            onReport(pos, cat)
            setReporting(false)
          }}
        />
      )}
      {sos && <SosOverlay onClose={() => setSos(false)} nearestVenue={nearestVenue} />}
    </>
  )
}
