import http from './http'

export function createCheckin(payload) {
  return http.post('/api/checkins', payload)
}

export function listCheckins(params = {}) {
  return http.get('/api/checkins', { params })
}

export function getCheckinStats(days = 7) {
  return http.get('/api/checkins/stats', { params: { days } })
}
