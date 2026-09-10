/** 金额 / 距离 / 时长的统一格式化，避免各组件各写各的 Math.round */

export function formatCurrency(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `¥${Math.round(value).toLocaleString('zh-CN')}`
}

export function formatNumber(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Math.round(value).toLocaleString('zh-CN')
}

/** 后端返回的门票可能是 "60" / "免费" / "￥80起"，统一转数字展示 */
export function parseTicketPrice(value?: string | number | null): number | null {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return value
  const match = String(value).match(/\d+/)
  return match ? Number(match[0]) : null
}

export function formatTicketPrice(value?: string | number | null): string {
  const price = parseTicketPrice(value)
  if (price === null) return '价格待定'
  return price === 0 ? '免费' : `¥${price}`
}

export function formatDistance(meters?: number | null): string {
  if (meters === null || meters === undefined) return ''
  if (meters < 1000) return `${Math.round(meters)} 米`
  return `${(meters / 1000).toFixed(1)} 公里`
}

/** 分钟 → "7.5 小时" / "45 分钟" */
export function formatMinutes(minutes?: number | null): string {
  if (minutes === null || minutes === undefined) return ''
  if (minutes < 60) return `${Math.round(minutes)} 分钟`
  const hours = minutes / 60
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} 小时`
}

export function formatDateRange(start?: string, end?: string): string {
  if (!start || !end) return ''
  return start === end ? start : `${start} 至 ${end}`
}
