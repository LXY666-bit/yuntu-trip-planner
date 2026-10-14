<template>
  <div class="draft-page">
    <header class="draft-hero">
      <span class="eyebrow">MAKE IT YOURS</span><h1>{{ draft?.city || '加载中...' }}<span v-if="draft"> · 旅程草稿</span></h1><p class="draft-subtitle">好行程，由你决定。调整景点顺序，安排每一天的美好。</p>
      <div class="meta" v-if="draft">
        {{ draft.request.start_date }} 至 {{ draft.request.end_date }} ·
        {{ draft.request.travel_days }} 天
      </div>
    </header>

    <a-spin v-if="loading" tip="加载草稿中..." />

    <div v-else-if="loadError" class="draft-error">
      <a-result status="warning" title="草稿加载失败" :sub-title="loadError">
        <template #extra>
          <a-button type="primary" @click="loadDraft">重试</a-button>
          <a-button @click="router.push('/')">返回首页</a-button>
        </template>
      </a-result>
    </div>

    <main v-else-if="draft" class="draft-content">
      <PlanningAssistant :draft="draft" :disabled="finalizing || reservationBusy || Object.keys(dayBusy).length > 0"
                         @busy="assistantBusy = $event" @changed="refreshDraft"
                         @constraints-saved="draft = { ...draft, request: $event }" />
      <ReservationChecklist kind="draft" :id="draft.draft_id" :revision="draft"
                            :disabled="finalizing || assistantBusy || Object.keys(dayBusy).length > 0"
                            @busy="reservationBusy = $event" @changed="refreshDraft" />
      <div class="days-container">
        <DayCard
          v-for="(ctx, idx) in draft.days"
          :key="idx"
          :context="ctx"
          :detail="draft.days_detail[idx] || null"
          :is-default-expanded="idx === 0"
          :busy="finalizing ? '定稿中' : assistantBusy || reservationBusy ? '行程助手处理中' : dayBusy[idx] || ''"
          @assemble="onAssemble(idx, $event)"
          @recompute="onRecompute(idx, $event)"
          @ai-rearrange="onAIRearrange(idx, $event)"
          @rewrite-narrative="onRewriteNarrative(idx)"
        />
      </div>

      <div class="finalize-bar"><div><strong>最后确认，准备出发</strong><p>保存后可在「我的行程」中查看与导出。</p></div>
        <a-button type="primary" size="large" :loading="finalizing" :disabled="assistantBusy || reservationBusy || Object.keys(dayBusy).length > 0"
                  @click="onFinalize">
          定稿并保存
        </a-button>
      </div>
    </main>

    <a-empty v-else description="草稿不存在或已过期" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  getDraft, assembleDay, recomputeDay, aiRearrangeDay,
  rewriteNarrative, finalizeDraftStream,
} from '@/services/api'
import type { FinalizeStreamEvent } from '@/services/api'
import { useAbortController } from '@/composables/useSSEStream'
import type { TripDraftPayload, DayEditRequest } from '@/types'
import DayCard from '@/components/draft/DayCard.vue'
import PlanningAssistant from '@/components/draft/PlanningAssistant.vue'
import ReservationChecklist from '@/components/ReservationChecklist.vue'
const reservationBusy = ref(false)

const route = useRoute()
const router = useRouter()
const draftId = computed(() => route.params.id as string)

// 离开页面时取消未完成的定稿流
const { signal: finalizeSignal } = useAbortController()

const draft = ref<TripDraftPayload | null>(null)
const loading = ref(true)
const loadError = ref('')
const finalizing = ref(false)
const assistantBusy = ref(false)

async function refreshDraft() {
  try { draft.value = await getDraft(draftId.value) }
  catch (e: any) { message.error(e?.message || '刷新草稿失败，请重试') }
}

const dayBusy = reactive<Record<number, string>>({})

async function withDayBusy<T>(
  idx: number,
  label: string,
  fn: () => Promise<T>,
): Promise<T | undefined> {
  if (dayBusy[idx] || finalizing.value || assistantBusy.value) return
  dayBusy[idx] = label
  try {
    const result = await fn()
    message.success(`已更新第 ${idx + 1} 天`)
    return result
  } catch (e: any) {
    console.error(`第 ${idx + 1} 天操作失败:`, e)
    message.error(e?.message || `第 ${idx + 1} 天操作失败`)
  } finally {
    delete dayBusy[idx]
  }
}

