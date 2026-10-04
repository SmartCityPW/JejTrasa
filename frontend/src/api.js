async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* brak treści */
    }
    throw new Error(typeof detail === 'string' ? detail : 'Błąd serwera')
  }
  return res.json()
}

export const api = {
  meta: () => request('/meta'),
  context: (time) => request(`/context?time=${encodeURIComponent(time)}`),
  routes: (origin, destination, time) =>
    request('/routes', { method: 'POST', body: { origin, destination, time } }),
  network: () => request('/network'),
  scores: (time) => request(`/scores?time=${encodeURIComponent(time)}`),
  incidents: () => request('/incidents'),
  survey: (payload) => request('/survey', { method: 'POST', body: payload }),
  report: (payload) => request('/reports', { method: 'POST', body: payload }),
}
