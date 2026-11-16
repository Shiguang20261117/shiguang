import { ref } from 'vue'
import { defineStore } from 'pinia'

import { getCheckinStats } from '@/api/checkins'

/**
 * 打卡统计共享状态：周视图 / 任务页打卡后调用 loadStats，
 * 个人中心直接读取 stats，切换页面即可看到最新结果，无需刷新。
 */
export const useCheckinStore = defineStore('checkins', () => {
  const days = ref(7)
  const stats = ref({
    days: 7,
    total: 0,
    streak_days: 0,
    completion_rate: 0,
    mascot: 'sad',
  })
  const loading = ref(false)

  async function loadStats(targetDays = days.value) {
    days.value = targetDays
    loading.value = true
    try {
      const { data } = await getCheckinStats(targetDays)
      stats.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  function markChecked() {
    // 打卡后立即拉取最新统计；失败不阻塞打卡本身
    loadStats().catch(() => {})
  }

  return { days, stats, loading, loadStats, markChecked }
})
