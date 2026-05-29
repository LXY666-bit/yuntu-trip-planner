<template>
  <div class="landing-page">
    <div class="page-header section-dark landing-header">
      <div class="filter"></div>
      <div class="content-center">
        <div class="container">
          <div class="title-brand">
            <h1 class="presentation-title">YUNTU</h1>
            <div class="title-underline"></div>
          </div>
          <h2 class="presentation-subtitle text-center">云途 · AI 驱动的个性化旅行规划</h2>
        </div>
      </div>
      <div class="moving-clouds"></div>
      <div class="fog-low">
        <img src="https://demos.creative-tim.com/paper-kit-2/assets/img/clouds.png" alt="fog" />
      </div>
      <div class="fog-low right">
        <img src="https://demos.creative-tim.com/paper-kit-2/assets/img/clouds.png" alt="fog" />
      </div>
      <div class="hero-bottom-shade"></div>
    </div>

    <section class="form-section" ref="formRef">
      <div class="form-panel" ref="panelRef">
        <a-form v-show="!loading" :model="formData" layout="vertical" @finish="handleSubmit">
          <!-- Step 01: Destination & Date -->
          <div class="step">
            <div class="step-head">
              <span class="step-num">01</span>
              <h3>选择目的地</h3>
            </div>

            <div class="city-list">
              <div v-for="(cs, idx) in formData.cities" :key="idx" class="city-row">
                <a-form-item class="city-row-name" :rules="[{ required: true, message: '请输入城市名' }]">
                  <template #label>
                    <span class="field-label">城市 {{ idx + 1 }}</span>
                  </template>
                  <a-input v-model:value="cs.city" placeholder="输入城市名，如北京" size="large" class="field-input" />
                </a-form-item>
                <a-form-item class="city-row-days">
                  <template #label><span class="field-label">停留天数</span></template>
                  <a-input-number v-model:value="cs.days" :min="1" :max="15" size="large" class="field-input" style="width:100%" />
                </a-form-item>
                <button v-if="formData.cities.length > 1" type="button" class="city-remove-btn" @click="removeCity(idx)">×</button>
              </div>
              <button type="button" class="city-add-btn" @click="addCity">+ 添加城市</button>
            </div>

            <div class="grid grid-date">
              <a-form-item name="start_date" :rules="[{ required: true, message: '请选择日期' }]">
                <template #label><span class="field-label">出发日期</span></template>
                <a-date-picker v-model:value="formData.start_date" style="width:100%" size="large" class="field-input" placeholder="选择出发日期" />
              </a-form-item>
              <a-form-item>
                <template #label><span class="field-label">总天数</span></template>
                <div class="days-chip">
                  <span class="days-number">{{ totalDays }}</span>
                  <span class="days-unit">天</span>
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
                <label
                  v-for="item in interestOptions"
                  :key="item.value"
                  class="interest-pill"
                  :class="{ active: formData.preferences.includes(item.value) }"
                  @click.prevent="togglePreference(item.value)"
                >
                  <span class="interest-emoji">{{ item.emoji }}</span>
                  {{ item.label }}
                </label>
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
              <span v-if="!loading">开始规划行程</span>
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
        <span>云途 YunTu &copy; 2025</span>
        <span class="footer-dot">·</span>
        <span>基于 AI + LangGraph 技术驱动</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { TripFormData } from '@/types'

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

