<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { loginUser } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref()
const submitting = ref(false)
const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const { data } = await loginUser(form.username.trim(), form.password)
    auth.setToken(data.access_token)
    await auth.fetchMe()

    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/week'
    router.replace(redirect.startsWith('/') ? redirect : '/week')
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '登录失败，请检查用户名和密码'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-intro">
      <div class="intro-inner">
        <div class="logo-badge">拾</div>
        <h1>拾光</h1>
        <p class="intro-slogan">把散落的时间，重新拾起来。</p>
        <ul class="intro-points">
          <li>课程表式周视图，一周安排一眼看清</li>
          <li>三餐与睡眠等固定日常，按星期自动重复</li>
          <li>单次日程与批量周期，一次安排到位</li>
        </ul>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <h2>欢迎回来</h2>
        <p class="auth-sub">登录后继续安排你的一周</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleSubmit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              size="large"
              placeholder="请输入用户名"
              autocomplete="username"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              size="large"
              show-password
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="handleSubmit"
            />
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            class="submit-btn"
            :loading="submitting"
            @click="handleSubmit"
          >
            登录
          </el-button>
        </el-form>

        <p class="auth-switch">
          还没有账号？<RouterLink to="/register">去注册</RouterLink>
        </p>
      </div>
    </section>
  </div>
</template>
