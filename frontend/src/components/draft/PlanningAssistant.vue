<template>
  <section class="planning-assistant" aria-label="行程检查与对话修改">
    <div class="assistant-heading">
      <div><h2>让行程更合心意</h2><p>检查行程是否安排得下，或用一句话修改某一天。酒店和其他日期保持不变。</p></div>
      <a-button :loading="busy === 'checking'" :disabled="disabled || !!busy" @click="check">检查行程</a-button>
    </div>

    <details class="constraints">
      <summary>设置必去景点、时间和预算</summary>
      <div class="constraint-fields">
        <label>必去景点（用逗号分隔，名称与景点卡片一致）<input v-model="mustVisit" :disabled="locked" placeholder="例如：上海博物馆" /></label>
        <label>每日最多安排（分钟）<input v-model.number="maxMinutes" type="number" min="60" max="960" :disabled="locked" /></label>
        <label>最晚结束时间<input v-model="endTime" type="time" :disabled="locked" /></label>
        <label>整趟预算（元，留空不限）<input v-model="budget" type="number" min="0" :disabled="locked" /></label>
      </div>
      <a-button :disabled="locked" @click="saveConstraints">保存要求并检查</a-button>
    </details>

    <div v-if="report" class="report" aria-live="polite">
      <strong>{{ report.valid ? '未发现已知硬约束冲突' : '有需要调整的行程冲突' }}</strong>
      <p>费用{{ report.pricing_status === 'incomplete' ? '已知部分小计' : '估算' }}：¥{{ report.total_cost }}。
        交通按每人每天 ¥50 估算，住宿按两人一间、末日不住宿估算。未知费用和开放时间仍需确认。</p>
      <ul v-if="report.violations.length">
        <li v-for="(item, index) in report.violations" :key="index" :class="item.severity">
          <span>{{ item.severity === 'error' ? '需调整' : '待核实' }}</span> {{ item.message }}
        </li>
      </ul>
      <a-button v-if="!report.valid" :disabled="locked" @click="propose(true)">尝试修复冲突（最多两轮）</a-button>
    </div>

    <div class="edit-box">
      <label for="edit-instruction">告诉我你想怎么调整</label>
      <textarea id="edit-instruction" v-model="instruction" :disabled="locked" maxlength="1500" rows="3"
        placeholder="例如：第二天下雨，换成室内景点，酒店和第三天保持不变" />
      <div class="edit-actions">
        <select v-model.number="dayIndex" aria-label="修改日期" :disabled="locked">
          <option :value="-1">从文字识别日期</option>
          <option v-for="(_, i) in draft.days" :key="i" :value="i">第 {{ i + 1 }} 天</option>
        </select>
        <a-button type="primary" :disabled="locked || !instruction.trim()" @click="propose(false)">生成修改建议</a-button>
        <a-button v-if="busy === 'proposing'" @click="cancelGeneration">停止生成</a-button>
      </div>
      <p v-if="busy" role="status">{{ statusText }}</p>
    </div>

    <div v-if="proposal" class="proposal" aria-live="polite">
      <h3>{{ proposal.status === 'pending' ? '请确认这份修改' : '本次建议' }}</h3>
      <p>{{ proposal.message }}</p>
      <div v-for="(after, index) in proposal.after" :key="index" class="day-diff">
        <strong>第 {{ Number(index) + 1 }} 天</strong>
        <div class="diff-columns">
          <div><small>修改前</small><p>{{ proposal.before[index]?.attractions.map(a => a.name).join(' → ') }}</p>
            <p>开始：{{ proposal.before[index]?.day_start_time || '08:00' }}</p></div>
          <div><small>修改后</small><p>{{ after.attractions.map(a => a.name).join(' → ') }}</p>
            <p>开始：{{ after.day_start_time || '08:00' }}</p></div>
        </div>
      </div>
      <p>整趟费用估算：¥{{ proposal.validation_before.total_cost }} → ¥{{ proposal.validation_after.total_cost }}</p>
      <ul><li v-for="(issue, i) in proposal.validation_after.violations" :key="i">{{ issue.message }}</li></ul>
      <template v-if="proposal.status === 'pending'">
        <label class="remember"><input v-model="remember" type="checkbox" :disabled="locked" />记住这次选择的景点类型，用于以后推荐</label>
        <div class="edit-actions">
          <a-button type="primary" :disabled="locked" @click="confirm">确认应用修改</a-button>
          <a-button :disabled="locked" @click="discard">保留原行程</a-button>
        </div>
      </template>
    </div>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { TripDraftPayload } from '@/types'
import type { EditProposal, ValidationReport, PlanningConstraints } from '@/types/planning'
import { validateDraft, savePlanningConstraints, proposeDraftEdit, confirmDraftEdit, cancelDraftEdit } from '@/services/api'

