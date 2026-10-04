import { useState } from 'react'
import { ArrowDownUp, ArrowLeft, Crosshair, MapPinned, Moon, Search, ShieldCheck, Sparkles, Sun, Sunset, Users } from 'lucide-react'
import { PlaceIcon } from '../components/ui'
import pinLogo from '../assets/pin-logo.png'
import { fmtDateLong, timeOf, toLocalIso } from '../utils'

const PHASE_ICON = { day: Sun, twilight: Sunset, night: Moon }

export function TimeChip({ time, ctx }) {
  if (!ctx) return null
  const Icon = PHASE_ICON[ctx.phase] ?? Sun
  const isToday = time.slice(0, 10) === toLocalIso(new Date()).slice(0, 10)
  return (
    <div className="time-chip">
      <div className={`ico ${ctx.phase}`}>
        <Icon size={18} />
      </div>
      <div style={{ flex: 1 }}>
        <b>
          Wyjście {isToday ? 'dziś' : fmtDateLong(time)} o {timeOf(time)} · {ctx.phaseLabel}
        </b>
        <small>
          Zachód słońca {ctx.sunset} · zmrok {ctx.dusk} · wschód {ctx.sunrise}
        </small>
      </div>
    </div>
  )
}

export default function PlanScreen({ places, origin, destination, setOrigin, setDestination, time, ctx, onSearch, onPickOnMap }) {
  const [picking, setPicking] = useState(null) // 'origin' | 'destination'
  const [query, setQuery] = useState('')

  const choose = (place) => {
    if (picking === 'origin') setOrigin(place)
    else setDestination(place)
    setPicking(null)
    setQuery('')
  }

  const filtered = places.filter((p) => `${p.name} ${p.address}`.toLowerCase().includes(query.toLowerCase()))
  const favourites = places.filter((p) => ['zaczek', 'agh', 'kawiory'].includes(p.id))

  return (
    <>
      <div className="screen-top">
        <div className="glass brand-bar">
          <img src={pinLogo} alt="" />
          <div className="wordmark">
            Jej Trasa
            <small>Wracaj bezpiecznie. Zawsze.</small>
          </div>
        </div>
        <button className="glass icon-btn" title="Zaufane kontakty">
          <Users size={20} />
          <span className="badge">2</span>
        </button>
      </div>

      <div className="sheet">
        <div className="grip" />
        <div className="sheet-scroll">
          <h2>Dokąd idziesz?</h2>
          <p className="lead">Wyznaczymy trasę, która jest bezpieczna o tej porze.</p>

          <div className="trip-inputs">
            <button className="trip-input" onClick={() => setPicking('origin')}>
              <span className="dot origin" />
              <div className="t">
                <small>Skąd</small>
                <span className={origin ? '' : 'placeholder'}>{origin?.name ?? 'Wybierz punkt startowy'}</span>
              </div>
            </button>
            <button className="trip-input" onClick={() => setPicking('destination')}>
              <span className="dot dest" />
              <div className="t">
                <small>Dokąd</small>
                <span className={destination ? '' : 'placeholder'}>{destination?.name ?? 'Wybierz cel'}</span>
              </div>
            </button>
            <button
              className="swap-btn"
              title="Zamień"
              onClick={() => {
                setOrigin(destination)
                setDestination(origin)
              }}
            >
              <ArrowDownUp size={16} />
            </button>
          </div>

          <TimeChip time={time} ctx={ctx} />

          <div className="chips-row">
            {favourites.map((p) => (
              <button key={p.id} className="chip" onClick={() => (origin ? setDestination(p) : setOrigin(p))}>
                <PlaceIcon icon={p.icon} size={14} /> {p.name}
              </button>
            ))}
          </div>

          <button className="cta" disabled={!origin || !destination} onClick={onSearch}>
            <ShieldCheck size={19} /> Pokaż bezpieczne trasy
          </button>
        </div>
      </div>

      {picking && (
        <div className="picker">
          <div className="picker-head">
            <button className="icon-btn" onClick={() => setPicking(null)}>
              <ArrowLeft size={20} />
            </button>
            <label className="search">
              <Search size={18} color="#8b5cf6" />
              <input
                autoFocus
                placeholder={picking === 'origin' ? 'Skąd wyruszasz?' : 'Dokąd idziesz?'}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          </div>
          <div className="picker-list">
            {picking === 'origin' && !query && (
              <button className="picker-item" onClick={() => choose({ ...places.find((p) => p.id === 'rynek'), name: 'Moja lokalizacja' })}>
                <span className="pi-ico accent">
                  <Crosshair size={19} />
                </span>
                <div>
                  <b>Moja lokalizacja</b>
                  <small>GPS (symulowany) – okolice Rynku</small>
                </div>
              </button>
            )}
            {!query && (
              <button
                className="picker-item"
                onClick={() => {
                  onPickOnMap(picking)
                  setPicking(null)
                }}
              >
                <span className="pi-ico">
                  <MapPinned size={19} />
                </span>
                <div>
                  <b>Wskaż na mapie</b>
                  <small>Dotknij dowolnego miejsca w centrum Krakowa</small>
                </div>
              </button>
            )}
            <div className="picker-section">
              <Sparkles size={11} style={{ verticalAlign: -1 }} /> Miejsca w Krakowie
            </div>
            {filtered.map((p) => (
              <button key={p.id} className="picker-item" onClick={() => choose(p)}>
                <span className="pi-ico">
                  <PlaceIcon icon={p.icon} />
                </span>
                <div>
                  <b>{p.name}</b>
                  <small>{p.address}</small>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
