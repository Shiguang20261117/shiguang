<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/date'

const router = useRouter()
const auth = useAuthStore()

const avatarText = computed(() => (auth.user?.username || '拾').slice(0, 1).toUpperCase())

function handleLogout() {
  auth.logout()
  ElMessage.success('已退出登录')
  router.replace('/login')
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">个人中心</h1>
        <p class="page-sub">账号信息、当前场景与你的陪伴形象</p>
      </div>
      <el-button @click="handleLogout">退出登录</el-button>
    </div>

    <div class="profile-grid">
      <section class="panel profile-card">
        <div class="avatar">{{ avatarText }}</div>
        <h2 class="profile-name">{{ auth.user?.username || '未登录' }}</h2>
        <span class="scene-chip">{{ auth.sceneLabel }}</span>

        <dl class="profile-meta">
          <div class="meta-row">
            <dt>邮箱</dt>
            <dd>{{ auth.user?.email || '未填写' }}</dd>
          </div>
          <div class="meta-row">
            <dt>用户 ID</dt>
            <dd>{{ auth.user?.id ?? '-' }}</dd>
          </div>
          <div class="meta-row">
            <dt>注册时间</dt>
            <dd>{{ formatDateTime(auth.user?.created_at) }}</dd>
          </div>
        </dl>

        <p class="scene-note">
          场景在注册时选择，目前保存在本地浏览器；后端暂未提供 scene 字段。
        </p>
      </section>

      <section class="panel mascot-card">
        <div class="mascot-stage">
          <div class="mascot-glow"></div>
          <svg class="mascot" viewBox="0 0 120 120" role="img" aria-label="Mascot 占位形象">
            <circle cx="60" cy="60" r="46" fill="#ffe3cc" />
            <circle cx="60" cy="18" r="6" fill="#f0a46b" />
            <path d="M60 12 v-6" stroke="#f0a46b" stroke-width="3" stroke-linecap="round" />
            <circle cx="46" cy="55" r="4" fill="#8a5a3b" />
            <circle cx="74" cy="55" r="4" fill="#8a5a3b" />
            <path
              d="M50 72 Q60 80 70 72"
              stroke="#8a5a3b"
              stroke-width="3"
              fill="none"
              stroke-linecap="round"
            />
            <circle cx="38" cy="66" r="6" fill="#ffc6a8" opacity="0.7" />
            <circle cx="82" cy="66" r="6" fill="#ffc6a8" opacity="0.7" />
          </svg>
          <p class="mascot-title">Mascot 占位区域</p>
          <p class="mascot-sub">后续在这里接入拾光伙伴形象与成长状态</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: minmax(280px, 380px) 1fr;
  gap: 18px;
  align-items: stretch;
}

.profile-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 28px;
  text-align: center;
}

.avatar {
  display: grid;
  place-items: center;
  width: 76px;
  height: 76px;
  border-radius: 26px;
  background: linear-gradient(145deg, #ffcaa0, #e8834a);
  color: #fff;
  font-size: 30px;
  font-weight: 700;
  box-shadow: 0 10px 24px rgba(232, 131, 74, 0.28);
}

.profile-name {
  margin: 16px 0 8px;
  font-size: 20px;
}

.scene-chip {
  padding: 4px 12px;
  border-radius: 999px;
  background: var(--sg-primary-soft);
  color: var(--sg-primary-strong);
  font-size: 12px;
  font-weight: 600;
}

.profile-meta {
  width: 100%;
  margin: 26px 0 0;
  padding-top: 18px;
  border-top: 1px dashed var(--sg-border);
  display: grid;
  gap: 12px;
  text-align: left;
}

.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.meta-row dt {
  color: var(--sg-text-3);
}

.meta-row dd {
  margin: 0;
  color: var(--sg-text);
  word-break: break-all;
}

.scene-note {
  margin: 22px 0 0;
  font-size: 11px;
  line-height: 1.7;
  color: var(--sg-text-3);
}

.mascot-card {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(circle at 50% 40%, #fff7ee 0%, #ffffff 62%),
    var(--sg-panel);
}

.mascot-stage {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px;
  border: 1px dashed var(--sg-border);
  border-radius: 20px;
  width: 100%;
  max-width: 420px;
}

.mascot-glow {
  position: absolute;
  top: 40px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 208, 168, 0.45), transparent 70%);
  pointer-events: none;
}

.mascot {
  position: relative;
  width: 132px;
  height: 132px;
}

.mascot-title {
  position: relative;
  margin: 10px 0 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--sg-text-2);
}

.mascot-sub {
  position: relative;
  margin: 0;
  font-size: 12px;
  color: var(--sg-text-3);
}

@media (max-width: 860px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
