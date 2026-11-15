import http from './http'

export function listRoutines(params) {
  return http.get('/api/routines', { params })
}

export function createRoutine(payload) {
  return http.post('/api/routines', payload)
}

export function deleteRoutine(routineId) {
  return http.delete(`/api/routines/${routineId}`)
}
