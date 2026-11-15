<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createExam, generateStudyPlan, listExams } from '@/api/exams'
import { getErrorMessage } from '@/utils/error'

const router = useRouter()

const exams = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const planningId = ref(null)
const formRef = ref()

const form = reactive({
  subject: '',
  exam_date: '',
  difficulty: 3,
})

const rules = {
  subject: [{ required: true, message: '请输入科目名称', trigger: 'blur' }],
  exam_date: [{ required: true, message: '请选择考试日期', trigger: 'change' }],
}

async function loadExams() {
  loading.value = true
  try {
    const { data } = await listExams()
    exams.value = Array.isArray(data) ? data : []
  } catch (error) {
    exams.value = []
    ElMessage.error(getErrorMessage(error, '加载考试列表失败'))
  } finally {
    loading.value = false
  }
}

function openDialog() {
  form.subject = ''
  form.exam_date = ''
  form.difficulty = 3
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createExam({
      subject: form.subject.trim(),
      exam_date: form.exam_date,
      difficulty: form.difficulty,
    })
    ElMessage.success('考试已添加')
    dialogVisible.value = false
    await loadExams()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '添加考试失败'))
  } finally {
    submitting.value = false
  }
}

async function planExam(exam) {
  planningId.value = exam.id
  try {
    const { data } = await generateStudyPlan(exam.id)
    const created = data?.created?.length || 0
    const skipped = data?.skipped_days?.length || 0
    await loadExams()

    const skippedText = skipped
      ? `${skipped} 天因无足够空闲时间跳过`
      : '全部安排成功'
    ElMessageBox.alert(
      `成功安排 ${created} 天复习，${skippedText}。可前往周视图查看生成的复习日程。`,
      '复习计划已生成',
      {
        confirmButtonText: '去周视图查看',
        callback: () => router.push('/week'),
      },
    ).catch(() => {})
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '生成复习计划失败'))
  } finally {
    planningId.value = null
  }
}

onMounted(loadExams)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">考试</h1>
        <p class="page-sub">录入考试信息，按难度自动把复习安排进空闲时间</p>
      </div>
      <el-button type="primary" @click="openDialog">添加考试</el-button>
    </div>

    <div class="exam-list" v-loading="loading">
      <article v-for="exam in exams" :key="exam.id" class="panel exam-item">
        <div class="exam-main">
          <div class="exam-head">
            <span class="exam-subject">{{ exam.subject }}</span>
            <el-tag v-if="exam.has_plan" type="success" size="small" effect="light">
              已生成计划
            </el-tag>
            <el-tag v-else type="info" size="small" effect="plain">未生成计划</el-tag>
          </div>

          <div class="exam-meta">
            <span class="exam-date">
              <span class="meta-label">考试日期</span>
              {{ exam.exam_date }}
            </span>
            <span class="exam-difficulty">
              <span class="meta-label">难度</span>
              <el-rate :model-value="exam.difficulty" disabled size="small" />
            </span>
          </div>
        </div>

        <div class="exam-actions">
          <el-button
            type="primary"
            plain
            :loading="planningId === exam.id"
            @click="planExam(exam)"
          >
            生成复习计划
          </el-button>
        </div>
      </article>

      <p v-if="!loading && !exams.length" class="exam-empty">
        还没有考试，点击右上角「添加考试」开始安排复习吧
      </p>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="添加考试"
      width="460px"
      :close-on-click-modal="false"
      append-to-body
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="84px">
        <el-form-item label="科目" prop="subject">
          <el-input v-model="form.subject" maxlength="100" placeholder="如：操作系统" />
        </el-form-item>

        <el-form-item label="考试日期" prop="exam_date">
          <el-date-picker
            v-model="form.exam_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择考试日期"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="难度" prop="difficulty">
          <el-rate v-model="form.difficulty" :max="5" />
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
.exam-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 120px;
}

.exam-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

.exam-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.exam-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.exam-subject {
  font-size: 17px;
  font-weight: 700;
}

.exam-meta {
  display: flex;
  align-items: center;
  gap: 26px;
  flex-wrap: wrap;
  color: var(--sg-text-2);
  font-size: 13px;
}

.exam-date,
.exam-difficulty {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.meta-label {
  color: var(--sg-text-3);
  font-size: 12px;
}

.exam-actions {
  flex: none;
}

.exam-empty {
  margin: 32px 0;
  color: var(--sg-text-3);
  font-size: 13px;
  text-align: center;
}

@media (max-width: 720px) {
  .exam-item {
    flex-direction: column;
    align-items: stretch;
  }

  .exam-actions {
    align-self: flex-end;
  }
}
</style>
