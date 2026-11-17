<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import mascotHappy from '@/assets/mascot-happy.png'
import mascotNormal from '@/assets/mascot-normal.png'
import mascotSad from '@/assets/mascot-sad.png'
import { updateMascotName } from '@/api/auth'
import { useCheckinStore } from '@/stores/checkins'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/date'

const router = useRouter()
const auth = useAuthStore()
const checkin = useCheckinStore()

const avatarText = computed(() => (auth.user?.username || '拾').slice(0, 1).toUpperCase())

const MASCOT_IMAGES = {
  happy: mascotHappy,
  normal: mascotNormal,
  sad: mascotSad,
}

const MASCOT_META = {
  happy: {
    label: '元气满满',
    text: '完成率很高，继续保持这个节奏！',
    color: '#e8834a',
  },
  normal: {
    label: '平稳前行',
    text: '状态还不错，再完成几项就更棒了。',
    color: '#d9a441',
  },
  sad: {
    label: '有点低落',
    text: '完成率偏低，陪它一起把日程补上吧。',
    color: '#8fa6b8',
  },
}

const completionRate = computed(() => Math.round(Number(checkin.stats.completion_rate) || 0))
const mascotState = computed(() => checkin.stats.mascot || 'sad')
const mascotMeta = computed(() => MASCOT_META[mascotState.value] || MASCOT_META.sad)
const ringColor = computed(() => mascotMeta.value.color)
const mascotImage = computed(() => MASCOT_IMAGES[mascotState.value] || MASCOT_IMAGES.sad)
const mascotName = computed(() => auth.user?.mascot_name || '小光')

async function handleRenameMascot() {
  try {
    const { value } = await ElMessageBox.prompt('给 mascot 起个新名字吧', '修改 mascot 名字', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValue: mascotName.value,
      inputPlaceholder: '例如：小光',
      inputValidator: (input) => {
        const name = (input || '').trim()
        if (!name) return '名字不能为空'
        if (name.length > 20) return '名字最多 20 个字符'
        return true
      },
    })
    const { data } = await updateMascotName(value.trim())
    auth.user = data
    ElMessage.success('mascot 名字已更新')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getErrorMessage(error, '改名失败，请稍后重试'))
  }
}

async function loadStats() {
  try {
    await checkin.loadStats(7)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '加载打卡统计失败'))
  }
}

function handleLogout() {
  auth.logout()
  ElMessage.success('已退出登录')
  router.replace('/login')
}

onMounted(loadStats)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">个人中心</h1>
        <p class="page-sub">账号信息、打卡统计与你的陪伴形象</p>
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

      <section class="panel stats-card" v-loading="checkin.loading">
        <div class="stats-head">
          <div>
            <h2 class="stats-title">打卡统计</h2>
            <p class="stats-sub">近 7 天完成率与连续打卡</p>
          </div>
          <span class="mascot-chip" :class="`is-${mascotState}`">{{ mascotMeta.label }}</span>
        </div>

        <div class="stats-main">
          <el-progress
            type="dashboard"
            :percentage="completionRate"
            :width="148"
            :stroke-width="11"
            :color="ringColor"
          >
            <template #default>
              <div class="ring-inner">
                <strong>{{ completionRate }}%</strong>
                <span>近7天完成率</span>
              </div>
            </template>
          </el-progress>

          <div class="mascot-stage">
            <div class="mascot-glow" :class="`is-${mascotState}`"></div>
            <img class="mascot-img" :src="mascotImage" :alt="`mascot ${mascotMeta.label}`" />
            <div class="mascot-name-row">
              <span class="mascot-name">{{ mascotName }}</span>
              <el-button link type="primary" size="small" @click="handleRenameMascot">
                改名
              </el-button>
            </div>
            <p class="mascot-title">{{ mascotMeta.label }}</p>
            <p class="mascot-sub">{{ mascotMeta.text }}</p>
          </div>
        </div>

        <dl class="stats-foot">
          <div class="stat-item">
            <dt>近7天打卡</dt>
            <dd>{{ checkin.stats.total || 0 }}<small>次</small></dd>
          </div>
          <div class="stat-item">
            <dt>连续打卡</dt>
            <dd>{{ checkin.stats.streak_days || 0 }}<small>天</small></dd>
          </div>
          <div class="stat-item">
            <dt>Mascot</dt>
            <dd class="stat-mascot">{{ mascotMeta.label }}</dd>
          </div>
        </dl>
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

.stats-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 26px 30px 24px;
  background:
    radial-gradient(circle at 78% 18%, #fff7ee 0%, #ffffff 58%),
    var(--sg-panel);
}

.stats-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.stats-title {
  margin: 0 0 4px;
  font-size: 18px;
}

.stats-sub {
  margin: 0;
  color: var(--sg-text-3);
  font-size: 12px;
}

.mascot-chip {
  flex: none;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.mascot-chip.is-happy {
  background: #fdeadb;
  color: #c25f27;
}

.mascot-chip.is-normal {
  background: #fdf4dd;
  color: #a0781f;
}

.mascot-chip.is-sad {
  background: #eef2f6;
  color: #62788d;
}

.stats-main {
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: 26px;
  flex-wrap: wrap;
  padding: 10px 0 4px;
}

.ring-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.ring-inner strong {
  font-size: 26px;
  line-height: 1.1;
}

.ring-inner span {
  font-size: 11px;
  color: var(--sg-text-3);
}

.mascot-stage {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 20px;
  border: 1px dashed var(--sg-border);
  border-radius: 20px;
  min-width: 240px;
}

.mascot-glow {
  position: absolute;
  top: 0;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  pointer-events: none;
}

.mascot-glow.is-happy {
  background: radial-gradient(circle, rgba(255, 208, 168, 0.5), transparent 70%);
}

.mascot-glow.is-normal {
  background: radial-gradient(circle, rgba(255, 229, 170, 0.45), transparent 70%);
}

.mascot-glow.is-sad {
  background: radial-gradient(circle, rgba(190, 210, 228, 0.4), transparent 70%);
}

.mascot-img {
  position: relative;
  height: 140px;
  width: auto;
  max-width: 180px;
  object-fit: contain;
  animation: mascot-float 4.2s ease-in-out infinite;
  filter: drop-shadow(0 8px 10px rgba(176, 132, 102, 0.16));
}

@keyframes mascot-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .mascot-img {
    animation: none;
  }
}

.mascot-name-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}

.mascot-name {
  max-width: 150px;
  overflow: hidden;
  font-size: 15px;
  font-weight: 700;
  color: var(--sg-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mascot-name-row :deep(.el-button) {
  font-size: 12px;
}

.mascot-title {
  position: relative;
  margin: 6px 0 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--sg-text-2);
}

.mascot-sub {
  position: relative;
  margin: 0;
  font-size: 12px;
  color: var(--sg-text-3);
  text-align: center;
}

.stats-foot {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 10px 0 0;
  padding-top: 16px;
  border-top: 1px dashed var(--sg-border);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-item dt {
  color: var(--sg-text-3);
  font-size: 12px;
}

.stat-item dd {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--sg-primary-strong);
}

.stat-item dd small {
  margin-left: 3px;
  font-size: 11px;
  font-weight: 500;
  color: var(--sg-text-3);
}

.stat-mascot {
  font-size: 15px !important;
}

@media (max-width: 860px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
</style>
