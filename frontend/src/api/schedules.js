import http from './http'

export function listSchedules(startDate, endDate) {
  return http.get('/api/schedules', {
    params: { start_date: startDate, end_date: endDate },
  })
}

export function createSchedule(payload) {
  return http.post('/api/schedules', payload)
}

export function updateSchedule(scheduleId, payload) {
  return http.patch(`/api/schedules/${scheduleId}`, payload)
}

export function deleteSchedule(scheduleId) {
  return http.delete(`/api/schedules/${scheduleId}`)
}
