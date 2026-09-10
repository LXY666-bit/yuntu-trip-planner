<template>
  <article class="trip-export">
    <header><span>TRAVEL JOURNAL · 旅行手册</span><h1>{{ tripPlan.city }} · {{ tripPlan.days.length }} 日旅行</h1><p>{{ tripPlan.start_date }} — {{ tripPlan.end_date }}</p><p>{{ tripPlan.trip_tagline }}</p></header>
    <section v-if="tripPlan.budget"><h2>预算概览</h2><div class="budget"><p v-for="item in budgetItems" :key="item.label">{{ item.label }}<strong>¥{{ item.value ?? 0 }}</strong></p></div></section>
    <section v-for="(day, index) in tripPlan.days" :key="index">
      <h2>第 {{ index + 1 }} 天 · {{ day.city || tripPlan.city }} <small>{{ day.date }}</small></h2>
      <div class="export-markdown" v-html="renderMarkdown(day.description)"></div><p v-if="day.transfer_info">{{ day.transfer_info }}</p>
      <div v-for="(attraction, i) in day.attractions" :key="i" class="stop">
        <h3>{{ i + 1 }}. {{ attraction.name }}</h3><p>{{ attraction.description }}</p>
        <p class="meta">{{ attraction.address }} · 建议游玩 {{ attraction.visit_duration }} 分钟<span v-if="attraction.ticket_price != null"> · 门票 ¥{{ attraction.ticket_price }}</span></p>
        <p v-if="attraction.open_hours">开放时间：{{ attraction.open_hours }}</p><p v-if="attraction.reservation_tips">预约提示：{{ attraction.reservation_tips }}</p>
      </div>
      <div v-if="day.meals?.length" class="notes"><h3>餐饮安排</h3><p v-for="(meal, i) in day.meals" :key="i">{{ mealNames[meal.type] || meal.type }} · {{ meal.name }}<span v-if="meal.estimated_cost != null"> · 约 ¥{{ meal.estimated_cost }}</span><br />{{ meal.address }} {{ meal.description }}</p></div>
      <div v-if="day.hotel" class="notes"><h3>住宿 · {{ day.hotel.name }}</h3><p>{{ day.hotel.address }} · {{ day.hotel.price_range }}</p></div>
      <div v-if="day.route_segments?.length" class="notes"><h3>交通路线</h3><p v-for="(segment, i) in day.route_segments" :key="i">{{ segment.from_name }} → {{ segment.to_name }} · {{ segment.mode }} · {{ segment.distance }} · {{ segment.duration }}<br />{{ segment.detail }}</p></div>
    </section>
    <section v-if="tripPlan.weather_info?.length"><h2>天气参考</h2><p v-for="weather in tripPlan.weather_info" :key="weather.date">{{ weather.date }} {{ weather.city }} · {{ weather.day_weather }} · {{ weather.night_temp }}–{{ weather.day_temp }}°C · {{ weather.wind_direction }} {{ weather.wind_power }}</p></section>
    <section v-if="tripPlan.overall_suggestions"><h2>出行建议</h2><div class="export-markdown" v-html="suggestions"></div></section>
    <footer>祝你一路有风景，每一站都有收获。</footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { TripPlan } from '@/types'
const props = defineProps<{ tripPlan: TripPlan }>()
const mealNames: Record<string, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '小吃' }
const renderMarkdown = (text: string) => DOMPurify.sanitize(marked.parse(text || '') as string, { FORBID_TAGS: ['img'] })
const suggestions = computed(() => renderMarkdown(props.tripPlan.overall_suggestions))
const budgetItems = computed(() => {
  const b = props.tripPlan.budget
  return [{ label: '门票', value: b?.total_attractions }, { label: '住宿', value: b?.total_hotels }, { label: '餐饮', value: b?.total_meals }, { label: '市内交通', value: b?.total_transportation }, { label: '城际交通', value: b?.total_inter_city_transport }, { label: '合计', value: b?.total }]
})
</script>

<style scoped>
.trip-export { width: 1000px; padding: 48px 56px; box-sizing: border-box; background: #fffdf8; color: #263d35; font: 16px/1.8 'Microsoft YaHei', sans-serif; overflow-wrap: anywhere; }
header { border-bottom: 3px solid #286852; padding-bottom: 24px; }
header span { font-size: 13px; letter-spacing: 2px; color: #6d7a72; }
h1 { font-size: 36px; margin: 12px 0; } h2 { font-size: 23px; margin: 0 0 16px; } h3 { font-size: 18px; margin: 0 0 6px; }
small { font-size: 15px; font-weight: normal; margin-left: 12px; color: #65736b; } p { margin: 6px 0; }
section { padding: 28px 0; border-bottom: 1px solid #dce3da; }
.budget { display: flex; flex-wrap: wrap; gap: 16px; } .budget p { width: 28%; } strong { display: block; font-size: 24px; }
.stop { padding: 16px 20px; margin: 12px 0; background: #f0f4ed; border-left: 3px solid #438568; }
.meta { color: #65736b; font-size: 14px; } .notes { margin-top: 18px; } footer { padding-top: 24px; color: #65736b; text-align: center; }
.export-markdown :deep(h1), .export-markdown :deep(h2), .export-markdown :deep(h3) { font-size: 18px; margin: 8px 0; }
</style>
