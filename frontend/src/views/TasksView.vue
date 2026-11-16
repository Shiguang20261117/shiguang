<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createCheckin, listCheckins } from '@/api/checkins'
import { createTask, generateTaskSchedule, listTasks } from '@/api/tasks'
import { useCheckinStore } from '@/stores/checkins'
import { getErrorMessage } from '@/utils/error'
import {
  WEEKDAY_LABELS,
  addDays,
  formatTime,
  parseDateStr,
  startOfWeek,
  toDateStr,
} from '@/utils/date'

const router = useRouter()
const checkinStore = useCheckinStore()

const tasks = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const generatingId = ref(null)
const expandedIds = ref([])
const formRef = ref()
// 已打卡的日程 id 集合（任务槽位关联 schedule_id）
const checkedScheduleIds = ref(new Set())
const checkingSlotIds = ref(new Set())

const form = reactive({
  title: '',
  week_start: '',
  target_count: 4,
  duration_min: 40,
})

const rules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  week_start: [{ required: true, message: '请选择目标周（周一）', trigger: 'change' }],
  target_count: [{ required: true, message: '请输入目标次数', trigger: 'blur' }],
  duration_min: [{ required: true, message: '请输入每次时长', trigger: 'blur' }],
}

const STATUS_LABELS = {
  pending: '待排期',
  scheduled: '已排期',
}

function weekdayOf(dateStr) {
  return WEEKDAY_LABELS[(parseDateStr(dateStr).getDay() + 6) % 7]
}

function weekLabel(weekStart) {
  const start = parseDateStr(weekStart)
  const end = addDays(start, 6)
  return `${weekStart} ~ ${toDateStr(end).slice(5)}`
}

function taskStatusTag(task) {
  return task.status === 'scheduled'
    ? { text: STATUS_LABELS.scheduled, type: 'success' }
    : { text: STATUS_LABELS.pending, type: 'info' }
}

function slotStatusTag(slot) {
  if (slot.status === 'done') return { text: '已完成', type: 'success' }
  if (slot.status === 'missed') return { text: '已错过', type: 'danger' }

  // 仍在计划中但结束时间已过，视为已错过
  const end = new Date(`${slot.date}T${formatTime(slot.end_time)}`)
  if (end < new Date()) return { text: '已错过', type: 'danger' }
  return { text: '待执行', type: 'primary' }
}

function isExpanded(task) {
  return expandedIds.value.includes(task.id)
}

function toggleExpand(task) {
  expandedIds.value = isExpanded(task)
    ? expandedIds.value.filter((id) => id !== task.id)
    : [...expandedIds.value, task.id]
}

function disableNonMonday(date) {
  return date.getDay() !== 1
}

function isSlotChecked(slot) {
  return Boolean(slot.schedule_id) && checkedScheduleIds.value.has(slot.schedule_id)
}

function isSlotChecking(slot) {
  return checkingSlotIds.value.has(slot.id)
}

async function loadTasks() {
  loading.value = true
  try {
    const [tasksResult, checkinsResult] = await Promise.allSettled([
      listTasks(),
      listCheckins(),
    ])

    if (tasksResult.status === 'fulfilled') {
      const data = tasksResult.value.data
      tasks.value = Array.isArray(data) ? data : []
    } else {
      tasks.value = []
      ElMessage.error(getErrorMessage(tasksResult.reason, '加载任务列表失败'))
    }

    if (checkinsResult.status === 'fulfilled') {
      const data = checkinsResult.value.data
      checkedScheduleIds.value = new Set(
        (Array.isArray(data) ? data : [])
          .filter((item) => item.target_type === 'schedule')
          .map((item) => item.target_id),
      )
    }
  } finally {
    loading.value = false
  }
}

async function doCheckinSlot(slot) {
  if (!slot.schedule_id || isSlotChecked(slot) || isSlotChecking(slot)) return

  const pending = new Set(checkingSlotIds.value)
  pending.add(slot.id)
  checkingSlotIds.value = pending

  try {
    await createCheckin({ target_type: 'schedule', target_id: slot.schedule_id })
    const next = new Set(checkedScheduleIds.value)
    next.add(slot.schedule_id)
    checkedScheduleIds.value = next
    ElMessage.success('已打卡')
    checkinStore.markChecked()
  } catch (error) {
    if (error.response?.status === 409) {
      const next = new Set(checkedScheduleIds.value)
      next.add(slot.schedule_id)
      checkedScheduleIds.value = next
      ElMessage.info('今天已经打过卡了')
    } else {
      ElMessage.error(getErrorMessage(error, '打卡失败'))
    }
  } finally {
    const next = new Set(checkingSlotIds.value)
    next.delete(slot.id)
    checkingSlotIds.value = next
  }
}

function openDialog() {
  form.title = ''
  form.week_start = toDateStr(startOfWeek(new Date()))
  form.target_count = 4
  form.duration_min = 40
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createTask({
      title: form.title.trim(),
      week_start: form.week_start,
      target_count: form.target_count,
      duration_min: form.duration_min,
    })
    ElMessage.success('任务已添加')
    dialogVisible.value = false
    await loadTasks()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '添加任务失败'))
  } finally {
    submitting.value = false
  }
}

async function confirmRegenerate() {
  try {
    await ElMessageBox.confirm(
      '将重新生成排期，原排期会被替换，是否继续？',
      '重新生成排期',
      {
        type: 'warning',
        confirmButtonText: '继续',
        cancelButtonText: '取消',
      },
    )
    return true
  } catch {
    return false
  }
}

