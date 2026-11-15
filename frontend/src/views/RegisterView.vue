<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { loginUser, registerUser } from '@/api/auth'
import { SCENE_OPTIONS, useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref()
const submitting = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  scene: 'student',
  customScene: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度需在 3 - 50 个字符之间', trigger: 'blur' },
  ],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度需在 6 - 128 个字符之间', trigger: 'blur' },
  ],
  confirmPassword: [{ required: true, message: '请再次输入密码', trigger: 'blur' }],
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (!form.scene) {
    ElMessage.warning('请选择你的场景')
    return
  }
  if (form.scene === 'custom' && !form.customScene.trim()) {
    ElMessage.warning('请填写自定义场景名称')
    return
  }
  if (form.password !== form.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  submitting.value = true
  try {
    await registerUser({
      username: form.username.trim(),
      password: form.password,
      email: form.email.trim() || null,
    })
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '注册失败，请稍后重试'))
    submitting.value = false
    return
  }

  // 场景只存在前端（后端暂无该字段），注册成功后立即写入本地
  auth.setScene(form.scene, form.customScene)

  // 注册接口不返回 token，这里用刚注册的账号自动登录
  try {
    const { data } = await loginUser(form.username.trim(), form.password)
    auth.setToken(data.access_token)
    await auth.fetchMe()
    ElMessage.success('注册成功，已为你登录')
    router.replace('/week')
  } catch {
    ElMessage.success('注册成功，请手动登录')
    router.replace('/login')
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
        <p class="intro-slogan">先选一个最像你的场景，拾光会按你的节奏排布时间。</p>
        <ul class="intro-points">
          <li>大学生：课表、考试与作息</li>
          <li>上班族：会议、通勤与加班</li>
          <li>自由职业：弹性时间与自我节奏</li>
        </ul>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card register-card">
        <h2>创建账号</h2>
        <p class="auth-sub">几步完成注册，开始安排你的第一周</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleSubmit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" size="large" placeholder="3 - 50 个字符" autocomplete="username" />
          </el-form-item>

          <el-form-item label="邮箱（选填）" prop="email">
            <el-input v-model="form.email" size="large" placeholder="用于找回账号，可留空" autocomplete="email" />
          </el-form-item>

          <div class="field-grid">
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                type="password"
                size="large"
                show-password
                placeholder="至少 6 位"
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                type="password"
                size="large"
                show-password
                placeholder="再次输入密码"
                autocomplete="new-password"
              />
            </el-form-item>
          </div>

          <el-form-item label="你的场景">
            <div class="scene-grid">
              <button
                v-for="option in SCENE_OPTIONS"
                :key="option.value"
                type="button"
                class="scene-card"
                :class="{ 'is-active': form.scene === option.value }"
                @click="form.scene = option.value"
              >
                <span class="scene-mark">{{ option.mark }}</span>
                <span class="scene-label">{{ option.label }}</span>
                <span class="scene-desc">{{ option.desc }}</span>
              </button>
            </div>
          </el-form-item>

          <el-form-item v-if="form.scene === 'custom'" label="自定义场景">
            <el-input
              v-model="form.customScene"
              size="large"
              maxlength="20"
              placeholder="例如：备考党 / 新手爸妈"
            />
          </el-form-item>

          <p class="auth-notice">
            场景用于个性化展示，当前后端尚未提供场景字段，会先保存在本设备浏览器中。
          </p>

          <el-button
            type="primary"
            size="large"
            class="submit-btn"
            :loading="submitting"
            @click="handleSubmit"
          >
            注册并登录
          </el-button>
        </el-form>

        <p class="auth-switch">
          已有账号？<RouterLink to="/login">去登录</RouterLink>
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.register-card {
  max-width: 460px;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.scene-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  width: 100%;
}

.scene-card {
  display: grid;
  grid-template-columns: 32px 1fr;
  grid-template-rows: auto auto;
  align-items: center;
  gap: 0 10px;
  padding: 10px 12px;
  border: 1px solid var(--sg-border);
  border-radius: 12px;
  background: #fffdfa;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: border-color 0.16s ease, background-color 0.16s ease, box-shadow 0.16s ease;
}

.scene-card:hover {
  border-color: #f2b98f;
  background: #fff8f1;
}

.scene-card.is-active {
  border-color: var(--sg-primary);
  background: var(--sg-primary-soft);
  box-shadow: 0 4px 12px rgba(232, 131, 74, 0.14);
}

.scene-mark {
  grid-row: 1 / span 2;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f6ede3;
  color: var(--sg-primary-strong);
  font-size: 14px;
  font-weight: 700;
}

.scene-card.is-active .scene-mark {
  background: #fff;
}

.scene-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--sg-text);
}

.scene-desc {
  font-size: 11px;
  color: var(--sg-text-3);
  line-height: 1.4;
}

@media (max-width: 480px) {
  .field-grid,
  .scene-grid {
    grid-template-columns: 1fr;
  }
}
</style>
