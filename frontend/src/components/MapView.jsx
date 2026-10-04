import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'
import {
  CircleMarker,
  MapContainer,
  Marker,
  Pane,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import { LEVEL_COLORS, scoreColor } from '../utils'

const CENTER = [50.0605, 19.932]

const pinIcon = (kind, letter) =>
  L.divIcon({
    className: '',
    html: `<div class="pin-marker ${kind}"><span>${letter}</span></div>`,
    iconSize: [30, 30],
    iconAnchor: [4, 30],
  })

const meIcon = L.divIcon({ className: '', html: '<div class="me-marker"></div>', iconSize: [22, 22], iconAnchor: [11, 11] })

function routeLabelIcon(route, selected) {
  const color = LEVEL_COLORS[route.level.id]
  return L.divIcon({
    className: '',
    html: `<div class="route-label ${selected ? 'selected' : ''}"><i style="background:${color}">${route.score}</i>${route.duration} min</div>`,
    iconSize: [0, 0],
  })
}

function HeatLayer({ network, scores }) {
  const map = useMap()
  const lines = useRef(null)

  useEffect(() => {
    if (!network) return undefined
    const renderer = L.canvas({ padding: 0.4, pane: 'heat' })
    const group = L.layerGroup()
    lines.current = network.map((g) =>
      L.polyline(g, { renderer, weight: 3, opacity: 0.85, color: '#cfc8e6', interactive: false }).addTo(group),
    )
    group.addTo(map)
    return () => {
      group.remove()
      lines.current = null
    }
  }, [network, map])

  useEffect(() => {
    if (!scores || !lines.current) return
    lines.current.forEach((l, i) => l.setStyle({ color: scoreColor(scores[i]) }))
  }, [scores, network])

  return null
}

function FitTo({ bounds, bottom, trigger }) {
  const map = useMap()
  useEffect(() => {
    if (!bounds || bounds.length < 2) return
    const h = map.getSize().y
    map.fitBounds(bounds, { paddingTopLeft: [24, 110], paddingBottomRight: [24, h * bottom + 16], maxZoom: 17, animate: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger, map])
  return null
}

function Follow({ pos, active }) {
  const map = useMap()
  const first = useRef(true)
  useEffect(() => {
    if (!active || !pos) {
      first.current = true
      return
    }
    // pozycja nieco poniżej środka - górę ekranu zajmuje karta nawigacji
    const zoom = first.current ? 17 : map.getZoom()
    const pt = map.project(pos, zoom).subtract([0, 40])
    const target = map.unproject(pt, zoom)
    if (first.current) map.setView(target, zoom, { animate: true })
    else map.panTo(target, { animate: true, duration: 0.5 })
    first.current = false
  }, [pos, active, map])
  return null
}

function ClickPicker({ onPick }) {
  useMapEvents({
    click(e) {
      if (onPick) onPick([e.latlng.lat, e.latlng.lng])
    },
  })
  return null
}

function ResizeFix() {
  const map = useMap()
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize(), 200)
    return () => clearTimeout(t)
  }, [map])
  return null
}