async function loadDraft() {
  loading.value = true
  loadError.value = ''
  try {
    draft.value = await getDraft(draftId.value)
    // 自动展开第 1 天
    if (draft.value && !draft.value.days_detail?.[0]) {
      await onAssemble(0, {})
    }
  } catch (e: any) {
    console.error('加载草稿失败:', e)
    draft.value = null
    loadError.value = e?.message || '草稿不存在或已过期'
  } finally {
    loading.value = false
  }
}

function applyDayDetail(idx: number, dayDetail: any) {
  if (!draft.value) return
  const days = [...(draft.value.days_detail || [])]
  days[idx] = dayDetail
  draft.value = { ...draft.value, days_detail: days }
}

async function onAssemble(idx: number, body: DayEditRequest) {
  await withDayBusy(idx, '装配中', async () => {
    const resp = await assembleDay(draftId.value, idx, body)
    applyDayDetail(idx, resp.day_detail)
  })
}

async function onRecompute(idx: number, body: DayEditRequest) {
  await withDayBusy(idx, '重算中', async () => {
    const resp = await recomputeDay(draftId.value, idx, body)
    applyDayDetail(idx, resp.day_detail)
  })
}

async function onAIRearrange(idx: number, hint: string) {
  await withDayBusy(idx, 'AI 重排中', async () => {
    const resp = await aiRearrangeDay(draftId.value, idx, hint)
    applyDayDetail(idx, resp.day_detail)
  })
}

async function onRewriteNarrative(idx: number) {
  await withDayBusy(idx, '重写叙述中', async () => {
    const resp = await rewriteNarrative(draftId.value, idx)
    applyDayDetail(idx, resp.day_detail)
  })
}

async function onFinalize() {
  if (finalizing.value || assistantBusy.value || Object.keys(dayBusy).length > 0) return
  finalizing.value = true
  try {
    await finalizeDraftStream(
      draftId.value,
      (event: FinalizeStreamEvent) => {
        if (event.type === 'complete' && event.trip_id) {
          message.success('定稿成功')
          router.replace(`/trip/${event.trip_id}`)
        } else if (event.type === 'progress') {
          message.loading(event.message || '正在定稿...', 1)
        } else if (event.type === 'error') {
          message.error(event.message || '定稿失败')
        }
      },
      { signal: finalizeSignal }
    )
  } catch (e: any) {
    console.error('定稿失败:', e)
    message.error(e?.message || '定稿失败')
  } finally {
    finalizing.value = false
  }
}

onMounted(loadDraft)
</script>

<style scoped>
.draft-page { max-width: 1120px; margin: auto; padding: 104px 32px 32px; }
.draft-hero { margin-bottom: 30px; }
.draft-hero h1 { font-size: 30px; margin: 12px 0; font-weight: 600; }
.draft-hero h1 span { font-size: 24px; font-weight: 400; }
.draft-subtitle { font-size: 14px; color: var(--color-text-secondary); }
.meta { color: var(--color-text-tertiary); margin-top: 14px; font-size: 12px; }
.days-container { display: flex; flex-direction: column; gap: 20px; }
.draft-error { padding: 40px 0; }
.finalize-bar { position: sticky; bottom: 12px; display: flex; align-items: center; justify-content: space-between; gap: 20px; background: var(--color-glass-bg); backdrop-filter: blur(20px); padding: 18px 24px; margin-top: 28px; border: 1px solid var(--color-border); border-radius: 14px; z-index: 4; }
.finalize-bar strong { font-size: 14px; font-weight: 550; }
.finalize-bar p { font-size: 12px; color: var(--color-text-tertiary); margin: 4px 0 0; }
@media (max-width: 600px) { .draft-page { padding: 88px 16px 24px; } .draft-hero h1 { font-size: 25px; } .draft-hero h1 span { font-size: 20px; } .finalize-bar { padding: 14px; gap: 10px; } .finalize-bar p { display: none; } }
</style>
