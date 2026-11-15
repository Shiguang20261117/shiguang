<script setup>
import { computed } from 'vue'

import { WEEKDAY_LABELS, formatTime, parseDateStr } from '@/utils/date'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  schedule: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'edit', 'delete'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const dateLabel = computed(() => {
  if (!props.schedule?.date) return ''
  const date = parseDateStr(props.schedule.date)
  return `${props.schedule.date} ${WEEKDAY_LABELS[(date.getDay() + 6) % 7]}`
})

const timeLabel = computed(() => {
  if (!props.schedule) return ''
  return `${formatTime(props.schedule.start_time)} - ${formatTime(props.schedule.end_time)}`
})
</script>

<template>
  <el-dialog v-model="visible" title="日程详情" width="440px" append-to-body>
    <div v-if="schedule" class="detail">
      <div class="detail-head">
        <h3 class="detail-title">{{ schedule.title }}</h3>
        <span v-if="schedule.series_id" class="detail-badge">周期日程</span>
      </div>

      <dl class="detail-list">
        <div class="detail-row">
          <dt>时间</dt>
          <dd>{{ dateLabel }} {{ timeLabel }}</dd>
        </div>
        <div class="detail-row">
          <dt>地点</dt>
          <dd>{{ schedule.location || '未填写' }}</dd>
        </div>
        <div class="detail-row">
          <dt>备注</dt>
          <dd>{{ schedule.description || '无' }}</dd>
        </div>
      </dl>
    </div>

    <template #footer>
      <el-button type="primary" @click="emit('edit')">编辑</el-button>
      <el-button type="danger" plain @click="emit('delete')">删除</el-button>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.detail-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  word-break: break-all;
}

.detail-badge {
  flex: none;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--sg-primary-soft);
  color: var(--sg-primary-strong);
  font-size: 11px;
}

.detail-list {
  display: grid;
  gap: 12px;
  margin: 0;
}

.detail-row {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 10px;
  font-size: 13px;
  line-height: 1.6;
}

.detail-row dt {
  color: var(--sg-text-3);
}

.detail-row dd {
  margin: 0;
  color: var(--sg-text);
  word-break: break-all;
  white-space: pre-wrap;
}
</style>
