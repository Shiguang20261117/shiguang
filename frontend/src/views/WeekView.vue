<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import AddScheduleDialog from '@/components/AddScheduleDialog.vue'
import EditScheduleDialog from '@/components/EditScheduleDialog.vue'
import ScheduleDetailDialog from '@/components/ScheduleDetailDialog.vue'
import { createCheckin, listCheckins } from '@/api/checkins'
import { exportWeekPng } from '@/api/export'
import { importTimetable } from '@/api/imports'
import { confirmNotice, discardNotice, parseNotice } from '@/api/notices'
import { listRoutines } from '@/api/routines'
import { deleteSchedule, listSchedules } from '@/api/schedules'
import { deleteSeries } from '@/api/series'
import { useCheckinStore } from '@/stores/checkins'
import { getErrorMessage } from '@/utils/error'
import {
  WEEKDAY_LABELS,
  addDays,
  formatMonthDay,
  formatTime,
  formatWeekRange,
  isSameDay,
  pad2,
  parseDateStr,
  startOfWeek,
  timeToMinutes,
  toDateStr,
} from '@/utils/date'

// 时间轴范围：06:00 - 24:00，每小时一行
const START_HOUR = 6
const END_HOUR = 24
const HOUR_HEIGHT = 56
const SNAP_MINUTES = 30

const weekStart = ref(startOfWeek(new Date()))
const schedules = ref([])
const routines = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogInitial = ref({})

const checkinStore = useCheckinStore()
// 已打卡目标集合，key 形如 schedule:12
const checkedKeys = ref(new Set())
const checkingIds = ref(new Set())

const detailVisible = ref(false)
const activeSchedule = ref(null)
const editVisible = ref(false)
const editTarget = ref(null)
const deleteScopeVisible = ref(false)
const exporting = ref(false)

const importVisible = ref(false)
const importText = ref('')
const importing = ref(false)
const importCreated = ref(null)
const importErrors = ref([])

const noticeVisible = ref(false)
const noticeText = ref('')
const noticeParsing = ref(false)
const noticeActing = ref(false)
const noticeResult = ref(null)

const NOTICE_EXAMPLE = '因老师出差，周三08:00的高等数学改到周五14:00-15:40'

const IMPORT_EXAMPLE = [
  '周一 08:00-09:40 高等数学 [教一楼 301]',
  '周三 10:00-11:40 大学英语 [文科楼 205]',
  '周五 14:00-15:40 数据结构 【计算机楼 402】',
  '周五 25:00-26:00 格式错误的课程',
].join('\n')

const hourLabels = Array.from({ length: END_HOUR - START_HOUR }, (_, index) => {
  const hour = START_HOUR + index
  return `${pad2(hour)}:00`
})
const gridHeight = (END_HOUR - START_HOUR) * HOUR_HEIGHT

const days = computed(() =>
  Array.from({ length: 7 }, (_, index) => {
    const date = addDays(weekStart.value, index)
    return {
      date,
      dateStr: toDateStr(date),
      weekdayLabel: WEEKDAY_LABELS[index],
      weekday: index, // 周一 = 0，与后端一致
      monthDay: formatMonthDay(date),
      isToday: isSameDay(date, new Date()),
    }
  }),
)

const weekRangeLabel = computed(() => formatWeekRange(weekStart.value))

const eventsByDay = computed(() => {
  const buckets = {}
  for (const day of days.value) buckets[day.dateStr] = []

  for (const schedule of schedules.value) {
    if (buckets[schedule.date]) buckets[schedule.date].push(schedule)
  }

  const result = {}
  for (const dateStr of Object.keys(buckets)) {
    result[dateStr] = layoutDayEvents(buckets[dateStr])
  }
  return result
})

/**
 * 固定日常按星期展开到本周日期。
 * 后端 Routine 目前返回 weekday（0=周一 ... 6=周日），并非 days_of_week 位掩码；
 * 这里同时兼容两种形态：优先 days_of_week（bit0=周一 ... bit6=周日），否则用 weekday。
 */