const formData = reactive<TripFormData>({
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
  if (!firstCity || !firstCity.city.trim()) {
    message.error('请至少输入一个目的地城市')
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

  formData.city = firstCity.city.trim()
  formData.travel_days = totalDays.value

  const startDate = new Date(formData.start_date)
  const endDate = new Date(startDate)
  endDate.setDate(endDate.getDate() + totalDays.value - 1)
  formData.end_date = endDate.toISOString().split('T')[0]

  // 存入 sessionStorage，跳转发现页开始景点选择
  sessionStorage.setItem('tripFormData', JSON.stringify(formData))
  router.push('/discover')
}
</script>

<style scoped>
/* === Hero Section === */
.landing-header {
  position: relative;
  min-height: 520px;
  background: linear-gradient(135deg, #1a0a2e 0%, #16213e 50%, #0f3460 100%);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.filter {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1;
}

.content-center {
  position: relative;
  z-index: 2;
  text-align: center;
  padding: 0 24px;
}

.title-brand {
  margin-bottom: 16px;
}

.presentation-title {
  font-size: 5em;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.08em;
  margin: 0;
  text-shadow: 0 2px 30px rgba(245, 89, 61, 0.4);
  background: linear-gradient(135deg, #fff 0%, #f7765f 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.title-underline {
  width: 80px;
  height: 3px;
  background: var(--color-primary);
  margin: 16px auto 0;
  border-radius: 2px;
}

.presentation-subtitle {
  font-size: 1.2em;
  font-weight: 300;
  color: rgba(255, 255, 255, 0.75);
  margin-top: 16px;
}

.moving-clouds {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 120px;
  background: url(https://demos.creative-tim.com/paper-kit-2/assets/img/clouds.png) repeat-x;
  background-size: 1000px;
  opacity: 0.15;
  z-index: 1;
  animation: moveClouds 60s linear infinite;
}

.fog-low {
  position: absolute;
  bottom: -40px;
  left: 0;
  width: 60%;
  opacity: 0.08;
  z-index: 1;
}

.fog-low.right {
  left: auto;
  right: 0;
  bottom: -60px;
}

.hero-bottom-shade {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 120px;
  background: linear-gradient(to top, var(--color-bg-secondary), transparent);
  z-index: 2;
}

@keyframes moveClouds {
  from { background-position: 0 0; }
  to { background-position: 1000px 0; }
}

/* === Form Section === */
.form-section {
  position: relative;
  z-index: 3;
  max-width: 1100px;
  margin: -60px auto 60px;
  padding: 0 24px;
}

.form-panel {
  background: var(--color-bg-card);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 48px;
  transition: var(--transition-normal);
}

/* The form uses a 2-column layout for fields */
@media (min-width: 769px) {
  .form-panel {
    padding: 56px;
  }

  .step-content-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }

  .step-content-row .full-width {
    grid-column: 1 / -1;
  }
}

.step {
  padding: 24px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.step:last-child { border-bottom: none; }

.step-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.step-num {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary);
  color: #fff;
  border-radius: 50%;
  font-weight: 700;
  font-size: 16px;
  flex-shrink: 0;
}

.step-head h3 {
  margin: 0;
  font-size: 1.3em;
  font-weight: 600;
  color: var(--color-text-primary);
}

.field-label {
  font-weight: 600;
  font-size: 13px;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* City list */
.city-list { display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; }

.city-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.city-row-name { flex: 1; margin-bottom: 0; }
.city-row-days { width: 120px; margin-bottom: 0; }

.city-remove-btn {
  margin-top: 30px;
  width: 28px; height: 28px;
  border: none;
  border-radius: 50%;
  background: rgba(245, 89, 61, 0.12);
  color: var(--color-primary);
  font-size: 16px;
  cursor: pointer;
  transition: var(--transition-fast);
  flex-shrink: 0;
}
.city-remove-btn:hover { background: var(--color-primary); color: #fff; }

.city-add-btn {
  background: none;
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
  padding: 10px;
  cursor: pointer;
  transition: var(--transition-fast);
}
.city-add-btn:hover { border-color: var(--color-primary); background: var(--color-primary-soft); }

.hot-cities-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.hot-label { font-size: 12px; color: var(--color-text-tertiary); font-weight: 500; }
.hot-city-tag {
  border: 1px solid var(--color-border);
  border-radius: 16px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
  transition: var(--transition-fast);
  font-family: var(--font-family-base);
}
.hot-city-tag:hover { border-color: var(--color-primary); color: var(--color-primary); }

/* Grids */
.grid { display: grid; gap: 20px; }
.grid-date { grid-template-columns: 1fr 120px; }
.grid2 { grid-template-columns: 1fr 1fr; }
.grid3 { grid-template-columns: 1fr 1fr 1fr; }

.days-chip {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 7px 16px;
  background: var(--color-primary-soft);
  border-radius: 8px;
  height: 40px;
}
.days-number { font-size: 24px; font-weight: 700; color: var(--color-primary); }
.days-unit { font-size: 14px; color: var(--color-text-tertiary); }

/* Interest pills */
.interest-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.interest-pill {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 18px;
  border: 2px solid var(--color-border);
  border-radius: 24px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
  user-select: none;
  background: transparent;
}
.interest-pill:hover { border-color: var(--color-primary); color: var(--color-primary); }
.interest-pill.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.interest-emoji { font-size: 16px; }

/* Textarea */
.field-textarea { margin-top: 4px; }

.special-textarea {
  border-radius: 8px !important;
  border: 1px solid var(--color-border) !important;
  font-family: var(--font-family-base) !important;
  transition: var(--transition-normal) !important;
}
.special-textarea:focus { border-color: var(--color-primary) !important; box-shadow: 0 0 0 2px var(--color-primary-soft) !important; }

/* Submit btn */
.submit-btn {
  width: 100%;
  padding: 14px 32px !important;
  font-size: 15px !important;
  font-weight: 700 !important;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #f5593d, #f33816) !important;
  border: none !important;
  margin-top: 16px;
  transition: var(--transition-normal) !important;
  color: #fff !important;
}
.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(245, 89, 61, 0.4);
}
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.loading-row { display: flex; align-items: center; justify-content: center; gap: 8px; }

.spinner {
  width: 18px; height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

/* Stepper */
.stepper-wrapper { padding: 20px 0; text-align: center; }
.stepper-title { font-size: 1.4em; font-weight: 600; margin: 0; color: var(--color-text-primary); }
.stepper-subtitle { color: var(--color-text-tertiary); margin: 8px 0 32px; font-size: 14px; }

.stepper-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 360px;
  margin: 0 auto;
}

.step-node {
  display: flex;
  align-items: center;
  gap: 16px;
  opacity: 0.3;
  transition: var(--transition-normal);
}
.step-node.active, .step-node.completed { opacity: 1; }

.node-icon {
  width: 40px; height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.05);
  border-radius: 50%;
  flex-shrink: 0;
}
[data-theme="dark"] .node-icon { background: rgba(255,255,255,0.06); }

.node-dot { width: 8px; height: 8px; background: var(--color-border); border-radius: 50%; }
.active .node-dot { background: var(--color-primary); animation: pulse 1.5s ease infinite; }

.spinner-small {
  width: 18px; height: 18px;
  border: 2px solid rgba(245, 89, 61, 0.2);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

.node-text { font-size: 14px; font-weight: 500; color: var(--color-text-secondary); margin: 0; }

/* Footer */
.landing-footer {
  text-align: center;
  padding: 32px;
  color: var(--color-text-tertiary);
  font-size: 13px;
  border-top: 1px solid var(--color-border-light);
}
.footer-dot { margin: 0 8px; opacity: 0.4; }

@keyframes spin { to { transform: rotate(360deg); } }

/* Responsive */
@media (max-width: 768px) {
  .landing-header { min-height: 360px; }
  .presentation-title { font-size: 3em; }
  .presentation-subtitle { font-size: 1em; }
  .form-panel { padding: 24px; }
  .grid-date, .grid2, .grid3 { grid-template-columns: 1fr; }
  .city-row { flex-direction: column; }
  .city-row-days { width: 100%; }
}

@media (min-width: 1400px) {
  .form-section { max-width: 1200px; }
  .form-panel { padding: 64px 72px; }
}
</style>
