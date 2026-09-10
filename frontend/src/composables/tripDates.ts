/** Calendar dates must stay in local time, including east-of-UTC time zones. */
export function tripEndDate(start: string, days: number): string {
  const date = new Date(`${start}T12:00:00`)
  if (Number.isNaN(date.getTime()) || !Number.isInteger(days) || days < 1) {
    throw new Error('请检查出发日期和停留天数')
  }
  date.setDate(date.getDate() + days - 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