function routineWeekdays(routine) {
  const daysOfWeek = routine.days_of_week
  if (Array.isArray(daysOfWeek)) return daysOfWeek
  if (typeof daysOfWeek === 'number') {
    return [0, 1, 2, 3, 4, 5, 6].filter((day) => daysOfWeek & (1 << day))
  }
  return Number.isInteger(routine.weekday) ? [routine.weekday] : []
}

// 只展示启用的固定日常，作为周视图背景块
const routinesByDay = computed(() => {
  const result = {}
  for (const day of days.value) {
    result[day.dateStr] = routines.value.filter(
      (routine) =>
        routine.is_active !== false && routineWeekdays(routine).includes(day.weekday),
    )
  }
  return result
})

/** 同一天内相互重叠的日程分列展示，避免互相遮挡 */
function layoutDayEvents(list) {
  const sorted = [...list].sort(
    (a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time),
  )

  const clusters = []
  for (const schedule of sorted) {
    const start = timeToMinutes(schedule.start_time)
    const end = timeToMinutes(schedule.end_time)
    const cluster = clusters.find((item) => start < item.end)

    if (cluster) {
      cluster.items.push(schedule)
      cluster.end = Math.max(cluster.end, end)
    } else {
      clusters.push({ end, items: [schedule] })
    }
  }

  const laidOut = []
  for (const cluster of clusters) {
    const columns = []
    for (const schedule of cluster.items) {
      let columnIndex = columns.findIndex((column) => {
        const last = column[column.length - 1]
        return timeToMinutes(last.end_time) <= timeToMinutes(schedule.start_time)
      })
      if (columnIndex === -1) {
        columnIndex = columns.length
        columns.push([])
      }
      columns[columnIndex].push(schedule)
    }

    columns.forEach((column, columnIndex) => {
      for (const schedule of column) {
        laidOut.push({ ...schedule, columnIndex, columnCount: columns.length })
      }
    })
  }
  return laidOut
}

const PALETTE = [
  { background: '#fff0e2', border: '#f0b183', color: '#8a4a20' },
  { background: '#e8f3ec', border: '#9ec9ae', color: '#2f6446' },
  { background: '#e9eefb', border: '#a8b8e8', color: '#34497f' },
  { background: '#fdeef1', border: '#eeb3c0', color: '#8d3b4f' },
  { background: '#f3edfb', border: '#c1ade4', color: '#553f80' },
  { background: '#fdf6dc', border: '#e0c878', color: '#7a6220' },
]

// 分类配色：复习=绿色系，运动=蓝色系，其余按标题散列到暖色系
const CATEGORY_PALETTE = {
  study: { background: '#e8f3ec', border: '#9ec9ae', color: '#2f6446' },
  sport: { background: '#e6effb', border: '#9dbce8', color: '#2f4d7f' },
}

function colorOf(schedule) {
  const categoryPalette = CATEGORY_PALETTE[schedule.category]
  if (categoryPalette) return categoryPalette

  let hash = 0
  for (const char of schedule.title || '') {
    hash = (hash * 31 + char.charCodeAt(0)) % 9973
  }
  return PALETTE[hash % PALETTE.length]
}

function eventStyle(schedule) {
  const start = timeToMinutes(schedule.start_time)
  const end = timeToMinutes(schedule.end_time)
  const visibleStart = Math.max(start, START_HOUR * 60)
  const visibleEnd = Math.min(end, END_HOUR * 60)

  const top = ((visibleStart - START_HOUR * 60) / 60) * HOUR_HEIGHT
  const height = Math.max(((visibleEnd - visibleStart) / 60) * HOUR_HEIGHT - 4, 26)
  const palette = colorOf(schedule)
  const columnWidth = 100 / schedule.columnCount

  return {
    top: `${top}px`,
    height: `${height}px`,
    left: `calc(${schedule.columnIndex * columnWidth}% + 1px)`,
    width: `calc(${columnWidth}% - 2px)`,
    background: palette.background,
    borderColor: palette.border,
    color: palette.color,
  }
}

