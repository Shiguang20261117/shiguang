import http from './http'

export function registerUser(payload) {
  return http.post('/api/auth/register', payload)
}

/**
 * 登录。
 * 需求要求以 form-data（username / password）提交，但当前后端 LoginRequest 是 JSON body，
 * 直接发 application/x-www-form-urlencoded 会被 FastAPI 判为 422（已实测）。
 * 因此先按需求发 form-urlencoded，遇到 422 自动回退 JSON，兼容现有后端。
 */
export async function loginUser(username, password) {
  try {
    return await http.post(
      '/api/auth/login',
      new URLSearchParams({ username, password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } },
    )
  } catch (error) {
    if (error.response?.status === 422) {
      return http.post('/api/auth/login', { username, password })
    }
    throw error
  }
}

export function fetchCurrentUser() {
  return http.get('/api/auth/me')
}
