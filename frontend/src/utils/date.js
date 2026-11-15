export const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

export function pad2(value) {
  return String(value).padStart(2, '0')
}

export function toDateStr(date) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

export function parseDateStr(value) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

/** 以周一为一周起点 */
export function startOfWeek(date = new Date()) {
  const result = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const offset = (result.getDay() + 6) % 7
  result.setDate(result.getDate() - offset)
  return result
}

export function addDays(date, days) {
  const result = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  result.setDate(result.getDate() + days)
  return result
}

export function isSameDay(a, b) {
  return toDateStr(a) === toDateStr(b)
}

export function formatMonthDay(date) {
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function formatWeekRange(start) {
  const end = addDays(start, 6)
  return `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日 - ${end.getMonth() + 1}月${end.getDate()}日`
}

/**
 * 后端 weekday 约定：0=周一 ... 6=周日；
 * JavaScript getDay()：0=周日 ... 6=周六，因此需要转换。
 */
export function toBackendWeekday(date) {
  return (date.getDay() + 6) % 7
}

export function timeToMinutes(time) {
  if (!time) return 0
  const [hour, minute] = time.split(':').map(Number)
  return hour * 60 + minute
}

/** "08:00:00" -> "08:00" */
export function formatTime(time) {
  return time ? time.slice(0, 5) : ''
}

/** "2026-11-15T10:20:30" -> "2026-11-15 10:20" */
export function formatDateTime(value) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 16)
}