/** 固定日常背景块：铺满当天列宽，仅按时间定位 */
function routineStyle(routine) {
  const start = Math.max(timeToMinutes(routine.start_time), START_HOUR * 60)
  const end = Math.min(timeToMinutes(routine.end_time), END_HOUR * 60)
  const top = ((start - START_HOUR * 60) / 60) * HOUR_HEIGHT
  const height = Math.max(((end - start) / 60) * HOUR_HEIGHT - 4, 22)

  return { top: `${top}px`, height: `${height}px` }
}

function routineTooltip(routine) {
  const parts = [
    `固定日常：${formatTime(routine.start_time)} - ${formatTime(routine.end_time)}  ${routine.title}`,
  ]
  if (routine.description) parts.push(routine.description)
  return parts.join('\n')
}

function notifyRoutine() {
  ElMessage.info('这是固定日常，请到「固定日常」页修改')
}

async function loadWeekData() {
  loading.value = true
  try {
    const start = days.value[0].dateStr
    const end = days.value[6].dateStr
    // 同时拉取本周日程、启用的固定日常与已打卡记录；任一失败不影响另一部分展示
    const [schedulesResult, routinesResult, checkinsResult] = await Promise.allSettled([
      listSchedules(start, end),
      listRoutines({ is_active: true }),
      listCheckins(),
    ])

    if (schedulesResult.status === 'fulfilled') {
      const data = schedulesResult.value.data
      schedules.value = Array.isArray(data) ? data : []
    } else {
      schedules.value = []
      ElMessage.error(getErrorMessage(schedulesResult.reason, '加载日程失败'))
    }

    if (routinesResult.status === 'fulfilled') {
      const data = routinesResult.value.data
      routines.value = Array.isArray(data) ? data : []
    } else {
      routines.value = []
      ElMessage.warning('固定日常加载失败，本周暂不显示')
    }

    if (checkinsResult.status === 'fulfilled') {
      const data = checkinsResult.value.data
      checkedKeys.value = new Set(
        (Array.isArray(data) ? data : [])
          .filter((item) => item.target_type === 'schedule')
          .map((item) => scheduleKey(item.target_id)),
      )
    }
  } finally {
    loading.value = false
  }
}

function scheduleKey(scheduleId) {
  return `schedule:${scheduleId}`
}

function isChecked(schedule) {
  return checkedKeys.value.has(scheduleKey(schedule.id))
}

function isCheckingIn(schedule) {
  return checkingIds.value.has(schedule.id)
}

function markChecked(scheduleId) {
  const next = new Set(checkedKeys.value)
  next.add(scheduleKey(scheduleId))
  checkedKeys.value = next
}

async function doCheckin(schedule) {
  if (isChecked(schedule) || isCheckingIn(schedule)) return

  const pending = new Set(checkingIds.value)
  pending.add(schedule.id)
  checkingIds.value = pending

  try {
    await createCheckin({ target_type: 'schedule', target_id: schedule.id })
    markChecked(schedule.id)
    ElMessage.success(`已打卡：${schedule.title}`)
    // 打卡后立即刷新统计，个人中心无需刷新即可看到最新数据
    checkinStore.markChecked()
  } catch (error) {
    if (error.response?.status === 409) {
      markChecked(schedule.id)
      ElMessage.info('今天已经打过卡了')
    } else {
      ElMessage.error(getErrorMessage(error, '打卡失败'))
    }
  } finally {
    const next = new Set(checkingIds.value)
    next.delete(schedule.id)
    checkingIds.value = next
  }
}

function shiftWeek(step) {
  weekStart.value = addDays(weekStart.value, step * 7)
}

function goToday() {
  weekStart.value = startOfWeek(new Date())
}

