<template>
  <section class="reservation-checklist" aria-label="预约待办">
    <header><div><h2>预约待办 <small>{{ pending }} 项待处理</small></h2>
      <p>以北京时间计算。攻略中的规则需要核实，“已到关注时间”不代表还有余票。</p></div>
      <a-button :disabled="locked || !exportCount" @click="download">导出日历（{{ exportCount }}）</a-button>
    </header>
    <p>日历只包含有明确提前天数、尚未到提醒时间且未预约的景点；未提供放票时刻时默认 09:00 提醒。导入日历并开启通知后生效，行程变更后需重新导入并清理旧提醒。</p>
    <p v-if="loading" role="status">正在读取预约清单…</p>
    <p v-if="error" role="alert" class="error">{{ error }} <button @click="load">重试</button></p>
    <div v-for="task in tasks" :key="task.id" class="reservation-task">
      <div class="task-title"><strong>{{ task.name }}</strong><span>{{ task.visit_date }} · 第 {{ task.day_index + 1 }} 天</span></div>
      <p :class="{ urgent: task.status === 'due' || task.status === 'conflicting' }">{{ labels[task.status] }}</p>
      <p v-if="task.remind_at">建议关注：{{ formatTime(task.remind_at) }}{{ task.default_reminder_time ? '（默认提醒时刻，不是放票时间）' : '' }}</p>
      <ReservationNotice :attraction="{ reservation: task.reservation }" />
      <a-button v-if="task.status !== 'past_visit' && task.status !== 'not_required'" :disabled="locked" @click="toggle(task)">
        {{ task.booked ? '撤销已预约标记' : '我已完成该日期的预约' }}
      </a-button>
    </div>
    <p v-if="!loading && !error && !tasks.length">当前没有景点预约待办。</p>
    <p v-if="tasks.length">“已预约”仅记录你的确认，不代订门票；更换景点或游览日期后需重新确认。</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ReservationNotice from './ReservationNotice.vue'
import type { ReservationTask } from '@/types/reservation'
import { getReservationTasks, markReservationBooked, exportReservationCalendar } from '@/services/api'
const props = defineProps<{ kind: 'draft' | 'trip'; id: string | number; revision?: unknown; disabled?: boolean }>()
const emit = defineEmits<{ changed: []; busy: [value: boolean] }>()
const tasks = ref<ReservationTask[]>([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')
let generation = 0
let refreshTimer: ReturnType<typeof setInterval> | undefined
const locked = computed(() => props.disabled || busy.value || loading.value)
const pending = computed(() => tasks.value.filter(t => !['booked', 'not_required', 'past_visit'].includes(t.status)).length)
const exportCount = computed(() => tasks.value.filter(t => t.calendar_eligible).length)
const labels: Record<ReservationTask['status'], string> = {
  booked: '已预约（用户确认）', past_visit: '游览日期已过', unknown: '待核实是否需要预约',
  conflicting: '来源规则有冲突，请先核实', not_required: '攻略称无需预约，出行前仍需核实',
  needs_check: '需要关注预约，提前天数未知', upcoming: '尚未到攻略建议的关注时间', due: '已到预约关注时间，请尽快核实并预约',
}
function formatTime(value: string) { return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short', hour12: false }).format(new Date(value)) }
async function load() {
  const current = ++generation
  loading.value = true
  try { const result = await getReservationTasks(props.kind, props.id); if (current === generation) { tasks.value = result.tasks; error.value = '' } }
  catch (e: any) { if (current === generation) error.value = e?.message || '预约清单加载失败' }
  finally { if (current === generation) loading.value = false }
}
async function toggle(task: ReservationTask) {
  if (locked.value) return
  busy.value = true; emit('busy', true); error.value = ''
  try { tasks.value = (await markReservationBooked(props.kind, props.id, task.id, !task.booked)).tasks; emit('changed') }
  catch (e: any) { error.value = e?.message || '预约状态保存失败' }
  finally { busy.value = false; emit('busy', false) }
}
async function download() {
  if (locked.value) return
  busy.value = true; error.value = ''
  try {
    const blob = await exportReservationCalendar(props.kind, props.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = '云途-预约提醒.ics'; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e: any) { error.value = e?.message || '日历导出失败' }
  finally { busy.value = false }
}
watch(() => [props.kind, props.id, props.revision], () => { void load() }, { immediate: true })
// Refresh time-dependent status while this page remains open; no background push service.
refreshTimer = setInterval(() => { if (!locked.value && document.visibilityState === 'visible') void load() }, 60000)
onBeforeUnmount(() => { generation++; clearInterval(refreshTimer); emit('busy', false) })
</script>

<style scoped>
.reservation-checklist { padding: 24px; margin: 24px 0; border: 1px solid var(--color-border, #ddd); border-radius: 14px; background: var(--color-bg-card, white); }
header, .task-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
h2 { font-size: 20px; margin: 0; } small, .task-title span { font-size: 12px; font-weight: normal; color: var(--color-text-secondary, #666); }
p { font-size: 13px; line-height: 1.7; } .reservation-task { border-top: 1px solid var(--color-border, #ddd); padding: 16px 0; }
.reservation-task button { margin-top: 10px; } .urgent, .error { color: #b45309; }
@media(max-width: 600px) { .reservation-checklist { padding: 16px; } }
</style>
