<script setup>
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function handleLogout() {
  auth.logout()
  ElMessage.success('已退出登录')
  router.replace('/login')
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-mark">拾</span>
          <div class="brand-text">
            <span class="brand-name">拾光</span>
            <span class="brand-sub">把时间拾起来</span>
          </div>
        </div>

        <nav class="app-nav">
          <RouterLink to="/week" class="nav-item">周视图</RouterLink>
          <RouterLink to="/routines" class="nav-item">固定日常</RouterLink>
          <RouterLink to="/profile" class="nav-item">个人中心</RouterLink>
        </nav>

        <div class="header-right">
          <span class="header-user">{{ auth.user?.username || '你好' }}</span>
          <el-button text @click="handleLogout">退出</el-button>
        </div>
      </div>
    </header>

    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 252, 248, 0.9);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--sg-border);
}

.header-inner {
  display: flex;
  align-items: center;
  gap: 28px;
  width: 100%;
  max-width: 1240px;
  margin: 0 auto;
  padding: 12px 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(140deg, #f7b183, #e8834a);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 6px 14px rgba(232, 131, 74, 0.25);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
}

.brand-sub {
  font-size: 11px;
  color: var(--sg-text-3);
}

.app-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.nav-item {
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 14px;
  color: var(--sg-text-2);
  text-decoration: none;
  transition: background-color 0.16s ease, color 0.16s ease;
}

.nav-item:hover {
  background: var(--sg-primary-soft);
  color: var(--sg-primary-strong);
  text-decoration: none;
}

.nav-item.router-link-active {
  background: var(--sg-primary-soft);
  color: var(--sg-primary-strong);
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: none;
}

.header-user {
  font-size: 13px;
  color: var(--sg-text-2);
}

.app-main {
  min-height: calc(100vh - 62px);
}

@media (max-width: 720px) {
  .header-inner {
    flex-wrap: wrap;
    gap: 10px 16px;
    padding: 10px 16px;
  }

  .brand-sub,
  .header-user {
    display: none;
  }

  .app-nav {
    order: 3;
    width: 100%;
    overflow-x: auto;
  }

  .header-right {
    margin-left: auto;
  }
}
</style>