/** 导出当前周为 PNG：接口需要携带 token，故用 blob 下载而不是 a 标签直链 */
async function exportWeek() {
  if (exporting.value) return
  exporting.value = true
  try {
    const start = days.value[0].dateStr
    const response = await exportWeekPng(start)
    const url = URL.createObjectURL(new Blob([response.data], { type: 'image/png' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `拾光周计划-${start}.png`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('本周计划已导出')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '导出失败，请稍后重试'))
  } finally {
    exporting.value = false
  }
}

function minutesToTime(minutes) {
  return `${pad2(Math.floor(minutes / 60))}:${pad2(minutes % 60)}:00`
}

function openImport() {
  importText.value = ''
  importCreated.value = null
  importErrors.value = []
  importVisible.value = true
}

function fillImportExample() {
  importText.value = IMPORT_EXAMPLE
}

/** 解析并导入课表文本；成功后刷新当前周视图 */
async function submitImport() {
  if (importing.value) return
  const text = importText.value.trim()
  if (!text) {
    ElMessage.warning('请先粘贴课表文本')
    return
  }

  importing.value = true
  try {
    const { data } = await importTimetable(text)
    importCreated.value = Number(data?.created) || 0
    importErrors.value = Array.isArray(data?.errors) ? data.errors : []

    if (importCreated.value > 0) {
      ElMessage.success(`成功导入 ${importCreated.value} 条课程`)
      await loadWeekData()
    } else {
      ElMessage.warning('没有成功导入的课程，请检查格式')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '导入失败，请稍后重试'))
  } finally {
    importing.value = false
  }
}

function noticeActionLabel(action) {
  if (action === 'cancel') return '取消课程'
  if (action === 'change') return '调整时间'
  return '未识别'
}

function openNotice() {
  noticeText.value = ''
  noticeResult.value = null
  noticeVisible.value = true
}

function fillNoticeExample() {
  noticeText.value = NOTICE_EXAMPLE
}

/** 解析通知文本，只展示结果，不直接修改日程 */
async function submitNoticeParse() {
  if (noticeParsing.value) return
  const text = noticeText.value.trim()
  if (!text) {
    ElMessage.warning('请先粘贴调课通知')
    return
  }

  noticeParsing.value = true
  try {
    const { data } = await parseNotice(text)
    noticeResult.value = data
    if (data?.action === 'none') {
      ElMessage.warning('未能自动识别，请手动处理')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '解析失败，请稍后重试'))
  } finally {
    noticeParsing.value = false
  }
}

/** 确认后真正执行取消 / 改时间 */
async function confirmNoticeResult() {
  const result = noticeResult.value
  if (!result || noticeActing.value) return

  noticeActing.value = true
  try {
    const { data } = await confirmNotice(result.id)
    ElMessage.success(data?.message || '已执行调课')
    noticeVisible.value = false
    noticeResult.value = null

    // 跳到课程实际所在周，确保修改结果立刻可见
    const targetDate = data?.schedule?.date || result.matched_schedule?.date
    if (targetDate) {
      weekStart.value = startOfWeek(parseDateStr(targetDate))
    } else {
      await loadWeekData()
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '执行失败'))
  } finally {
    noticeActing.value = false
  }
}

/** 取消 / 丢弃解析结果，不修改日程 */
async function discardNoticeResult() {
  const result = noticeResult.value
  if (!result || noticeActing.value) return

  noticeActing.value = true
  try {
    await discardNotice(result.id)
    ElMessage.info('已丢弃该通知')
    noticeResult.value = null
    noticeVisible.value = false
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '丢弃失败'))
  } finally {
    noticeActing.value = false
  }
}

async function closeNoticeDialog() {
  // 未识别的通知没有可执行动作，关闭时顺手丢弃，避免留下无用记录
  if (noticeResult.value?.action === 'none') {
    discardNotice(noticeResult.value.id).catch(() => {})
  }
  noticeResult.value = null
  noticeVisible.value = false
}

