<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createRoutine, deleteRoutine, listRoutines } from '@/api/routines'
import { getErrorMessage } from '@/utils/error'
import { WEEKDAY_LABELS, formatTime, timeToMinutes } from '@/utils/date'

const routines = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  title: '',
  weekday: 0,
  start_time: '07:30:00',
  end_time: '08:00:00',
  description: '',
})

const rules = {
  title: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

const groupedRoutines = computed(() =>
  WEEKDAY_LABELS.map((label, weekday) => ({
    weekday,
    label,
    items: routines.value
      .filter((routine) => routine.weekday === weekday)
      .sort((a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time)),
  })),
)

async function loadRoutines() {
  loading.value = true
  try {
    const { data } = await listRoutines()
    routines.value = Array.isArray(data) ? data : []
  } catch (error) {
    routines.value = []
    ElMessage.error(getErrorMessage(error, '加载固定日常失败'))
  } finally {
    loading.value = false
  }
}

function openDialog() {
  form.title = ''
  form.weekday = 0
  form.start_time = '07:30:00'
  form.end_time = '08:00:00'
  form.description = ''
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (timeToMinutes(form.end_time) <= timeToMinutes(form.start_time)) {
    ElMessage.warning('结束时间必须晚于开始时间')
    return
  }

  submitting.value = true
  try {
    await createRoutine({
      title: form.title.trim(),
      description: form.description.trim() || null,
      weekday: form.weekday,
      start_time: form.start_time,
      end_time: form.end_time,
      is_active: true,
    })
    ElMessage.success('固定日常已添加')
    dialogVisible.value = false
    await loadRoutines()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存失败'))
  } finally {
    submitting.value = false
  }
}

async function removeRoutine(routine) {
  try {
    await ElMessageBox.confirm(`确定删除固定日常「${routine.title}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }

  try {
    await deleteRoutine(routine.id)
    ElMessage.success('已删除固定日常')
    await loadRoutines()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '删除失败'))
  }
}

onMounted(loadRoutines)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">固定日常</h1>
        <p class="page-sub">按星期几重复的作息，比如三餐、睡眠、运动</p>
      </div>
      <el-button type="primary" @click="openDialog">添加固定日常</el-button>
    </div>

    <div class="routine-grid" v-loading="loading">
      <section v-for="group in groupedRoutines" :key="group.weekday" class="panel routine-day">
        <header class="routine-day-head">
          <span class="routine-day-name">{{ group.label }}</span>
          <span class="routine-day-count">{{ group.items.length ? `${group.items.length} 项` : '空' }}</span>
        </header>

        <div v-if="group.items.length" class="routine-list">
          <div
            v-for="routine in group.items"
            :key="routine.id"
            class="routine-item"
            :class="{ 'is-muted': !routine.is_active }"
          >
            <div class="routine-item-head">
              <span class="routine-time">
                {{ formatTime(routine.start_time) }} - {{ formatTime(routine.end_time) }}
              </span>
              <el-button link type="danger" size="small" @click="removeRoutine(routine)">
                删除
              </el-button>
            </div>
            <span class="routine-title">{{ routine.title }}</span>
            <span v-if="routine.description" class="routine-desc">{{ routine.description }}</span>
          </div>
        </div>

        <p v-else class="routine-empty">暂无固定安排</p>
      </section>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="添加固定日常"
      width="460px"
      :close-on-click-modal="false"
      append-to-body
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="76px">
        <el-form-item label="名称" prop="title">
          <el-input v-model="form.title" maxlength="200" placeholder="如：早餐 / 午休 / 睡觉" />
        </el-form-item>

        <el-form-item label="星期" required>
          <el-select v-model="form.weekday" style="width: 100%">
            <el-option
              v-for="(label, index) in WEEKDAY_LABELS"
              :key="label"
              :label="label"
              :value="index"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="时间" required>
          <div class="time-row">
            <el-time-picker
              v-model="form.start_time"
              value-format="HH:mm:ss"
              format="HH:mm"
              placeholder="开始"
              style="width: 100%"
            />
            <span class="time-sep">至</span>
            <el-time-picker
              v-model="form.end_time"
              value-format="HH:mm:ss"
              format="HH:mm"
              placeholder="结束"
              style="width: 100%"
            />
          </div>
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            maxlength="500"
            placeholder="选填"
          />
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
.routine-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.routine-day {
  display: flex;
  flex-direction: column;
  min-height: 150px;
  padding: 16px 18px 18px;
}

.routine-day-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.routine-day-name {
  font-size: 15px;
  font-weight: 700;
}

.routine-day-count {
  padding: 2px 8px;
  border-radius: 999px;
  background: #f7f1e9;
  color: var(--sg-text-3);
  font-size: 11px;
}

.routine-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.routine-item {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border: 1px solid var(--sg-border-soft);
  border-left: 3px solid #f0a578;
  border-radius: 10px;
  background: #fffcf8;
}

.routine-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.routine-item.is-muted {
  opacity: 0.55;
}

.routine-time {
  font-size: 11px;
  color: var(--sg-primary-strong);
}

.routine-title {
  font-size: 14px;
  font-weight: 600;
}

.routine-desc {
  font-size: 12px;
  color: var(--sg-text-3);
  line-height: 1.5;
}

.routine-empty {
  margin: auto 0;
  color: var(--sg-text-3);
  font-size: 12px;
  text-align: center;
}
</style>
