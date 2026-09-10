<template>
  <div class="tab-overview">
    <!-- 景点叠层轮播 -->
    <div v-if="overviewAttractions.length > 0" class="overview-swiper-section">
      <h3 class="section-title">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        景点概览
        <span class="title-count">{{ overviewAttractions.length }} 个景点</span>
      </h3>
      <AttractionCarousel :items="overviewAttractions" :photos="{ ...attractionPhotos, ...imageCache }" @select-day="goToDay" />
    </div>

    <!-- Trip Meta -->
    <div class="overview-meta-card">
      <div class="meta-row">
        <div class="meta-item" v-if="tripPlan.trip_tagline">
          <span class="meta-label">行程主题</span>
          <span class="meta-value highlight">{{ tripPlan.trip_tagline }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">日期</span>
          <span class="meta-value">{{ tripPlan.start_date }} ~ {{ tripPlan.end_date }}</span>
        </div>
        <div class="meta-item" v-if="tripPlan.cities && tripPlan.cities.length > 0">
          <span class="meta-label">{{ tripPlan.cities.length > 1 ? '途经城市' : '目的地' }}</span>
          <span class="meta-value">{{ tripPlan.cities.join(' → ') }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">天数</span>
          <span class="meta-value">{{ tripPlan.days.length }} 天</span>
        </div>
        <div class="meta-item" v-if="tripPlan.budget">
          <span class="meta-label">总预算</span>
          <span class="meta-value price">¥{{ tripPlan.budget.total?.toLocaleString() }}</span>
        </div>
        <div class="meta-item" v-if="tripPlan.weather_summary">
          <span class="meta-label">天气概况</span>
          <span class="meta-value">{{ tripPlan.weather_summary }}</span>
        </div>
      </div>
    </div>

    <!-- Overall Suggestions -->
    <div v-if="tripPlan.overall_suggestions" class="suggestions-card">
      <div class="suggestions-header">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>旅行建议</span>
      </div>
      <div class="suggestions-body" v-html="renderedSuggestions"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { TripPlan } from '@/types'
import AttractionCarousel from '@/components/result/AttractionCarousel.vue'
import type { OverviewAttractionItem } from '@/components/OverviewAttractionCard.vue'

const props = defineProps<{
  tripPlan: TripPlan
  attractionPhotos: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'goToDay', dayIndex: number): void
}>()

const imageCache = ref<Record<string, string>>({})

const overviewAttractions = computed<OverviewAttractionItem[]>(() => {
  const result: OverviewAttractionItem[] = []
  props.tripPlan.days.forEach((day, dayIdx) => {
    day.attractions.forEach((attr, order) => {
      result.push({
        name: attr.name,
        description: attr.description,
        visit_duration: attr.visit_duration,
        ticket_price: attr.ticket_price,
        reservation_required: attr.reservation_required,
        dayNumber: dayIdx + 1,
        dayArrayIndex: dayIdx,
        order,
      })
    })
  })
  return result
})

function goToDay(dayIndex: number) {
  emit('goToDay', dayIndex)
}

async function loadImages() {
  const names = [...new Set(overviewAttractions.value.map(a => a.name))]
  await Promise.all(names.map(async (name) => {
    if (imageCache.value[name] || props.attractionPhotos[name]) return
    try {
      const city = props.tripPlan.city || ''
      const res = await fetch(`/api/poi/photo?name=${encodeURIComponent(name)}&city=${encodeURIComponent(city)}`)
      const data = await res.json()
      if (data.success && data.data?.photo_url) {
        imageCache.value[name] = data.data.photo_url
      }
    } catch {}
  }))
}

onMounted(loadImages)

marked.setOptions({ breaks: true, gfm: true })

const renderedSuggestions = computed(() => {
  if (!props.tripPlan.overall_suggestions) return ''
  return DOMPurify.sanitize(marked.parse(props.tripPlan.overall_suggestions) as string)
})
</script>

<style scoped>
.tab-overview {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1em;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 16px;
}

.title-count {
  font-size: 0.8em;
  font-weight: 400;
  color: var(--color-text-tertiary);
  margin-left: auto;
}

/* Swiper Coverflow */
.overview-swiper-section {
  background: var(--color-bg-card);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
}

/* Meta Card */
.overview-meta-card {
  background: var(--color-bg-card);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
}

.meta-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-tertiary);
}

.meta-value {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.meta-value.highlight { color: var(--color-primary); font-weight: 600; }
.meta-value.price { color: var(--color-primary); font-weight: 700; font-size: 18px; }

/* Suggestions */
.suggestions-card {
  background: var(--color-bg-card);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
}

.suggestions-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 1.05em;
  color: var(--color-text-primary);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.suggestions-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-secondary);
}

:deep(.suggestions-body h2),
:deep(.suggestions-body h3) { color: var(--color-text-primary); font-weight: 600; margin: 20px 0 8px; }
:deep(.suggestions-body ul),
:deep(.suggestions-body ol) { padding-left: 20px; }
:deep(.suggestions-body li) { margin: 4px 0; }
:deep(.suggestions-body strong) { color: var(--color-text-primary); }
:deep(.suggestions-body blockquote) {
  border-left: 3px solid var(--color-primary);
  padding: 12px 16px;
  margin: 12px 0;
  background: var(--color-primary-soft);
  border-radius: 0 8px 8px 0;
  color: var(--color-text-secondary);
}

@media (max-width: 768px) {
  .tab-overview { padding: 0 8px; }
  .meta-row { grid-template-columns: 1fr 1fr; }
  .overview-swiper-section { padding: 16px; }
}

</style>