/** 点击空白格子：按点击的纵向位置换算开始时间，默认 1 小时 */
function onColumnClick(day, event) {
  const rect = event.currentTarget.getBoundingClientRect()
  const offsetY = Math.min(Math.max(event.clientY - rect.top, 0), rect.height)
  const rawMinutes = START_HOUR * 60 + (offsetY / HOUR_HEIGHT) * 60
  const snapped = Math.floor(rawMinutes / SNAP_MINUTES) * SNAP_MINUTES
  const start = Math.min(Math.max(snapped, START_HOUR * 60), (END_HOUR - 1) * 60)
  const end = Math.min(start + 60, END_HOUR * 60)

  openDialog({
    date: day.dateStr,
    weekday: day.weekday,
    start: minutesToTime(start),
    end: minutesToTime(end),
  })
}

function openCreateFromHeader() {
  const current = days.value.find((day) => day.isToday) || days.value[0]
  openDialog({
    date: current.dateStr,
    weekday: current.weekday,
    start: '08:00:00',
    end: '09:00:00',
  })
}

function openDialog(initial) {
  dialogInitial.value = initial
  dialogVisible.value = true
}

function openDetail(schedule) {
  activeSchedule.value = schedule
  detailVisible.value = true
}

function handleEdit() {
  if (!activeSchedule.value) return
  editTarget.value = { ...activeSchedule.value }
  detailVisible.value = false
  editVisible.value = true
}

async function askDeleteConfirm(message) {
  try {
    await ElMessageBox.confirm(message, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
    return true
  } catch {
    return false
  }
}

async function performDelete(scope, schedule) {
  try {
    if (scope === 'series') {
      await deleteSeries(schedule.series_id)
      ElMessage.success('已删除整个系列')
    } else {
      await deleteSchedule(schedule.id)
      ElMessage.success('已删除该日程')
    }

    detailVisible.value = false
    deleteScopeVisible.value = false
    await loadWeekData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '删除失败'))
  }
}

async function handleDelete() {
  const schedule = activeSchedule.value
  if (!schedule) return

  // 周期日程需要先选择删除范围
  if (schedule.series_id) {
    detailVisible.value = false
    deleteScopeVisible.value = true
    return
  }

  if (!(await askDeleteConfirm(`确定删除日程「${schedule.title}」吗？`))) return
  await performDelete('single', schedule)
}

async function confirmDeleteScope(scope) {
  const schedule = activeSchedule.value
  if (!schedule) return

  const message =
    scope === 'series'
      ? `确定删除整个系列「${schedule.title}」吗？该系列内的所有日程都会被删除。`
      : `确定只删除 ${schedule.date} 的「${schedule.title}」吗？`

  if (!(await askDeleteConfirm(message))) return
  await performDelete(scope, schedule)
}

