<template>
  <div class="result-hero" :style="heroStyle">
    <div class="hero-overlay"></div>
    <div class="hero-inner">
      <div class="hero-top">
        <button class="hero-back" @click="$emit('goBack')">
          <span class="back-arrow">←</span>
          <span class="back-text">返回</span>
        </button>
        <div class="hero-actions">
          <button v-if="!isSaved" class="hero-btn" :disabled="savingTrip" @click="$emit('save')">
            <span v-if="savingTrip" class="btn-spinner"></span>
            {{ savingTrip ? '保存中...' : '保存行程' }}
          </button>
          <button v-else class="hero-btn hero-btn-done" disabled>已保存</button>

          <button v-if="!editMode" class="hero-btn" @click="$emit('edit')">编辑行程</button>
          <template v-else>
            <button class="hero-btn hero-btn-primary" @click="$emit('saveChanges')">保存修改</button>
            <button class="hero-btn" @click="$emit('cancelEdit')">取消</button>
          </template>

          <div v-if="!editMode" class="export-dropdown" ref="exportDropdownRef">
            <button class="hero-btn" @click="showExport = !showExport">
              导出 <span class="dropdown-arrow">▾</span>
            </button>
            <div v-if="showExport" class="export-menu" @mouseleave="showExport = false">
              <button class="export-menu-item" @click="$emit('exportImage'); showExport = false">导出为图片</button>
              <button class="export-menu-item" @click="$emit('exportPdf'); showExport = false">导出为PDF</button>
            </div>
          </div>
        </div>
      </div>
      <div class="hero-content">
        <h1 class="hero-title">{{ heroTitle }}</h1>
        <div class="hero-tags">
          <span class="hero-tag">📅 {{ tripPlan.start_date }} 出发</span>
          <span class="hero-tag-divider">|</span>
          <span class="hero-tag">💰 预估 ¥{{ totalBudget }}</span>
          <span class="hero-tag-divider">|</span>
          <span class="hero-tag">☀️ {{ weatherSummary }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { TripPlan } from '@/types'

const props = defineProps<{
  tripPlan: TripPlan
  isSaved: boolean
  savingTrip: boolean
  editMode: boolean
}>()

defineEmits<{
  goBack: []
  save: []
  edit: []
  saveChanges: []
  cancelEdit: []
  exportImage: []
  exportPdf: []
}>()

const showExport = ref(false)
const cityPhoto = ref('')

const nights = computed(() => {
  const days = props.tripPlan.days?.length || 1
  return days > 1 ? days - 1 : 0
})

const heroTitle = computed(() => {
  const city = props.tripPlan.city
  const days = props.tripPlan.days?.length || 1
  const duration = nights.value > 0 ? `${days}天${nights.value}晚` : `${days}天`
  const tagline = props.tripPlan.trip_tagline
  return tagline ? `${city} ${duration} ${tagline}` : `${city} ${duration}`
})

const totalBudget = computed(() => {
  return props.tripPlan.budget?.total || '—'
})

const weatherSummary = computed(() => {
  if (props.tripPlan.weather_summary) return props.tripPlan.weather_summary
  if (props.tripPlan.weather_info?.length) {
    return props.tripPlan.weather_info[0].day_weather || '暂无天气信息'
  }
  return '暂无天气信息'
})

const heroStyle = computed(() => {
  if (cityPhoto.value) {
    return { backgroundImage: `url(${cityPhoto.value})` }
  }
  return {}
})

onMounted(async () => {
  try {
    const res = await fetch(`/api/poi/photo?name=${encodeURIComponent(props.tripPlan.city + ' city skyline')}`)
    const data = await res.json()
    if (data.success && data.data?.photo_url) {
      cityPhoto.value = data.data.photo_url
    }
  } catch {
    // fallback to gradient
  }
})
</script>

<style scoped>
.result-hero {
  position: relative;
  overflow: hidden;
  min-height: 320px;
  display: flex;
  align-items: stretch;
  background: var(--color-bg-hero);
  background-size: cover;
  background-position: center;
  transition: background-image 0.6s ease;
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.35) 0%,
    rgba(0, 0, 0, 0.25) 40%,
    rgba(0, 0, 0, 0.55) 100%
  );
  z-index: 0;
}

.hero-inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
  position: relative;
  z-index: 1;
  width: 100%;
  padding: var(--space-8) var(--space-6) var(--space-10);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.hero-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-8);
}

.hero-back {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-pill);
  padding: var(--space-2) var(--space-4);
  color: rgba(255, 255, 255, 0.9);
  font-size: var(--font-size-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  backdrop-filter: blur(8px);
}

.hero-back:hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.back-arrow {
  font-size: var(--font-size-lg);
}

.hero-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.hero-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-family-base);
  cursor: pointer;
  transition: all 150ms linear;
  white-space: nowrap;
}

.hero-btn:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.5);
  color: #fff;
  background: rgba(255, 255, 255, 0.18);
}

.hero-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hero-btn-primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.hero-btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.hero-btn-done {
  background: rgba(107, 208, 152, 0.2);
  border-color: rgba(107, 208, 152, 0.3);
  color: #6bd098;
}

/* Export dropdown */
.export-dropdown {
  position: relative;
}

.export-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: rgba(30, 30, 50, 0.95);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 6px;
  min-width: 140px;
  z-index: 10;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
}

.export-menu-item {
  display: block;
  width: 100%;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font-family-base);
  cursor: pointer;
  text-align: left;
  transition: all 100ms linear;
}

.export-menu-item:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.dropdown-arrow {
  font-size: 10px;
  opacity: 0.6;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.hero-content {
  text-align: center;
}

.hero-title {
  font-size: clamp(1.8rem, 4vw, 3rem);
  font-weight: var(--font-weight-bold);
  color: #fff;
  margin: 0 0 var(--space-5);
  letter-spacing: 0.03em;
  text-shadow: 0 2px 24px rgba(0, 0, 0, 0.4);
  animation: fadeInUp var(--transition-normal);
  line-height: 1.3;
}

.hero-tags {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  animation: fadeInUp var(--transition-normal);
  animation-delay: 0.15s;
  animation-fill-mode: both;
}

.hero-tag {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-3);
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: var(--radius-pill);
  color: rgba(255, 255, 255, 0.95);
  font-size: var(--font-size-md);
  backdrop-filter: blur(10px);
  white-space: nowrap;
}

.hero-tag-divider {
  color: rgba(255, 255, 255, 0.4);
  font-size: var(--font-size-md);
}

@media (max-width: 768px) {
  .result-hero {
    min-height: 260px;
  }
  .hero-inner {
    padding: var(--space-5) var(--space-4) var(--space-8);
  }
  .hero-top {
    flex-direction: column;
    gap: var(--space-3);
    align-items: flex-start;
  }
  .hero-actions {
    flex-wrap: wrap;
  }
  .hero-title {
    font-size: clamp(1.4rem, 5vw, 2rem);
  }
  .hero-tags {
    gap: var(--space-2);
  }
  .hero-tag-divider {
    display: none;
  }
  .back-text {
    display: none;
  }
}
</style>
