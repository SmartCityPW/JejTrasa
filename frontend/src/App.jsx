import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, Info, MapPinned, SlidersHorizontal, X } from 'lucide-react'
import { api } from './api'
import MapView from './components/MapView'
import DemoPanel from './components/DemoPanel'
import InfoPanel from './components/InfoPanel'
import { StatusBar } from './components/ui'
import PlanScreen from './screens/PlanScreen'
import RoutesScreen from './screens/RoutesScreen'
import DetailScreen from './screens/DetailScreen'
import NavigateScreen from './screens/NavigateScreen'
import SurveyScreen from './screens/SurveyScreen'
import { nowRounded, withTime } from './utils'

const FIT_BOTTOM = { plan: 0.5, routes: 0.6, detail: 0.66, navigate: 0.3 }

export default function App() {
  const [meta, setMeta] = useState(null)
  const [time, setTime] = useState(nowRounded)
  const [ctx, setCtx] = useState(null)
  const [screen, setScreen] = useState('plan')
  const [origin, setOrigin] = useState(null)
  const [destination, setDestination] = useState(null)
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [fitKey, setFitKey] = useState(0)
  const [layers, setLayers] = useState({ heat: false, incidents: false })
  const [heat, setHeat] = useState({ network: null, scores: null })
  const [allIncidents, setAllIncidents] = useState([])
  const [myReports, setMyReports] = useState([])
  const [navPos, setNavPos] = useState(null)
  const [following, setFollowing] = useState(true)
  const [surveyOpen, setSurveyOpen] = useState(false)
  const [pickTarget, setPickTarget] = useState(null)
  const [boost, setBoost] = useState(false)
  const [toast, setToast] = useState(null)
  const [activeScenario, setActiveScenario] = useState(null)
  const [demoOpen, setDemoOpen] = useState(false)
  const lastPlanned = useRef(null)
  const planSeq = useRef(0)

  const refreshMeta = useCallback(() => api.meta().then(setMeta).catch(() => {}), [])

  useEffect(() => {
    api
      .meta()
      .then((m) => {
        setMeta(m)
        const here = m.places.find((p) => p.id === 'rynek')
        setOrigin((o) => o ?? { ...here, name: 'Moja lokalizacja' })
      })
      .catch(() => setError('Brak połączenia z serwerem API (uruchom backend na porcie 8000).'))
  }, [])

  useEffect(() => {
    const t = setTimeout(() => api.context(time).then(setCtx).catch(() => {}), 120)
    return () => clearTimeout(t)
  }, [time])

  const showToast = (text) => {
    setToast(text)
    setTimeout(() => setToast(null), 3200)
  }

  const runPlan = useCallback(async (o, d, t, keepId = null) => {
    if (!o || !d) return
    const seq = ++planSeq.current
    lastPlanned.current = t
    setLoading(true)
    setError(null)
    try {
      const res = await api.routes({ lat: o.lat, lon: o.lon }, { lat: d.lat, lon: d.lon }, t)
      if (seq !== planSeq.current) return
      setPlan(res)
      const keep = keepId && res.routes.find((r) => r.id === keepId)
      setSelectedId(keep ? keepId : (res.routes.find((r) => r.recommended) ?? res.routes[0]).id)
      if (!keepId) setFitKey((k) => k + 1)
    } catch (e) {
      if (seq === planSeq.current) setError(e.message)
    } finally {
      if (seq === planSeq.current) setLoading(false)
    }
  }, [])

  // zmiana godziny w "wehikule czasu" przelicza trasy na żywo
  useEffect(() => {
    if (!['routes', 'detail'].includes(screen) || lastPlanned.current === time) return undefined
    const t = setTimeout(() => runPlan(origin, destination, time, selectedId), 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [time, screen])

  // warstwa "mapa bezpieczeństwa"
  useEffect(() => {
    if (!layers.heat) return undefined
    if (!heat.network) api.network().then((n) => setHeat((h) => ({ ...h, network: n.edges })))
    const t = setTimeout(() => api.scores(time).then((s) => setHeat((h) => ({ ...h, scores: s.scores }))), 200)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layers.heat, time, meta?.dataset?.ratings, meta?.dataset?.reports])

  useEffect(() => {
    if (layers.incidents) api.incidents().then(setAllIncidents)
  }, [layers.incidents, myReports.length])

  const selectedRoute = plan?.routes.find((r) => r.id === selectedId)

  const goPlan = () => {
    setScreen('plan')
    setPlan(null)
    setNavPos(null)
    setSurveyOpen(false)
    lastPlanned.current = null
    setFitKey((k) => k + 1)
  }

  const search = () => {
    setActiveScenario(null)
    setScreen('routes')
    setPlan(null)
    runPlan(origin, destination, time)
  }

  const onScenario = (sc, hhmm) => {
    const places = Object.fromEntries(meta.places.map((p) => [p.id, p]))
    const t = withTime(time, hhmm)
    const o = places[sc.from]
    const d = places[sc.to]
    setActiveScenario(sc)
    setOrigin(o)
    setDestination(d)
    setTime(t)
    setNavPos(null)
    setSurveyOpen(false)
    setScreen('routes')
    if (!(origin?.id === o.id && destination?.id === d.id)) setPlan(null)
    runPlan(o, d, t)
    setDemoOpen(false)
  }

  const startNav = (id) => {
    setSelectedId(id)
    setFollowing(true)
    setScreen('navigate')
  }

  const submitSurvey = async (answers) => {
    const res = await api.survey({
      edges: selectedRoute.edges,
      time,
      overall: answers.overall,
      feltSafe: answers.feltSafe,
      lighting: answers.lighting,
      venues: answers.venues,
      comment: answers.comment,
      weight: boost ? 20 : 1,
    })
    refreshMeta()
    return res
  }

  const report = async (pos, category) => {
    try {
      const inc = await api.report({ lat: pos[0], lon: pos[1], category, time })
      setMyReports((r) => [...r, inc])
      refreshMeta()
      showToast('Dziękujemy! Zgłoszenie ostrzeże inne kobiety.')
    } catch (e) {
      showToast(e.message)
    }
  }

  const onPick = (latlng) => {
    if (!pickTarget) return
    const place = {
      id: `pt-${latlng[0].toFixed(5)}-${latlng[1].toFixed(5)}`,
      name: 'Punkt na mapie',
      address: `${latlng[0].toFixed(4)}, ${latlng[1].toFixed(4)}`,
      lat: latlng[0],
      lon: latlng[1],
      icon: 'map',
    }
    if (pickTarget === 'origin') setOrigin(place)
    else setDestination(place)
    setPickTarget(null)
  }

  const mapIncidents = useMemo(() => {
    if (layers.incidents) return allIncidents
    if (screen === 'detail' && selectedRoute) return selectedRoute.incidents.list
    if (screen === 'navigate') return myReports
    return []
  }, [layers.incidents, allIncidents, screen, selectedRoute, myReports])

  const night = ctx ? ctx.phase !== 'day' : false
  const detailRoute = ['detail', 'navigate'].includes(screen) ? selectedRoute : null

  useEffect(() => {
    if (screen === 'plan' && origin && destination) setFitKey((k) => k + 1)
  }, [origin, destination, screen])

  useEffect(() => {
    if (['detail'].includes(screen)) setFitKey((k) => k + 1)
  }, [screen])

  return (
    <div className={`page ${demoOpen ? 'demo-open' : ''}`}>
      <aside className="side side-left">
        <DemoPanel
          meta={meta}
          time={time}
          setTime={setTime}
          ctx={ctx}
          activeScenario={activeScenario}
          onScenario={onScenario}
          layers={layers}
          setLayers={setLayers}
          boost={boost}
          setBoost={setBoost}
        />
      </aside>

      <main className="phone-wrap">
        <div className="phone">
          <div className="phone-screen">
            <StatusBar time={time} />
            <MapView
              night={night}
              origin={origin}
              destination={destination}
              routes={screen === 'routes' ? plan?.routes : null}
              selectedId={selectedId}
              onSelectRoute={setSelectedId}
              detailRoute={detailRoute}
              navPos={screen === 'navigate' ? navPos : null}
              following={screen === 'navigate' && following}
              heat={layers.heat ? heat : null}
              showIncidents={mapIncidents.length > 0}
              incidents={mapIncidents}
              showVenues={screen === 'detail'}
              onPick={pickTarget ? onPick : null}
              fitKey={`${screen}-${fitKey}`}
              fitBottom={FIT_BOTTOM[screen]}
            />

            {pickTarget && (
              <div className="glass pick-banner">
                <MapPinned size={18} color="#7c3aed" />
                Dotknij mapy, aby wybrać {pickTarget === 'origin' ? 'start' : 'cel'}
                <button className="icon-btn" style={{ width: 32, height: 32 }} onClick={() => setPickTarget(null)}>
                  <X size={16} />
                </button>
              </div>
            )}

            {screen === 'plan' && !pickTarget && meta && (
              <PlanScreen
                places={meta.places}
                origin={origin}
                destination={destination}
                setOrigin={setOrigin}
                setDestination={setDestination}
                time={time}
                ctx={ctx}
                onSearch={search}
                onPickOnMap={setPickTarget}
              />
            )}
            {screen === 'plan' && !meta && error && (
              <div className="sheet">
                <div className="error-box">{error}</div>
              </div>
            )}
            {screen === 'routes' && (
              <RoutesScreen
                origin={origin}
                destination={destination}
                time={time}
                ctx={plan?.context ?? ctx}
                plan={plan}
                loading={loading}
                error={error}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onBack={goPlan}
                onDetails={(id) => {
                  setSelectedId(id)
                  setScreen('detail')
                }}
                onStart={startNav}
              />
            )}
            {screen === 'detail' && selectedRoute && (
              <DetailScreen route={selectedRoute} ctx={plan?.context ?? ctx} onBack={() => setScreen('routes')} onStart={() => startNav(selectedRoute.id)} />
            )}
            {screen === 'navigate' && selectedRoute && (
              <NavigateScreen
                key={`${selectedRoute.id}-${fitKey}`}
                route={selectedRoute}
                time={time}
                ctx={plan?.context ?? ctx}
                categories={meta?.reportCategories ?? []}
                onPosition={setNavPos}
                onArrive={() => setSurveyOpen(true)}
                onExit={() => setSurveyOpen(true)}
                onReport={report}
                following={following}
                setFollowing={setFollowing}
              />
            )}
            {surveyOpen && selectedRoute && (
              <SurveyScreen
                route={selectedRoute}
                ctx={plan?.context ?? ctx}
                onSubmit={submitSurvey}
                onDone={goPlan}
                onReplan={() => {
                  setSurveyOpen(false)
                  setNavPos(null)
                  setScreen('routes')
                  runPlan(origin, destination, time)
                }}
              />
            )}
            {toast && (
              <div className="toast">
                <CheckCircle2 size={16} /> {toast}
              </div>
            )}
          </div>
        </div>
        <div className="phone-caption">
          <Info size={14} /> Prototyp · Kraków · ulice z OpenStreetMap, zgłoszenia symulowane
        </div>
      </main>

      <aside className="side side-right">
        <InfoPanel meta={meta} />
      </aside>

      <button className="mobile-demo-btn" onClick={() => setDemoOpen((o) => !o)}>
        {demoOpen ? <X size={15} /> : <SlidersHorizontal size={15} />}
        {demoOpen ? 'Wróć do aplikacji' : 'Demo'}
      </button>
    </div>
  )
}