watch(weekStart, loadWeekData)
onMounted(loadWeekData)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">周视图</h1>
        <p class="page-sub">{{ weekRangeLabel }} · 点击空白格子即可添加日程</p>
      </div>

      <div class="head-actions">
        <el-button-group>
          <el-button @click="shiftWeek(-1)">上一周</el-button>
          <el-button @click="goToday">本周</el-button>
          <el-button @click="shiftWeek(1)">下一周</el-button>
        </el-button-group>
        <el-button @click="openImport">导入课表</el-button>
        <el-button @click="openNotice">调课通知</el-button>
        <el-button :loading="exporting" @click="exportWeek">导出本周</el-button>
        <el-button type="primary" @click="openCreateFromHeader">添加日程</el-button>
      </div>
    </div>

    <div class="week-scroll">
      <div class="week-board" v-loading="loading">
        <div class="week-header">
          <div class="time-corner"></div>
          <div
            v-for="day in days"
            :key="day.dateStr"
            class="day-head"
            :class="{ 'is-today': day.isToday }"
          >
            <span class="day-name">{{ day.weekdayLabel }}</span>
            <span class="day-date">{{ day.monthDay }}</span>
          </div>
        </div>

        <div class="week-body">
          <div class="time-axis" :style="{ height: `${gridHeight}px` }">
            <div
              v-for="label in hourLabels"
              :key="label"
              class="time-label"
              :style="{ height: `${HOUR_HEIGHT}px` }"
            >
              <span>{{ label }}</span>
            </div>
          </div>

          <div
            v-for="day in days"
            :key="day.dateStr"
            class="day-column"
            :class="{ 'is-today': day.isToday }"
            :style="{ height: `${gridHeight}px` }"
            @click="onColumnClick(day, $event)"
          >
            <!-- 固定日常：浅灰半透明背景块，位于日程块下方，点击只提示不新增 -->
            <div
              v-for="routine in routinesByDay[day.dateStr]"
              :key="`routine-${routine.id}`"
              class="routine-block"
              :style="routineStyle(routine)"
              :title="routineTooltip(routine)"
              @click.stop="notifyRoutine"
            >
              <span class="routine-title">{{ routine.title }}</span>
              <span class="routine-time">
                {{ formatTime(routine.start_time) }} - {{ formatTime(routine.end_time) }}
              </span>
            </div>

            <div
              v-for="schedule in eventsByDay[day.dateStr]"
              :key="schedule.id"
              class="event-block"
              :style="eventStyle(schedule)"
              @click.stop="openDetail(schedule)"
            >
              <span class="event-title">{{ schedule.title }}</span>
              <span class="event-time">
                {{ formatTime(schedule.start_time) }} - {{ formatTime(schedule.end_time) }}
              </span>
              <button
                type="button"
                class="checkin-btn"
                :class="{
                  'is-checked': isChecked(schedule),
                  'is-pending': isCheckingIn(schedule),
                }"
                :title="isChecked(schedule) ? '已打卡' : '打卡'"
                @click.stop="doCheckin(schedule)"
              >
                {{ isChecked(schedule) ? '✓' : '打卡' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <AddScheduleDialog
      v-model="dialogVisible"
      :initial="dialogInitial"
      @created="loadWeekData"
    />

    <ScheduleDetailDialog
      v-model="detailVisible"
      :schedule="activeSchedule"
      @edit="handleEdit"
      @delete="handleDelete"
    />

    <EditScheduleDialog v-model="editVisible" :schedule="editTarget" @saved="loadWeekData" />

    <el-dialog
      v-model="deleteScopeVisible"
      title="删除周期日程"
      width="430px"
      append-to-body
    >
      <p class="delete-scope-text">该日程属于一个批量周期系列，请选择删除范围：</p>
      <ul class="delete-scope-list">
        <li>
          <strong>仅删除本次</strong>：只删除 {{ activeSchedule?.date }} 这一条日程
        </li>
        <li>
          <strong>删除整个系列</strong>：该系列生成的所有日程都会被删除
        </li>
      </ul>

      <template #footer>
        <el-button @click="deleteScopeVisible = false">取消</el-button>
        <el-button type="danger" plain @click="confirmDeleteScope('single')">仅删除本次</el-button>
        <el-button type="danger" @click="confirmDeleteScope('series')">删除整个系列</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="导入课表" width="580px" append-to-body>
      <p class="import-hint">
        每行一门课程，格式为「星期几 HH:MM-HH:MM 课程名 [地点]」，地点可省略；
        星期支持 周一 / 星期一 / Mon 等写法，导入后按当前日期起 20 周重复。
      </p>

      <el-input
        v-model="importText"
        type="textarea"
        :rows="9"
        resize="vertical"
        placeholder="周一 08:00-09:40 高等数学 [教一楼 301]"
      />

      <div class="import-example-head">
        <span>格式示例</span>
        <el-button link type="primary" size="small" @click="fillImportExample">填入示例</el-button>
      </div>
      <pre class="import-example">{{ IMPORT_EXAMPLE }}</pre>

      <div v-if="importCreated !== null" class="import-result">
        <p class="import-summary">成功导入 {{ importCreated }} 条课程</p>
        <template v-if="importErrors.length">
          <p class="import-failed-title">以下 {{ importErrors.length }} 行失败：</p>
          <ul class="import-error-list">
            <li v-for="item in importErrors" :key="item.line">
              <span class="import-error-line">第 {{ item.line }} 行</span>
              <span class="import-error-content">{{ item.content }}</span>
              <span class="import-error-reason">{{ item.reason }}</span>
            </li>
          </ul>
        </template>
        <p v-else class="import-all-ok">所有行均导入成功。</p>
      </div>

      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="submitImport">解析并导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="noticeVisible" title="调课通知" width="560px" append-to-body>
      <p class="import-hint">
        粘贴老师发的调课通知，系统会识别「取消」「改到 / 调整至 / 换成」等关键词，
        自动匹配你的课程。解析结果确认后才会修改日程。
      </p>

      <el-input
        v-model="noticeText"
        type="textarea"
        :rows="4"
        resize="vertical"
        placeholder="如：因老师出差，周三08:00的高等数学改到周五14:00-15:40"
      />

      <div class="import-example-head">
        <span>示例</span>
        <el-button link type="primary" size="small" @click="fillNoticeExample">填入示例</el-button>
      </div>
      <pre class="import-example">{{ NOTICE_EXAMPLE }}</pre>

      <div v-if="noticeResult" class="notice-card" :class="`is-${noticeResult.action}`">
        <div class="notice-card-head">
          <span class="notice-action">{{ noticeActionLabel(noticeResult.action) }}</span>
          <span class="notice-confidence" :class="{ 'is-low': noticeResult.confidence === '低' }">
            置信度：{{ noticeResult.confidence }}
          </span>
        </div>
        <p class="notice-card-text">{{ noticeResult.message }}</p>
        <p
          v-if="noticeResult.action !== 'none' && noticeResult.confidence === '低'"
          class="notice-card-hint"
        >
          匹配置信度较低，请确认课程与时间是否正确后再执行。
        </p>
      </div>

      <template #footer>
        <el-button @click="closeNoticeDialog">关闭</el-button>
        <el-button
          v-if="noticeResult && noticeResult.action !== 'none'"
          :loading="noticeActing"
          @click="discardNoticeResult"
        >
          取消（丢弃）
        </el-button>
        <el-button
          v-if="noticeResult && noticeResult.action !== 'none'"
          type="primary"
          :loading="noticeActing"
          @click="confirmNoticeResult"
        >
          确认执行
        </el-button>
        <el-button
          v-else
          type="primary"
          :loading="noticeParsing"
          @click="submitNoticeParse"
        >
          解析通知
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.week-scroll {
  overflow: auto;
  max-height: calc(100vh - 214px);
  border: 1px solid var(--sg-border);
  border-radius: var(--sg-radius);
  background: var(--sg-panel);
  box-shadow: var(--sg-shadow-sm);
}

.week-board {
  position: relative;
  min-width: 760px;
}

.week-header {
  position: sticky;
  top: 0;
  z-index: 5;
  display: grid;
  grid-template-columns: 64px repeat(7, minmax(0, 1fr));
  background: #fffdfa;
  border-bottom: 1px solid var(--sg-border);
}

.time-corner {
  border-right: 1px solid var(--sg-border);
}

.day-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 8px;
  border-right: 1px solid var(--sg-border-soft);
}

.day-head:last-child {
  border-right: none;
}

.day-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--sg-text-2);
}

