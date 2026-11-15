<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import AddScheduleDialog from '@/components/AddScheduleDialog.vue'
import EditScheduleDialog from '@/components/EditScheduleDialog.vue'
import ScheduleDetailDialog from '@/components/ScheduleDetailDialog.vue'
import { listRoutines } from '@/api/routines'
import { deleteSchedule, listSchedules } from '@/api/schedules'
import { deleteSeries } from '@/api/series'
import { getErrorMessage } from '@/utils/error'
import {
  WEEKDAY_LABELS,
  addDays,
  formatMonthDay,
  formatTime,
  formatWeekRange,
  isSameDay,
  pad2,
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

const detailVisible = ref(false)
const activeSchedule = ref(null)
const editVisible = ref(false)
const editTarget = ref(null)
const deleteScopeVisible = ref(false)

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

function colorOf(schedule) {
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
    // 同时拉取本周日程与启用的固定日常；任一失败不影响另一部分展示
    const [schedulesResult, routinesResult] = await Promise.allSettled([
      listSchedules(start, end),
      listRoutines({ is_active: true }),
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
  } finally {
    loading.value = false
  }
}

function shiftWeek(step) {
  weekStart.value = addDays(weekStart.value, step * 7)
}

function goToday() {
  weekStart.value = startOfWeek(new Date())
}

function minutesToTime(minutes) {
  return `${pad2(Math.floor(minutes / 60))}:${pad2(minutes % 60)}:00`
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
</style>
