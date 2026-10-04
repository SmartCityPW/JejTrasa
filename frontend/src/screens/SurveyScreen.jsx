import { useState } from 'react'
import { ArrowRight, Check, Heart, Lightbulb, LightbulbOff, RotateCcw, Store, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import { plural } from '../utils'

const SAFE_LABELS = ['Bardzo źle', 'Niepewnie', 'Tak sobie', 'Dobrze', 'Super']

export default function SurveyScreen({ route, ctx, onSubmit, onDone, onReplan }) {
  const [overall, setOverall] = useState(null)
  const [feltSafe, setFeltSafe] = useState(null)
  const [lighting, setLighting] = useState(null)
  const [venues, setVenues] = useState(null)
  const [comment, setComment] = useState('')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const night = ctx?.phase !== 'day'

  const submit = async () => {
    setSending(true)
    setError(null)
    try {
      setResult(await onSubmit({ overall, feltSafe, lighting, venues, comment }))
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="overlay" style={{ background: 'rgba(30, 11, 69, 0.35)' }}>
      <div className="modal-sheet" style={{ maxHeight: '92%' }}>
        <div className="grip" style={{ width: 40, height: 5, borderRadius: 3, background: 'var(--v-200)', margin: '0 auto 12px' }} />
        {!result ? (
          <>
            <div className="survey-hero">
              <div className="ok">
                <Check size={32} strokeWidth={3} />
              </div>
              <h3>Jesteś na miejscu!</h3>
              <p className="lead">Twoja opinia pomoże innym kobietom wybrać bezpieczniejszą drogę. To zajmie 15 sekund.</p>
            </div>

            <div className="q">
              <b>Jak oceniasz tę trasę?</b>
              <div className="thumbs">
                <button className={`thumb up ${overall === 1 ? 'selected' : ''}`} onClick={() => setOverall(1)}>
                  <ThumbsUp size={26} /> Dobra trasa
                </button>
                <button className={`thumb down ${overall === 0 ? 'selected' : ''}`} onClick={() => setOverall(0)}>
                  <ThumbsDown size={26} /> Zła trasa
                </button>
              </div>
            </div>

            <div className="q">
              <b>Jak bezpiecznie się czułaś?</b>
              <div className="scale">
                {SAFE_LABELS.map((l, i) => (
                  <button key={l} className={feltSafe === i + 1 ? 'selected' : ''} onClick={() => setFeltSafe(i + 1)}>
                    {i + 1}
                    <small>{l}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="q">
              <b>Oświetlenie na trasie było…</b>
              <div className="seg">
                <button className={lighting === 1 ? 'selected' : ''} onClick={() => setLighting(1)}>
                  <Lightbulb size={16} /> Dobre
                </button>
                <button className={lighting === 0 ? 'selected' : ''} onClick={() => setLighting(0)}>
                  <LightbulbOff size={16} /> Słabe
                </button>
              </div>
            </div>

            <div className="q">
              <b>Lokale wokół były…</b>
              <div className="seg">
                <button className={venues === 1 ? 'selected' : ''} onClick={() => setVenues(1)}>
                  <Store size={16} /> Otwarte
                </button>
                <button className={venues === 0 ? 'selected' : ''} onClick={() => setVenues(0)}>
                  <X size={16} /> Zamknięte
                </button>
              </div>
            </div>

            <div className="q">
              <b>
                Komentarz <span style={{ color: 'var(--faint)', fontWeight: 600 }}>(opcjonalnie)</span>
              </b>
              <textarea
                className="comment"
                placeholder="Np. przy kładce zepsuta latarnia, grupa osób pod mostem…"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={1000}
              />
            </div>

            {error && <div className="error-box">{error}</div>}
            <button className="cta" disabled={sending || (overall === null && feltSafe === null)} onClick={submit}>
              <Heart size={18} /> {sending ? 'Wysyłanie…' : 'Wyślij opinię'}
            </button>
            <button className="cta secondary" style={{ marginTop: 8 }} onClick={onDone}>
              Pomiń
            </button>
          </>
        ) : (
          <>
            <div className="survey-hero">
              <div className="ok">
                <Heart size={30} />
              </div>
              <h3>Dziękujemy!</h3>
              <p className="lead">Twoja opinia już działa – kolejne trasy w tej okolicy uwzględnią Twoje doświadczenie.</p>
            </div>
            <div className="result-card">
              <span className="eyebrow">Średni wskaźnik ocenionych odcinków {night ? 'nocą' : 'w dzień'}</span>
              <div className="delta">
                {Math.round(result.scoreBefore)} <span>→</span> {Math.round(result.scoreAfter)}
              </div>
              <p style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', lineHeight: 1.5 }}>
                Zaktualizowano {result.segmentsUpdated} {plural(result.segmentsUpdated, 'odcinek', 'odcinki', 'odcinków')} ulic na trasie „{route.label}”.
                {Math.abs(result.scoreAfter - result.scoreBefore) < 0.5 &&
                  ' Pojedyncza opinia zmienia wskaźnik delikatnie – wiele podobnych opinii przesuwa go wyraźnie.'}
              </p>
            </div>
            <button className="cta" onClick={onReplan}>
              <RotateCcw size={17} /> Wyznacz tę trasę ponownie
            </button>
            <button className="cta secondary" style={{ marginTop: 8 }} onClick={onDone}>
              Zaplanuj nową trasę <ArrowRight size={16} />
            </button>
          </>
        )}
      </div>
    </div>
  )
}