.day-date {
  font-size: 12px;
  color: var(--sg-text-3);
}

.day-head.is-today {
  background: #fff4ea;
}

.day-head.is-today .day-name,
.day-head.is-today .day-date {
  color: var(--sg-primary-strong);
}

.week-body {
  display: flex;
}

.time-axis {
  flex: none;
  width: 64px;
  border-right: 1px solid var(--sg-border);
}

.time-label {
  display: flex;
  justify-content: flex-end;
  padding-right: 8px;
  font-size: 11px;
  color: var(--sg-text-3);
}

.time-label span {
  transform: translateY(-7px);
}

.day-column {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
  border-right: 1px solid var(--sg-border-soft);
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 55px,
    var(--sg-border-soft) 55px,
    var(--sg-border-soft) 56px
  );
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.day-column:last-child {
  border-right: none;
}

.day-column:hover {
  background-color: #fffbf5;
}

.day-column.is-today {
  background-color: #fffaf4;
}

.routine-block {
  position: absolute;
  left: 2px;
  right: 2px;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 3px 6px;
  border: 1px dashed #d9d2c8;
  border-radius: 8px;
  background: rgba(122, 115, 106, 0.08);
  color: #9a8f82;
  font-size: 11px;
  line-height: 1.3;
  overflow: hidden;
  cursor: pointer;
}