export default function MapView({
  night,
  origin,
  destination,
  routes,
  selectedId,
  onSelectRoute,
  detailRoute,
  navPos,
  following,
  heat,
  showIncidents,
  incidents,
  showVenues,
  onPick,
  fitKey,
  fitBottom = 0.5,
}) {
  const selected = routes?.find((r) => r.id === selectedId)

  const bounds = useMemo(() => {
    if (detailRoute) return detailRoute.coords
    if (routes?.length) return routes.flatMap((r) => r.coords)
    const pts = [origin, destination].filter(Boolean).map((p) => [p.lat, p.lon])
    return pts.length === 2 ? pts : null
  }, [routes, detailRoute, origin, destination])

  const labelPos = (r) => r.coords[Math.floor(r.coords.length * 0.55)]

  return (
    <div className={`map ${night ? 'night-tint' : ''}`}>
      <MapContainer center={CENTER} zoom={15} zoomControl={false} attributionControl style={{ width: '100%', height: '100%' }}>
        <ResizeFix />
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          maxZoom={19}
        />
        <Pane name="heat" style={{ zIndex: 350 }} />
        <Pane name="routes-under" style={{ zIndex: 410 }} />
        <Pane name="routes" style={{ zIndex: 420 }} />
        <Pane name="dots" style={{ zIndex: 430 }} />

        {heat?.network && <HeatLayer network={heat.network} scores={heat.scores} />}

        {/* alternatywne trasy */}
        {routes &&
          !detailRoute &&
          routes
            .filter((r) => r.id !== selectedId)
            .map((r) => (
              <Polyline
                key={`alt-${r.id}`}
                pane="routes-under"
                positions={r.coords}
                pathOptions={{ color: '#b9a7f5', weight: 7, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }}
                eventHandlers={{ click: () => onSelectRoute?.(r.id) }}
              />
            ))}
        {selected && !detailRoute && (
          <>
            <Polyline pane="routes" positions={selected.coords} pathOptions={{ color: '#fff', weight: 12, opacity: 1, lineCap: 'round', lineJoin: 'round' }} />
            <Polyline pane="routes" positions={selected.coords} pathOptions={{ color: '#6d28d9', weight: 7, opacity: 1, lineCap: 'round', lineJoin: 'round' }} />
          </>
        )}
        {routes &&
          !detailRoute &&
          routes.map((r) => (
            <Marker
              key={`lbl-${r.id}`}
              position={labelPos(r)}
              icon={routeLabelIcon(r, r.id === selectedId)}
              eventHandlers={{ click: () => onSelectRoute?.(r.id) }}
            />
          ))}

        {/* trasa w szczegółach / nawigacji - kolorowana odcinkami */}
        {detailRoute && (
          <>
            <Polyline pane="routes" positions={detailRoute.coords} pathOptions={{ color: '#fff', weight: 13, opacity: 1, lineCap: 'round', lineJoin: 'round' }} />
            {detailRoute.segments.map((s, i) => (
              <Polyline
                key={`seg-${i}`}
                pane="routes"
                positions={s.coords}
                pathOptions={{ color: LEVEL_COLORS[s.band], weight: 7, opacity: 1, lineCap: 'round', lineJoin: 'round' }}
              >
                <Tooltip sticky className="map-tip">
                  <b>Wskaźnik odcinka: {s.score}/100</b>
                  <small>{s.len} m</small>
                </Tooltip>
              </Polyline>
            ))}
          </>
        )}

        {showVenues &&
          detailRoute?.venues.list.map((v, i) => (
            <CircleMarker
              key={`v-${i}`}
              pane="dots"
              center={[v.lat, v.lon]}
              radius={5}
              pathOptions={{ color: '#fff', weight: 2, fillColor: '#0f9f75', fillOpacity: 1 }}
            >
              <Tooltip className="map-tip">
                <b>{v.name}</b>
                <small>
                  {v.label} · otwarte do {v.until}
                </small>
              </Tooltip>
            </CircleMarker>
          ))}

        {showIncidents &&
          (incidents ?? []).map((inc, i) => (
            <CircleMarker
              key={`i-${i}`}
              pane="dots"
              center={[inc.lat, inc.lon]}
              radius={inc.source === 'kmzb' ? 5.5 : 4.5}
              pathOptions={{
                color: '#fff',
                weight: 1.5,
                fillColor: inc.source === 'kmzb' ? '#be123c' : '#f97316',
                fillOpacity: 0.95,
              }}
            >
              <Tooltip className="map-tip">
                <b>{inc.label}</b>
                <small>
                  {inc.source === 'kmzb' ? 'KMZB (symulacja)' : 'Zgłoszenie użytkowniczki'} · {inc.date?.slice(0, 10)}, ok. {inc.hour}:00
                </small>
              </Tooltip>
            </CircleMarker>
          ))}

        {origin && <Marker position={[origin.lat, origin.lon]} icon={pinIcon('origin', 'A')} />}
        {destination && <Marker position={[destination.lat, destination.lon]} icon={pinIcon('dest', 'B')} />}
        {navPos && <Marker position={navPos} icon={meIcon} zIndexOffset={1000} />}

        <FitTo bounds={bounds} bottom={fitBottom} trigger={fitKey} />
        <Follow pos={navPos} active={following} />
        <ClickPicker onPick={onPick} />
      </MapContainer>
      {night && <div className="night-overlay" />}
    </div>
  )
}
