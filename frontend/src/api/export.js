import http from './http'

/** 导出指定周（周一日期）的周计划 PNG 图片 */
export function exportWeekPng(startDate) {
  return http.get('/api/export/week.png', {
    params: { start_date: startDate },
    responseType: 'blob',
  })
}
