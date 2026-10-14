<template>
  <div class="reservation-notice" @click.stop>
    <strong>{{ label }}</strong>
    <span v-if="info.advance_days != null && info.status === 'required'"> · 攻略提及提前 {{ info.advance_days }} 天</span>
    <details v-if="info.tips || info.evidence || info.channel || info.source_url">
      <summary>查看预约线索</summary>
      <p v-if="info.tips">{{ info.tips }}</p>
      <p v-if="info.channel">预约渠道：{{ info.channel }}</p>
      <p v-if="info.release_time">攻略提及放票时间：{{ info.release_time }}（北京时间）</p>
      <blockquote v-if="info.evidence">{{ info.evidence }}</blockquote>
      <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener noreferrer">{{ info.source_title || '查看攻略来源' }}</a>
      <p v-else>来源：{{ info.source_title || '未提供可追溯链接' }}</p>
      <p v-if="info.captured_at">采集时间：{{ info.captured_at.slice(0, 10) }}</p>
      <p>攻略线索未经官方核验，出行前请确认规则与余票。</p>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReservationFields, ReservationInfo } from '@/types/reservation'
const props = defineProps<{ attraction: ReservationFields }>()
const info = computed<ReservationInfo>(() => props.attraction.reservation || {
  status: props.attraction.reservation_required === true ? 'required' : 'unknown',
  tips: props.attraction.reservation_tips,
})
const label = computed(() => ({ required: '需关注预约', not_required: '攻略称无需预约 · 待核实', unknown: '预约信息待核实', conflicting: '预约规则有冲突 · 请核实' }[info.value.status]))
const sourceUrl = computed(() => {
  try { const url = new URL(info.value.source_url || ''); return ['https:', 'http:'].includes(url.protocol) && !url.username ? url.href : '' }
  catch { return '' }
})
</script>

<style scoped>
.reservation-notice { margin-top: 10px; padding: 9px 12px; background: var(--color-primary-soft, #edf5f1); border-radius: 8px; font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
strong { font-weight: 600; } summary { cursor: pointer; margin-top: 6px; } p { margin: 6px 0; } blockquote { margin: 8px 0; padding-left: 10px; border-left: 2px solid var(--color-primary, #26715d); } a { color: var(--color-primary, #26715d); }
</style>
