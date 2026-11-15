import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import http from '@/api/http'

const TOKEN_KEY = 'shiguang_token'
const SCENE_KEY = 'shiguang_scene'
const SCENE_CUSTOM_KEY = 'shiguang_scene_custom'

/**
 * 注册时选择的场景。
 * 说明：后端 users 表暂无 scene 字段（注册接口只接收 username/password/email），
 * 因此场景先保存在前端 localStorage，个人中心从本地读取展示。
 * 后端后续补充字段时，只需把 setScene 里的本地写入替换为接口调用。
 */
export const SCENE_OPTIONS = [
  { value: 'student', label: '大学生', desc: '课表、考试与作息', mark: '大' },
  { value: 'worker', label: '上班族', desc: '会议、通勤与加班', mark: '上' },
  { value: 'freelancer', label: '自由职业', desc: '弹性时间与自我节奏', mark: '自' },
  { value: 'custom', label: '自定义', desc: '按自己的方式安排', mark: '定' },
]

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref(null)
  const scene = ref(localStorage.getItem(SCENE_KEY) || '')
  const customScene = ref(localStorage.getItem(SCENE_CUSTOM_KEY) || '')

  const isLoggedIn = computed(() => Boolean(token.value))

  const sceneLabel = computed(() => {
    if (!scene.value) return '未设置'
    if (scene.value === 'custom') return customScene.value || '自定义'
    return SCENE_OPTIONS.find((item) => item.value === scene.value)?.label || scene.value
  })

  function setToken(value) {
    token.value = value || ''
    if (token.value) localStorage.setItem(TOKEN_KEY, token.value)
    else localStorage.removeItem(TOKEN_KEY)
  }

  function setScene(value, customText = '') {
    scene.value = value || ''
    customScene.value = value === 'custom' ? customText.trim() : ''

    if (scene.value) localStorage.setItem(SCENE_KEY, scene.value)
    else localStorage.removeItem(SCENE_KEY)

    if (customScene.value) localStorage.setItem(SCENE_CUSTOM_KEY, customScene.value)
    else localStorage.removeItem(SCENE_CUSTOM_KEY)
  }

  async function fetchMe() {
    const { data } = await http.get('/api/auth/me')
    user.value = data
    return data
  }

  function clearAuth() {
    setToken('')
    user.value = null
  }

  function logout() {
    clearAuth()
  }

  return {
    token,
    user,
    scene,
    customScene,
    isLoggedIn,
    sceneLabel,
    setToken,
    setScene,
    fetchMe,
    clearAuth,
    logout,
  }
})
