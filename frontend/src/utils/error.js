/** 把后端错误统一转成可展示的中文提示 */
export function getErrorMessage(error, fallback = '请求失败，请稍后重试') {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    // FastAPI 422 校验错误是数组，取第一条的 msg
    const first = detail[0]
    if (first?.msg) return String(first.msg)
  }
  if (error?.code === 'ERR_NETWORK' || error?.message === 'Network Error') {
    return '无法连接后端服务，请确认后端已启动且地址配置正确'
  }
  return fallback
}