async function scheduleTask(task) {
  const hasSchedule = task.status === 'scheduled' || (task.slots?.length || 0) > 0
  if (hasSchedule && !(await confirmRegenerate())) return

  generatingId.value = task.id
  try {
    const { data } = await generateTaskSchedule(task.id)
    const scheduled = data?.scheduled_count || 0
    const shortage = data?.shortage ?? Math.max(0, task.target_count - scheduled)
    await loadTasks()

    ElMessageBox.alert(
      `已排期 ${scheduled} 次，还差 ${shortage} 次。可前往周视图查看生成的日程。`,
      '排期已生成',
      {
        confirmButtonText: '去周视图查看',
        callback: () => router.push('/week'),
      },
    ).catch(() => {})
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '生成排期失败'))
  } finally {
    generatingId.value = null
  }
}

onMounted(loadTasks)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">任务</h1>
        <p class="page-sub">设定每周目标，自动把任务安排进空闲时间</p>
      </div>
      <el-button type="primary" @click="openDialog">添加任务</el-button>
    </div>

    <div class="task-list" v-loading="loading">
      <article v-for="task in tasks" :key="task.id" class="panel task-item">
        <div class="task-main">
          <div class="task-head">
            <span class="task-title">{{ task.title }}</span>
            <el-tag :type="taskStatusTag(task).type" size="small" effect="light">
              {{ taskStatusTag(task).text }}
            </el-tag>
          </div>

          <div class="task-meta">
            <span>
              <span class="meta-label">目标周</span>
              {{ weekLabel(task.week_start) }}
            </span>
            <span>
              <span class="meta-label">目标次数</span>
              {{ task.target_count }} 次
            </span>
            <span>
              <span class="meta-label">每次时长</span>
              {{ task.duration_min }} 分钟
            </span>
            <span>
              <span class="meta-label">已排期</span>
              {{ task.slots?.length || 0 }} / {{ task.target_count }} 次
            </span>
          </div>

          <div v-if="isExpanded(task)" class="slot-list">
            <p v-if="!task.slots?.length" class="slot-empty">
              还没有排期，点击「生成排期」自动安排时间
            </p>
            <ul v-else class="slot-ul">
              <li v-for="slot in task.slots" :key="slot.id" class="slot-row">
                <span class="slot-when">
                  {{ weekdayOf(slot.date) }} {{ slot.date }}
                  {{ formatTime(slot.start_time) }} - {{ formatTime(slot.end_time) }}
                </span>
                <div class="slot-actions">
                  <el-tag :type="slotStatusTag(slot).type" size="small" effect="plain">
                    {{ slotStatusTag(slot).text }}
                  </el-tag>
                  <el-button
                    v-if="slot.schedule_id"
                    size="small"
                    :type="isSlotChecked(slot) ? 'info' : 'primary'"
                    :plain="!isSlotChecked(slot)"
                    :disabled="isSlotChecked(slot)"
                    :loading="isSlotChecking(slot)"
                    @click="doCheckinSlot(slot)"
                  >
                    {{ isSlotChecked(slot) ? '✓ 已打卡' : '打卡' }}
                  </el-button>
                </div>
              </li>
            </ul>
          </div>
        </div>

        <div class="task-actions">
          <el-button text @click="toggleExpand(task)">
            {{ isExpanded(task) ? '收起排期' : '查看排期' }}
          </el-button>
          <el-button
            type="primary"
            plain
            :loading="generatingId === task.id"
            @click="scheduleTask(task)"
          >
            生成排期
          </el-button>
        </div>
      </article>

      <p v-if="!loading && !tasks.length" class="task-empty">
        还没有任务，点击右上角「添加任务」设定本周目标吧
      </p>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="添加任务"
      width="460px"
      :close-on-click-modal="false"
      append-to-body
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="form.title" maxlength="200" placeholder="如：跑步" />
        </el-form-item>

        <el-form-item label="目标周" prop="week_start">
          <el-date-picker
            v-model="form.week_start"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择目标周"
            :disabled-date="disableNonMonday"
            style="width: 100%"
          />
          <p class="form-hint">请选择某一周的周一</p>
        </el-form-item>

        <el-form-item label="目标次数" prop="target_count">
          <el-input-number v-model="form.target_count" :min="1" :max="99" />
        </el-form-item>

        <el-form-item label="每次时长" prop="duration_min">
          <el-input-number v-model="form.duration_min" :min="1" :max="1440" :step="10" />
          <span class="form-unit">分钟</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 120px;
}

.task-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

.task-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.task-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.task-title {
  font-size: 17px;
  font-weight: 700;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 22px;
  flex-wrap: wrap;
  color: var(--sg-text-2);
  font-size: 13px;
}

.meta-label {
  margin-right: 6px;
  color: var(--sg-text-3);
  font-size: 12px;
}

.task-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 4px;
}

.slot-list {
  margin-top: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #fbf8f4;
  border: 1px solid var(--sg-border-soft);
}

.slot-ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.slot-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--sg-text-2);
}

.slot-when {
  word-break: break-all;
}

.slot-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.slot-empty {
  margin: 2px 0;
  color: var(--sg-text-3);
  font-size: 12px;
}

.task-empty {
  margin: 32px 0;
  color: var(--sg-text-3);
  font-size: 13px;
  text-align: center;
}

.form-hint {
  margin: 4px 0 0;
  color: var(--sg-text-3);
  font-size: 12px;
  line-height: 1.4;
}

.form-unit {
  margin-left: 8px;
  color: var(--sg-text-3);
  font-size: 13px;
}

@media (max-width: 720px) {
  .task-item {
    flex-direction: column;
    align-items: stretch;
  }

  .task-actions {
    align-self: flex-end;
  }
}
</style>
