import http from './http'

export function listTasks() {
  return http.get('/api/tasks')
}

export function createTask(payload) {
  return http.post('/api/tasks', payload)
}

export function generateTaskSchedule(taskId) {
  return http.post(`/api/tasks/${taskId}/schedule`)
}
