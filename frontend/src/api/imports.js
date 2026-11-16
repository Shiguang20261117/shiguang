import http from './http'

/** 粘贴课表纯文本并批量导入为周期日程 */
export function importTimetable(text) {
  return http.post('/api/import/timetable', { text })
}
