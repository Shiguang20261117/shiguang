<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { updateSchedule } from '@/api/schedules'
import { updateSeries } from '@/api/series'
import { getErrorMessage } from '@/utils/error'
import { WEEKDAY_LABELS, parseDateStr, timeToMinutes } from '@/utils/date'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  schedule: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isSeries = computed(() => Boolean(props.schedule?.series_id))

const formRef = ref()
const submitting = ref(false)

const form = reactive({
  title: '',
  start_time: '08:00:00',
  end_time: '09:00:00',
  location: '',
  description: '',
  scope: 'single',
})

const rules = {
  title: [{ required: true, message: '请输入日程标题', trigger: 'blur' }],
}

const dateLabel = computed(() => {
  if (!props.schedule?.date) return ''
  const date = parseDateStr(props.schedule.date)
  return `${props.schedule.date} ${WEEKDAY_LABELS[(date.getDay() + 6) % 7]}`
})

watch(
  () => props.modelValue,
  (open) => {
    if (!open || !props.schedule) return

    form.title = props.schedule.title || ''
    form.start_time = props.schedule.start_time || '08:00:00'
    form.end_time = props.schedule.end_time || '09:00:00'
    form.location = props.schedule.location || ''
    form.description = props.schedule.description || ''
    form.scope = 'single'

    nextTick(() => formRef.value?.clearValidate())
  },
)

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (timeToMinutes(form.end_time) <= timeToMinutes(form.start_time)) {
    ElMessage.warning('结束时间必须晚于开始时间')
    return
  }

  const payload = {
    title: form.title.trim(),
    start_time: form.start_time,
    end_time: form.end_time,
    location: form.location.trim() || null,
    description: form.description.trim() || null,
  }

  submitting.value = true
  try {
    if (isSeries.value && form.scope === 'series') {
      await updateSeries(props.schedule.series_id, payload)
      ElMessage.success('已修改整个系列')
    } else {
      await updateSchedule(props.schedule.id, payload)
      ElMessage.success('已保存本次修改')
    }

    visible.value = false
    emit('saved')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存修改失败'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="编辑日程"
    width="520px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="82px">
      <el-form-item label="日期">
        <span class="readonly-text">{{ dateLabel }}</span>
      </el-form-item>

      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" maxlength="200" />
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

      <el-form-item label="地点">
        <el-input v-model="form.location" maxlength="200" placeholder="选填" />
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.description" type="textarea" :rows="2" maxlength="500" placeholder="选填" />
      </el-form-item>

      <el-form-item v-if="isSeries" label="修改范围">
        <el-radio-group v-model="form.scope">
          <el-radio value="single">仅修改本次</el-radio>
          <el-radio value="series">修改整个系列</el-radio>
        </el-radio-group>
        <p v-if="form.scope === 'series'" class="field-hint">
          会同步更新该系列的所有日程，日期保持不变。
        </p>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.readonly-text {
  font-size: 13px;
  color: var(--sg-text-2);
}

.field-hint {
  margin: 6px 0 0;
  font-size: 11px;
  line-height: 1.6;
  color: var(--sg-text-3);
}
</style>