const props = defineProps<{ draft: TripDraftPayload; disabled?: boolean }>()
const emit = defineEmits<{ changed: []; constraintsSaved: [request: TripDraftPayload['request']]; busy: [value: boolean] }>()
const busy = ref('')
const locked = computed(() => props.disabled || !!busy.value || props.draft.status === 'finalized')
const statusText = computed(() => ({ checking: '正在检查行程…', proposing: '正在检索候选、计算路线并校验，原行程尚未修改…', applying: '正在应用已确认的修改…', saving: '正在保存要求…' }[busy.value] || '正在处理…'))
const report = ref<ValidationReport | null>(null)
const proposal = ref<EditProposal | null>(null)
const instruction = ref('')
const dayIndex = ref(-1)
const error = ref('')
const remember = ref(false)
const mustVisit = ref('')
const maxMinutes = ref(600)
const endTime = ref('22:00')
const budget = ref('')
let controller: AbortController | undefined
watch(() => props.draft, draft => {
  const constraints = draft.request as typeof draft.request & Partial<PlanningConstraints>
  mustVisit.value = constraints.must_visit?.join('，') || ''
  maxMinutes.value = constraints.max_day_minutes || 600
  endTime.value = constraints.day_end_time || '22:00'
  budget.value = constraints.budget == null ? '' : String(constraints.budget)
  report.value = null
  proposal.value = null
}, { immediate: true })
watch(busy, value => emit('busy', !!value), { flush: 'sync' })
onBeforeUnmount(() => { controller?.abort(); emit('busy', false) })

async function run(label: string, operation: () => Promise<void>) {
  if (locked.value) return
  busy.value = label
  error.value = ''
  try { await operation() } catch (e: any) { error.value = e?.message || '操作失败，请重试' }
  finally { busy.value = '' }
}
async function check() { await run('checking', async () => { report.value = await validateDraft(props.draft.draft_id) }) }
async function saveConstraints() {
  await run('saving', async () => {
    if (!Number.isFinite(maxMinutes.value) || maxMinutes.value < 60 || maxMinutes.value > 960) throw new Error('每日时长应为60至960分钟')
    const request = await savePlanningConstraints(props.draft.draft_id, {
      must_visit: mustVisit.value.split(/[,，、]/).map(x => x.trim()).filter(Boolean),
      max_day_minutes: maxMinutes.value, day_end_time: endTime.value,
      budget: budget.value === '' ? null : Number(budget.value),
    })
    emit('constraintsSaved', request)
    proposal.value = null
    report.value = await validateDraft(props.draft.draft_id)
  })
}
async function propose(repair: boolean) {
  await run('proposing', async () => {
    proposal.value = null
    controller = new AbortController()
    proposal.value = await proposeDraftEdit(props.draft.draft_id, {
      message: instruction.value, repair,
      ...(dayIndex.value >= 0 ? { day_index: dayIndex.value } : {}),
    }, controller.signal)
    report.value = proposal.value.validation_after
  })
}
function cancelGeneration() { controller?.abort() }
async function confirm() {
  if (!proposal.value) return
  await run('applying', async () => {
    proposal.value = await confirmDraftEdit(props.draft.draft_id, proposal.value!.proposal_id, remember.value)
    emit('changed')
  })
}
async function discard() {
  if (!proposal.value) return
  await run('saving', async () => {
    await cancelDraftEdit(props.draft.draft_id, proposal.value!.proposal_id)
    proposal.value = null
    report.value = await validateDraft(props.draft.draft_id)
  })
}
</script>

<style scoped>
.planning-assistant { padding: 24px; margin-bottom: 24px; border: 1px solid var(--color-border, #ddd); border-radius: 14px; background: var(--color-bg-card, #fff); color: var(--color-text-primary, #222); }
.assistant-heading, .edit-actions { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
h2 { margin: 0; font-size: 20px; } p { line-height: 1.7; } .assistant-heading p, small { color: var(--color-text-secondary, #666); }
.constraints { padding: 16px 0; border-block: 1px solid var(--color-border, #ddd); margin: 16px 0; } summary { cursor: pointer; }
.constraint-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }
label { display: block; font-size: 13px; } input:not([type=checkbox]), textarea, select { display: block; width: 100%; box-sizing: border-box; margin-top: 7px; padding: 9px 12px; border: 1px solid var(--color-border, #ddd); border-radius: 8px; background: transparent; color: inherit; font: inherit; }
textarea { resize: vertical; } select { width: auto; margin: 0; } .edit-actions { justify-content: flex-start; margin-top: 12px; }
.report, .proposal { padding: 16px; background: var(--color-bg-secondary, #f6f7f9); border-radius: 10px; margin-block: 16px; }
ul { padding-left: 22px; max-height: 240px; overflow: auto; } li { line-height: 1.7; margin-block: 5px; } li span { font-weight: 600; }
.error, .error-message { color: #b42318; } .warning { color: #8a5a12; } .day-diff { border-top: 1px solid var(--color-border, #ddd); padding-top: 12px; }
.diff-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; } .remember { margin: 16px 0; }
@media (max-width: 600px) { .constraint-fields, .diff-columns { grid-template-columns: 1fr; } .planning-assistant { padding: 16px; } }
</style>
