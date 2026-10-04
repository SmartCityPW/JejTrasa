import {
  BatteryFull,
  Castle,
  GraduationCap,
  Home,
  Landmark,
  MapPin,
  Music,
  Signal,
  Theater,
  TrainFront,
  TramFront,
  TreePine,
  Wifi,
} from 'lucide-react'
import { LEVEL_COLORS, levelOf, timeOf } from '../utils'

export function ScoreRing({ score, size = 64, stroke = 7, label = true }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const color = LEVEL_COLORS[levelOf(score).id]
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#ede9fe" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - score / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="val">
        <div>
          <strong style={{ fontSize: size * 0.34 }}>{score}</strong>
          {label && <small>/100</small>}
        </div>
      </div>
    </div>
  )
}

export function StatusBar({ time, dark }) {
  return (
    <div className={`statusbar ${dark ? 'dark' : ''}`}>
      <span>{timeOf(time)}</span>
      <div className="island" />
      <div className="icons">
        <Signal size={15} strokeWidth={2.6} />
        <Wifi size={15} strokeWidth={2.6} />
        <BatteryFull size={20} strokeWidth={2.2} />
      </div>
    </div>
  )
}

const PLACE_ICONS = {
  home: Home,
  school: GraduationCap,
  landmark: Landmark,
  train: TrainFront,
  music: Music,
  castle: Castle,
  tram: TramFront,
  museum: Landmark,
  theater: Theater,
  map: MapPin,
  tree: TreePine,
}

export function PlaceIcon({ icon, size = 18 }) {
  const Icon = PLACE_ICONS[icon] ?? MapPin
  return <Icon size={size} />
}

export function Switch({ on }) {
  return <span className={`switch ${on ? 'on' : ''}`} />
}

export function Spinner({ children }) {
  return (
    <div className="loading">
      <div className="spinner" />
      {children}
    </div>
  )
}
