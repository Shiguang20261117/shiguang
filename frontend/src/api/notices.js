import http from './http'

/** 解析调课通知文本（只返回解析结果，不修改日程） */
export function parseNotice(text) {
  return http.post('/api/notices/parse', { text })
}

/** 确认执行解析结果：取消课程或调整时间 */
export function confirmNotice(id) {
  return http.post(`/api/notices/${id}/confirm`)
}

/** 丢弃解析结果 */
export function discardNotice(id) {
  return http.post(`/api/notices/${id}/discard`)
}
