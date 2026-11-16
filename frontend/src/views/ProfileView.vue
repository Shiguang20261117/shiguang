<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useCheckinStore } from '@/stores/checkins'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'
import { formatDateTime } from '@/utils/date'

const router = useRouter()
const auth = useAuthStore()
const checkin = useCheckinStore()

const avatarText = computed(() => (auth.user?.username || '拾').slice(0, 1).toUpperCase())

const MASCOT_META = {
  happy: {
    label: '元气满满',
    text: '完成率很高，继续保持这个节奏！',
    mouth: 'M46 70 Q60 86 74 70',
    color: '#e8834a',
  },
  normal: {
    label: '平稳前行',
    text: '状态还不错，再完成几项就更棒了。',
    mouth: 'M50 74 Q60 80 70 74',
    color: '#d9a441',
  },
  sad: {
    label: '有点低落',
    text: '完成率偏低，陪它一起把日程补上吧。',
    mouth: 'M50 80 Q60 70 70 80',
    color: '#8fa6b8',
  },
}

const completionRate = computed(() => Math.round(Number(checkin.stats.completion_rate) || 0))
const mascotState = computed(() => checkin.stats.mascot || 'sad')
const mascotMeta = computed(() => MASCOT_META[mascotState.value] || MASCOT_META.sad)
const ringColor = computed(() => mascotMeta.value.color)

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
            <svg class="mascot" viewBox="0 0 120 120" role="img" aria-label="Mascot 表情">
              <circle cx="60" cy="60" r="46" fill="#ffe3cc" />
              <circle cx="60" cy="18" r="6" fill="#f0a46b" />
              <path d="M60 12 v-6" stroke="#f0a46b" stroke-width="3" stroke-linecap="round" />

              <template v-if="mascotState === 'happy'">
                <path
                  d="M40 56 Q46 49 52 56"
                  stroke="#8a5a3b"
                  stroke-width="3"
                  fill="none"
                  stroke-linecap="round"
                />
                <path
                  d="M68 56 Q74 49 80 56"
                  stroke="#8a5a3b"
                  stroke-width="3"
                  fill="none"
                  stroke-linecap="round"
                />
              </template>
              <template v-else>
                <circle cx="46" cy="55" r="4" fill="#8a5a3b" />
                <circle cx="74" cy="55" r="4" fill="#8a5a3b" />
              </template>

              <path
                :d="mascotMeta.mouth"
                stroke="#8a5a3b"
                stroke-width="3"
                fill="none"
                stroke-linecap="round"
              />

              <circle cx="38" cy="66" r="6" fill="#ffc6a8" opacity="0.7" />
              <circle cx="82" cy="66" r="6" fill="#ffc6a8" opacity="0.7" />

              <circle
                v-if="mascotState === 'sad'"
                cx="80"
                cy="66"
                r="3.4"
                fill="#a9c9e6"
                opacity="0.9"
              />
            </svg>
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
  top: 8px;
  width: 150px;
  height: 150px;
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

.mascot {
  position: relative;
  width: 108px;
  height: 108px;
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
