<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { listRoutines } from '@/api/routines'
import { createSchedule } from '@/api/schedules'
import { createSeries } from '@/api/series'
import { getErrorMessage } from '@/utils/error'
import {
  WEEKDAY_LABELS,
  addDays,
  parseDateStr,
  timeToMinutes,
  toBackendWeekday,
  toDateStr,
} from '@/utils/date'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initial: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue', 'created'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const formRef = ref()
const submitting = ref(false)
const mode = ref('single')

const form = reactive({
  title: '',
  description: '',
  location: '',
  date: '',
  start_time: '08:00:00',
  end_time: '10:00:00',
  weekday: 2,
  dateRange: [],
})

const rules = {
  title: [{ required: true, message: '请输入日程标题', trigger: 'blur' }],
}

// 每次打开时按点击的位置重置表单
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return

    mode.value = 'single'
    const baseDate = props.initial?.date || toDateStr(new Date())

    form.title = ''
    form.description = ''
    form.location = ''
    form.date = baseDate
    form.start_time = props.initial?.start || '08:00:00'
    form.end_time = props.initial?.end || '10:00:00'
    form.weekday = props.initial?.weekday ?? 2
    // 假设：后端没有"学期周次"概念，批量模式直接用起止日期；
    // 默认从选中日期开始、覆盖 8 周，用户可自行调整。
    form.dateRange = [baseDate, toDateStr(addDays(parseDateStr(baseDate), 7 * 7))]

    nextTick(() => formRef.value?.clearValidate())
  },
)

/** 查找单次日程与启用中的固定日常的时间冲突（按日期对应的星期几） */
async function findRoutineConflict(payload) {
  try {
    const { data } = await listRoutines({ is_active: true })
    const routines = Array.isArray(data) ? data : []
    const weekday = toBackendWeekday(parseDateStr(payload.date))
    const start = timeToMinutes(payload.start_time)
    const end = timeToMinutes(payload.end_time)

    return (
      routines.find(
        (routine) =>
          routine.weekday === weekday &&
          timeToMinutes(routine.start_time) < end &&
          timeToMinutes(routine.end_time) > start,
      ) || null
    )
  } catch {
    // 冲突检查失败不阻塞保存，交给后端正常保存
    return null
  }
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (timeToMinutes(form.end_time) <= timeToMinutes(form.start_time)) {
    ElMessage.warning('结束时间必须晚于开始时间')
    return
  }

  if (mode.value === 'single') {
    if (!form.date) {
      ElMessage.warning('请选择日期')
      return
    }
  } else if (!form.dateRange || form.dateRange.length !== 2) {
    ElMessage.warning('请选择起止日期范围')
    return
  }

  submitting.value = true
  try {
    if (mode.value === 'single') {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        date: form.date,
        start_time: form.start_time,
        end_time: form.end_time,
        location: form.location.trim() || null,
        status: 'pending',
      }

      // 与固定日常时间重叠时给出提醒，但允许用户继续保存
      const conflict = await findRoutineConflict(payload)
      if (conflict) {
        try {
          await ElMessageBox.confirm(
            `该时段与固定日常「${conflict.title}」重叠，仍要保存吗？`,
            '时间冲突提醒',
            {
              confirmButtonText: '仍然保存',
              cancelButtonText: '取消',
              type: 'warning',
            },
          )
        } catch {
          return // 用户取消保存
        }
      }

      await createSchedule(payload)
      ElMessage.success('日程已添加')
    } else {
      const { data } = await createSeries({
        title: form.title.trim(),
        weekday: form.weekday,
        start_time: form.start_time,
        end_time: form.end_time,
        start_date: form.dateRange[0],
        end_date: form.dateRange[1],
      })
      ElMessage.success(`已创建 ${data.created_count} 条周期日程`)
    }

    visible.value = false
    emit('created')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存日程失败'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="添加日程"
    width="520px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-radio-group v-model="mode" class="mode-switch">
      <el-radio-button value="single">单次日程</el-radio-button>
      <el-radio-button value="series">批量周期</el-radio-button>
    </el-radio-group>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="82px" class="schedule-form">
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" maxlength="200" placeholder="如：高等数学 / 团队周会" />
      </el-form-item>

      <el-form-item v-if="mode === 'single'" label="日期" required>
        <el-date-picker
          v-model="form.date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 100%"
        />
      </el-form-item>

      <template v-else>
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

        <el-form-item label="日期范围" required>
          <el-date-picker
            v-model="form.dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
          <p class="field-hint">
            在该日期范围内，每个所选星期几都会生成一条日程，例如第 10~16 周每周三 08:00-10:00。
          </p>
        </el-form-item>
      </template>

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

      <el-form-item v-if="mode === 'single'" label="地点">
        <el-input v-model="form.location" maxlength="200" placeholder="选填，如：三教 302" />
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
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.mode-switch {
  margin-bottom: 18px;
}

.schedule-form {
  margin-top: 4px;
}

.field-hint {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.6;
  color: var(--sg-text-3);
}
</style>
