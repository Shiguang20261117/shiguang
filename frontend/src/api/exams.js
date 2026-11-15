import http from './http'

export function listExams() {
  return http.get('/api/exams')
}

export function createExam(payload) {
  return http.post('/api/exams', payload)
}

export function generateStudyPlan(examId) {
  return http.post(`/api/exams/${examId}/plan`)
}