.routine-title {
  overflow: hidden;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.routine-time {
  font-size: 10px;
  opacity: 0.85;
  white-space: nowrap;
}

.event-block {
  position: absolute;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 4px 6px;
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.35;
  overflow: hidden;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(60, 45, 30, 0.06);
}

.event-title {
  overflow: hidden;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.event-time {
  font-size: 11px;
  opacity: 0.78;
  white-space: nowrap;
}

.checkin-btn {
  position: absolute;
  right: 3px;
  bottom: 3px;
  z-index: 3;
  height: 16px;
  padding: 0 6px;
  border: 1px solid rgba(60, 45, 30, 0.18);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  color: inherit;
  font-size: 10px;
  line-height: 14px;
  cursor: pointer;
  transition: background-color 0.15s ease, opacity 0.15s ease;
}

.checkin-btn:hover {
  background: #fff;
}

.checkin-btn.is-pending {
  opacity: 0.6;
}

.checkin-btn.is-checked,
.checkin-btn.is-checked:hover {
  border-color: #ddd5cc;
  background: #f1ebe4;
  color: #a89a8c;
  cursor: default;
}

@media (max-width: 720px) {
  .week-scroll {
    max-height: none;
  }
}

.delete-scope-text {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--sg-text-2);
}

.delete-scope-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--sg-text-3);
}

.delete-scope-list strong {
  color: var(--sg-text);
}

.import-hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--sg-text-3);
}

.import-example-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 14px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--sg-text-2);
}

.import-example {
  margin: 0;
  padding: 10px 12px;
  border: 1px dashed var(--sg-border);
  border-radius: 8px;
  background: #fffaf4;
  color: var(--sg-text-2);
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}

.import-result {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f7f5f1;
}

.import-summary {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--sg-text);
}

.import-failed-title {
  margin: 0 0 6px;
  font-size: 12px;
  color: #b4541f;
}

.import-error-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
}

.import-error-list li {
  display: grid;
  gap: 2px;
  padding: 6px 8px;
  border-left: 3px solid #e9a07a;
  border-radius: 4px;
  background: #fff;
  font-size: 12px;
  line-height: 1.5;
}

.import-error-line {
  font-weight: 600;
  color: #b4541f;
}

.import-error-content {
  color: var(--sg-text-2);
  word-break: break-all;
}

.import-error-reason {
  color: var(--sg-text-3);
}

.import-all-ok {
  margin: 0;
  font-size: 12px;
  color: #2f6446;
}

.notice-card {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--sg-border);
  border-left: 3px solid #e09a6a;
  border-radius: 10px;
  background: #fffaf4;
}

.notice-card.is-cancel {
  border-left-color: #d98a8a;
  background: #fdf5f5;
}

.notice-card.is-none {
  border-left-color: #b9b0a6;
  background: #f7f5f1;
}

.notice-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.notice-action {
  font-size: 13px;
  font-weight: 700;
  color: var(--sg-text);
}

.notice-confidence {
  padding: 1px 8px;
  border-radius: 999px;
  background: #e8f3ec;
  color: #2f6446;
  font-size: 11px;
}

.notice-confidence.is-low {
  background: #fdf1e4;
  color: #b4541f;
}

.notice-card-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--sg-text-2);
}

.notice-card-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #b4541f;
}
</style>
