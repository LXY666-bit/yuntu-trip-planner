<template>
  <div class="landing-page">
    <aside class="travel-intro">
      <div class="eyebrow"><span class="intro-dot"></span> YOUR NEXT CHAPTER</div>
      <h1>把向往的远方，<br>变成下一站。</h1>
      <p class="intro-description">告诉云途你想去的地方。一起发现值得停留的风景，安排刚刚好的旅行节奏。</p>
      <div class="intro-features"><span>精选目的地</span><span>个性化推荐</span><span>灵活调整</span></div>
      <div class="journey-preview" aria-label="旅行规划流程示意">
        <div class="preview-heading"><span>一段旅程，从这里开始</span><span class="preview-stamp">YUNTU / 旅途手记</span></div>
        <svg class="journey-drawing" viewBox="0 0 430 210" role="img" aria-label="从城市漫步到山野日落的旅行路线">
          <path d="M0 165 Q80 115 155 160 T300 140 T430 150 L430 210 L0 210Z" fill="currentColor" opacity=".05"/>
          <path d="M270 125 L320 40 L370 125 M302 70 L320 82 L335 65" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"/>
          <circle cx="370" cy="44" r="14" fill="#d89c72" opacity=".5"/>
          <path d="M55 147 C110 147 65 58 143 67 S240 175 279 143 S340 158 371 128" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 6" opacity=".5"/>
          <g fill="var(--color-bg-card)" stroke="currentColor" stroke-width="1.5"><circle cx="55" cy="147" r="9"/><circle cx="143" cy="67" r="9"/><circle cx="279" cy="143" r="9"/></g>
          <g fill="currentColor"><circle cx="55" cy="147" r="3"/><circle cx="143" cy="67" r="3"/><circle cx="279" cy="143" r="3"/></g>
          <g fill="currentColor" font-size="11" font-family="sans-serif"><text x="28" y="178">城市漫步</text><text x="118" y="42">在地寻味</text><text x="254" y="178">山野日落</text></g>
        </svg>
        <div class="preview-footer"><span>去发现，也留一点时间给偶遇。</span><span>↗</span></div>
      </div>
      <ol class="intro-steps">
        <li><span>01</span><div><strong>说说你的旅行</strong><p>目的地、时间，以及你的偏好</p></div></li>
        <li><span>02</span><div><strong>挑选心动的景点</strong><p>AI 给出建议，选择权在你</p></div></li>
        <li><span>03</span><div><strong>带上行程，出发</strong><p>调整每日安排，保存或导出</p></div></li>
      </ol>
    </aside>

    <section class="form-section" ref="formRef">
      <div class="form-panel" ref="panelRef">
        <div class="form-intro"><span class="eyebrow">LET’S PLAN</span><h2>开启你的下一段旅程</h2><p>花一点时间，规划一场喜欢的旅行。</p></div>
        <a-form v-show="!loading" :model="formData" layout="vertical" @finish="handleSubmit">
          <!-- Step 01: Destination & Date -->
          <div class="step">
            <div class="step-head">
              <span class="step-num">01</span>
              <h3>选择目的地</h3>
            </div>

            <div class="city-list">
              <div v-for="(cs, idx) in formData.cities" :key="idx" class="city-row">
                <a-form-item class="city-row-name" :name="['cities', idx, 'city']" :rules="[{ required: true, message: '请输入城市名' }]">
                  <template #label>
                    <span class="field-label">城市 {{ idx + 1 }}</span>
                  </template>
                  <a-input v-model:value="cs.city" :aria-label="`城市 ${idx + 1}`" placeholder="输入城市名，如北京" size="large" class="field-input" />
                </a-form-item>
                <a-form-item class="city-row-days">
                  <template #label><span class="field-label">停留天数</span></template>
                  <a-input-number v-model:value="cs.days" :min="1" :max="15" size="large" class="field-input" style="width:100%" />
                </a-form-item>
                <button v-if="formData.cities.length > 1" type="button" :aria-label="`移除城市 ${idx + 1}`" class="city-remove-btn" @click="removeCity(idx)">×</button>
              </div>
              <button type="button" class="city-add-btn" @click="addCity">+ 添加城市</button>
            </div>

            <div class="grid grid-date">
              <a-form-item name="start_date" :rules="[{ required: true, message: '请选择日期' }]">
                <template #label><span class="field-label">出发日期</span></template>
                <a-date-picker v-model:value="formData.start_date" value-format="YYYY-MM-DD" style="width:100%" size="large" class="field-input" placeholder="选择出发日期" />
              </a-form-item>
              <a-form-item>
                <template #label><span class="field-label">总天数</span></template>
                <div class="days-chip">
                  <span class="days-number">{{ totalDays }}</span>
                  <span class="days-unit">天</span>
                </div>
                <div v-if="dateRangePreview" class="date-range-preview">
                  {{ dateRangePreview }}
                </div>
              </a-form-item>
            </div>

            <div class="hot-cities-row">
              <span class="hot-label">热门:</span>
              <button v-for="city in hotCities" :key="city" type="button" class="hot-city-tag" @click="formData.cities = [{ city, days: formData.cities[0]?.days || 3 }]">{{ city }}</button>
            </div>
          </div>

          <!-- Step 02: Preferences -->
          <div class="step">
            <div class="step-head">
              <span class="step-num">02</span>
              <h3>旅行偏好</h3>
            </div>
            <div class="grid grid2">
              <a-form-item name="transportation">
                <template #label><span class="field-label">交通方式</span></template>
                <a-select v-model:value="formData.transportation" size="large" class="field-select">
                  <a-select-option value="公共交通">公共交通</a-select-option>
                  <a-select-option value="自驾">自驾</a-select-option>
                  <a-select-option value="步行">步行</a-select-option>
                  <a-select-option value="混合">混合</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item name="accommodation">
                <template #label><span class="field-label">住宿偏好</span></template>
                <a-select v-model:value="formData.accommodation" size="large" class="field-select">
                  <a-select-option value="经济型酒店">经济型酒店</a-select-option>
                  <a-select-option value="舒适型酒店">舒适型酒店</a-select-option>
                  <a-select-option value="豪华酒店">豪华酒店</a-select-option>
                  <a-select-option value="民宿">民宿</a-select-option>
                </a-select>
              </a-form-item>
            </div>

            <a-form-item name="preferences">
              <template #label><span class="field-label">兴趣标签</span></template>
              <div class="interest-grid">
                <button type="button"
                  v-for="item in interestOptions"
                  :key="item.value"
                  class="interest-pill"
                  :class="{ active: formData.preferences.includes(item.value) }"
                  :aria-pressed="formData.preferences.includes(item.value)"
                  @click="togglePreference(item.value)"
                >
                  <span class="interest-emoji">{{ item.emoji }}</span>
                  {{ item.label }}
                </button>
              </div>
            </a-form-item>

            <a-form-item name="food_preference">
              <template #label><span class="field-label">美食偏好</span></template>
              <a-select v-model:value="formData.food_preference" size="large" class="field-select">
                <a-select-option value="本地特色">本地特色</a-select-option>
                <a-select-option value="川菜">川菜</a-select-option>
                <a-select-option value="粤菜">粤菜</a-select-option>
                <a-select-option value="日料">日料</a-select-option>
                <a-select-option value="西餐">西餐</a-select-option>
                <a-select-option value="小吃">小吃</a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item name="companions">
              <template #label><span class="field-label">出行同伴</span></template>
              <a-select v-model:value="formData.companions.type" size="large" class="field-select">
                <a-select-option value="solo">独自出行</a-select-option>
                <a-select-option value="couple">情侣出行</a-select-option>
                <a-select-option value="family">家庭亲子</a-select-option>
                <a-select-option value="friends">朋友出行</a-select-option>
                <a-select-option value="elderly">带老人</a-select-option>
              </a-select>
            </a-form-item>
          </div>

          <!-- Step 03: Extra -->
          <div class="step">
            <div class="step-head">
              <span class="step-num">03</span>
              <h3>额外需求</h3>
            </div>
            <div class="grid grid2">
              <a-form-item>
                <template #label><span class="field-label">预算上限 (元)</span></template>
                <a-input-number v-model:value="formData.budget" :min="0" :max="100000" size="large" class="field-input" style="width:100%" placeholder="不限" />
              </a-form-item>
              <a-form-item>
                <template #label><span class="field-label">人数</span></template>
                <a-input-number v-model:value="formData.companions.count" :min="1" :max="20" size="large" class="field-input" style="width:100%" />
              </a-form-item>
            </div>
            <a-form-item name="free_text_input">
              <div class="field-textarea">
                <a-textarea v-model:value="formData.free_text_input" placeholder="还有什么特殊需求？比如'多安排博物馆'、'不要太累'..." :rows="4" size="large" class="special-textarea" />
              </div>
            </a-form-item>
          </div>

          <a-form-item>
            <button type="submit" class="btn btn-danger btn-round submit-btn" :class="{ loading }" :disabled="loading">
              <span v-if="!loading">发现我的旅行灵感 <span aria-hidden="true">↗</span></span>
              <span v-else class="loading-row">
                <i class="spinner"></i> 生成中...
              </span>
            </button>
          </a-form-item>
        </a-form>

        <!-- Loading Stepper -->
        <div v-show="loading" class="stepper-wrapper">
          <div class="stepper-header">
            <h2 class="stepper-title">正在为您规划...</h2>
            <p class="stepper-subtitle">AI 正在搜索景点、查询天气、推荐酒店</p>
          </div>
          <div class="stepper-container">
            <div v-for="s in loadingSteps" :key="s.key" class="step-node" :class="{ active: s.active, completed: s.done }">
              <div class="node-icon">
                <i v-if="s.active && !s.done" class="spinner-small"></i>
                <svg v-else-if="s.done" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6bd098" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>
                <span v-else class="node-dot"></span>
              </div>
              <p class="node-text">{{ s.label }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <footer class="landing-footer">
      <div class="footer-inner">
        <span>云途 YunTu &copy; {{ new Date().getFullYear() }}</span>
        <span class="footer-dot">·</span>
        <span>让每一次出发，都更从容</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { tripEndDate } from '@/composables/tripDates'
import type { TripFormState } from '@/types'

const router = useRouter()
const formRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const loading = ref(false)

const hotCities = ['北京', '上海', '成都', '杭州', '西安', '三亚', '大理', '重庆', '广州', '厦门']

const interestOptions = [
  { value: '历史文化', label: '历史文化', emoji: '🏛️' },
  { value: '自然风光', label: '自然风光', emoji: '🏔️' },
  { value: '美食', label: '美食', emoji: '🍜' },
  { value: '购物', label: '购物', emoji: '🛍️' },
  { value: '亲子', label: '亲子', emoji: '👨‍👩‍👧' },
  { value: '网红打卡', label: '网红打卡', emoji: '📸' },
  { value: '博物馆', label: '博物馆', emoji: '🏛️' },
  { value: '古镇园林', label: '古镇园林', emoji: '🏯' },
  { value: '夜生活', label: '夜生活', emoji: '🌃' },
  { value: '户外运动', label: '户外运动', emoji: '🏃' },
]

const formData = reactive<TripFormState>({
  city: '',
  cities: [{ city: '', days: 3 }],
  start_date: '',
  end_date: '',
  travel_days: 3,
  transportation: '公共交通',
  accommodation: '经济型酒店',
  preferences: [],
  food_preference: '本地特色',
  free_text_input: '',
  budget: undefined,
  companions: { count: 1, type: 'solo' },
})

const totalDays = computed(() => {
  return formData.cities.reduce((sum, c) => sum + (c.days || 0), 0)
})

/** 实时日期范围预览："6月1日 - 6月3日 · 共3天"，让用户在提交前看到结束日期 */
const dateRangePreview = computed(() => {
  if (!formData.start_date) return ''
  const start = new Date(formData.start_date)
  if (Number.isNaN(start.getTime())) return ''
  const end = new Date(start)
  end.setDate(start.getDate() + Math.max(totalDays.value, 1) - 1)
  const fmt = (d: Date) => `${d.getMonth() + 1}月${d.getDate()}日`
  return `${fmt(start)} - ${fmt(end)} · 共${totalDays.value}天`
})

const loadingSteps = ref([
  { key: 'search', label: '搜索景点攻略', active: false, done: false },
  { key: 'weather', label: '查询天气信息', active: false, done: false },
  { key: 'hotel', label: '推荐酒店住宿', active: false, done: false },
  { key: 'plan', label: '生成旅行计划', active: false, done: false },
])

function addCity() {
  formData.cities.push({ city: '', days: 2 })
}

function removeCity(idx: number) {
  if (formData.cities.length > 1) formData.cities.splice(idx, 1)
}

function togglePreference(val: string) {
  const i = formData.preferences.indexOf(val)
  if (i >= 0) formData.preferences.splice(i, 1)
  else formData.preferences.push(val)
}

async function handleSubmit() {
  const firstCity = formData.cities[0]
  if (!firstCity || formData.cities.some(c => !c.city.trim())) {
    message.error('请填写每一站的目的地城市')
    return
  }
  if (!formData.start_date) {
    message.error('请选择出发日期')
    return
  }
  if (formData.preferences.length === 0) {
    message.error('请至少选择一个兴趣标签')
    return
  }

  if (formData.cities.some(c => !Number.isInteger(c.days) || c.days < 1) || totalDays.value > 30) {
    message.error('每站至少停留 1 天，行程总天数不能超过 30 天')
    return
  }
  formData.cities = formData.cities.map(c => ({ ...c, city: c.city.trim() }))
  formData.city = firstCity.city.trim()
  formData.travel_days = totalDays.value

  formData.end_date = tripEndDate(formData.start_date, totalDays.value)

  // 存入 sessionStorage，跳转发现页开始景点选择
  sessionStorage.setItem('tripFormData', JSON.stringify(formData))
  router.push('/discover')
}
</script>

<style scoped>
.landing-page { max-width: 1280px; margin: auto; padding: 108px 36px 28px; display: grid; grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr); gap: 64px; align-items: start; }
/* 侧栏(约845px)高于多数视口: 只有视口足够高时才启用 sticky, 否则吸附元素底部会溢出网格与 footer 重叠 */
.travel-intro { position: relative; }
@media (min-height: 1000px) {
  .travel-intro { position: sticky; top: 102px; }
}
.travel-intro > .eyebrow { display: flex; align-items: center; gap: 8px; }
.intro-dot { width: 6px; height: 6px; background: var(--color-primary); border-radius: 50%; }
.travel-intro h1 { font-size: clamp(34px, 3.5vw, 49px); font-weight: 650; letter-spacing: -1.5px; line-height: 1.45; margin: 22px 0; }
.intro-description { max-width: 370px; color: var(--color-text-secondary); font-size: 15px; line-height: 1.9; }
.intro-features { display: flex; gap: 20px; font-size: 12px; color: var(--color-text-secondary); margin: 22px 0 32px; }
.intro-features span::before { content: '✓'; margin-right: 6px; color: var(--color-primary); }
.journey-preview { color: var(--color-primary); border: 1px solid var(--color-border); border-radius: 16px; background: var(--color-bg-card); overflow: hidden; transform: rotate(-1.5deg); box-shadow: 0 8px 24px rgba(23,53,43,.04); }
.preview-heading { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; padding: 20px 22px 0; font-size: 12px; }
.preview-stamp { color: var(--color-text-tertiary); font-size: 9px; letter-spacing: 1px; }
.journey-drawing { display: block; width: 100%; }
.preview-footer { display: flex; justify-content: space-between; border-top: 1px dashed var(--color-border); padding: 14px 22px; font-size: 11px; color: var(--color-text-secondary); }
.intro-steps { display: flex; flex-direction: column; gap: 18px; margin: 32px 0 0; padding: 0; list-style: none; }
.intro-steps li { display: flex; gap: 15px; align-items: baseline; }
.intro-steps li > span { color: var(--color-accent); font-size: 11px; font-weight: 600; }
.intro-steps strong { font-size: 13px; font-weight: 550; }
.intro-steps p { font-size: 12px; color: var(--color-text-tertiary); margin: 4px 0 0; }
.form-section { min-width: 0; }
.form-panel { padding: 32px; background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 20px; box-shadow: 0 8px 40px rgba(23,53,43,.04); }
.form-intro { border-bottom: 1px solid var(--color-border-light); padding-bottom: 22px; }
.form-intro h2 { font-size: 23px; font-weight: 600; margin: 8px 0; letter-spacing: -.5px; }
.form-intro p { font-size: 13px; color: var(--color-text-tertiary); margin: 0; }
.step { padding: 26px 0 12px; border-bottom: 1px solid var(--color-border-light); }
.step-head { display: flex; gap: 10px; align-items: center; margin-bottom: 22px; }
.step-head h3 { margin: 0; font-size: 15px; font-weight: 600; }
.step-num { color: var(--color-primary); font-size: 11px; font-weight: 650; background: var(--color-primary-soft); padding: 5px 7px; border-radius: 6px; }
.field-label { color: var(--color-text-secondary); font-size: 12px; font-weight: 500; }
.city-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; }
.city-row { display: flex; gap: 12px; align-items: flex-start; }
.city-row-name { flex: 1; min-width: 0; margin-bottom: 0; }
.city-row-days { width: 106px; margin-bottom: 0; }
.city-remove-btn { margin-top: 32px; border: 0; background: var(--color-bg-secondary); color: var(--color-text-secondary); width: 28px; height: 32px; border-radius: 6px; cursor: pointer; flex: none; }
.city-add-btn { border: 1px dashed var(--color-border); background: transparent; color: var(--color-primary); padding: 9px; font-size: 12px; border-radius: 8px; cursor: pointer; }
.grid { display: grid; gap: 16px; }
.grid-date { grid-template-columns: minmax(0, 1fr) minmax(110px, .55fr); }
.grid2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.days-chip { display: flex; height: 44px; align-items: baseline; gap: 6px; padding: 6px 14px; background: var(--color-bg-secondary); border-radius: 8px; }
.days-number { font-weight: 600; font-size: 22px; color: var(--color-primary); }
.days-unit { font-size: 12px; }
.date-range-preview { font-size: 11px; color: var(--color-text-tertiary); margin-top: 5px; }
.hot-cities-row { display: flex; gap: 7px; flex-wrap: wrap; align-items: center; margin: 0 0 10px; }
.hot-label { font-size: 11px; color: var(--color-text-tertiary); }
.hot-city-tag { border: 0; background: var(--color-bg-secondary); color: var(--color-text-secondary); font-size: 11px; padding: 5px 10px; border-radius: 5px; cursor: pointer; }
.hot-city-tag:hover, .city-add-btn:hover { background: var(--color-primary-soft); color: var(--color-primary); }
.interest-grid { display: flex; gap: 8px; flex-wrap: wrap; }
.interest-pill { border: 1px solid var(--color-border); border-radius: 7px; background: transparent; color: var(--color-text-secondary); padding: 7px 10px; font-size: 12px; cursor: pointer; }
.interest-pill.active { color: var(--color-primary); border-color: var(--color-primary); background: var(--color-primary-soft); }
.interest-emoji { margin-right: 4px; font-size: 12px; }
.special-textarea { font-size: 13px; }
.submit-btn { width: 100%; margin-top: 24px; padding: 13px 20px; border: 0; border-radius: 10px; background: var(--color-primary); color: var(--color-text-inverse); font-size: 14px; font-weight: 600; cursor: pointer; }
.submit-btn > span { display: flex; align-items: center; justify-content: space-between; }
.submit-btn:hover { background: var(--color-primary-hover); }
.landing-footer { grid-column: 1 / -1; padding: 26px 0; border-top: 1px solid var(--color-border); font-size: 11px; color: var(--color-text-tertiary); }
.footer-inner { display: flex; justify-content: space-between; gap: 12px; }
.footer-dot { display: none; }
@media (max-width: 1000px) { .landing-page { gap: 32px; padding: 88px 24px 0; } .form-panel { padding: 24px; } .intro-features { gap: 12px; } }
@media (max-width: 760px) {
  .landing-page { display: block; padding: 84px 16px 0; }
  .travel-intro { position: static; padding: 0 8px; }
  .travel-intro h1 { font-size: 34px; margin: 16px 0; }
  .intro-description { max-width: 100%; font-size: 14px; }
  .journey-preview, .intro-steps { display: none; }
  .intro-features { margin: 18px 0 26px; }
  .form-panel { padding: 24px 20px; border-radius: 16px; }
  .form-intro h2 { font-size: 21px; }
  .landing-footer { margin-top: 32px; }
  .city-row-days { width: 88px; }
}
</style>
