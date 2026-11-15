import http from './http'

export function createSeries(payload) {
  return http.post('/api/series', payload)
}

export function updateSeries(seriesId, payload) {
  return http.patch(`/api/series/${seriesId}`, payload)
}

export function deleteSeries(seriesId) {
  return http.delete(`/api/series/${seriesId}`)
}
