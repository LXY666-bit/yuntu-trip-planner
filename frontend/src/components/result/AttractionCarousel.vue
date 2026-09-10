<template>
  <div class="attraction-carousel" role="region" aria-roledescription="轮播图" aria-label="景点概览" @keydown.left.prevent="step(-1)" @keydown.right.prevent="step(1)">
    <div ref="stage" class="carousel-stage" @pointermove="onPointerMove" @pointerleave="stopEdge" @pointerdown="onPointerDown" @pointerup="onPointerUp" @pointercancel="stopEdge">
      <div v-for="(item, index) in items" :key="`${item.dayArrayIndex}-${item.order}-${item.name}`" class="carousel-card" :class="{ centered: index === active }" :style="cardStyle(index)" :aria-hidden="Math.abs(offset(index)) > 3" @click="selectCard(index)">
        <OverviewAttractionCard :item="item" :image-src="photos[item.name] || ''" :active="index === active" @select-day="emit('selectDay', item.dayArrayIndex)" />
      </div>
    </div>
    <div class="carousel-controls">
      <button type="button" aria-label="上一个景点" :disabled="items.length < 2" @click="step(-1)">←</button>
      <span aria-live="polite" aria-atomic="true">{{ active + 1 }} / {{ items.length }} · {{ items[active]?.name }}</span>
      <button type="button" aria-label="下一个景点" :disabled="items.length < 2" @click="step(1)">→</button>
    </div>
    <p class="carousel-hint">移到两侧浏览景点 · 点击箭头查看当天行程</p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount, onMounted } from 'vue'
import OverviewAttractionCard, { type OverviewAttractionItem } from '@/components/OverviewAttractionCard.vue'
const props = defineProps<{ items: OverviewAttractionItem[]; photos: Record<string, string> }>()
const emit = defineEmits<{ selectDay: [dayIndex: number] }>()
const active = ref(0)
const stage = ref<HTMLElement | null>(null)
const width = ref(900)
let observer: ResizeObserver | undefined
let edgeTimer: ReturnType<typeof setInterval> | undefined
let direction = 0
let pointerStart: { x: number; y: number } | null = null
let swiped = false
function offset(index: number) {
  const n = props.items.length
  let d = index - active.value
  if (d > n / 2) d -= n
  if (d < -n / 2) d += n
  return d
}
function cardStyle(index: number) {
  const d = offset(index), distance = Math.abs(d)
  return { transform: `translateX(calc(-50% + ${d * Math.min(width.value * .21, 190)}px)) scale(${Math.max(.5, 1 - distance * .14)})`, zIndex: 10 - distance, opacity: distance > 3 ? 0 : 1, visibility: distance > 3 ? 'hidden' as const : 'visible' as const }
}
function step(amount: number) { if (props.items.length > 1) active.value = (active.value + amount + props.items.length) % props.items.length }
function stopEdge() { clearInterval(edgeTimer); edgeTimer = undefined; direction = 0 }
function onPointerMove(event: PointerEvent) {
  if (event.pointerType !== 'mouse' || event.buttons || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return stopEdge()
  const bounds = stage.value!.getBoundingClientRect()
  const ratio = (event.clientX - bounds.left) / bounds.width
  const next = ratio < .2 ? -1 : ratio > .8 ? 1 : 0
  if (next === direction) return
  stopEdge()
  if (next) { direction = next; edgeTimer = setInterval(() => { if (stage.value?.getClientRects().length) step(next); else stopEdge() }, 700) }
}
function onPointerDown(event: PointerEvent) { stopEdge(); swiped = false; pointerStart = { x: event.clientX, y: event.clientY } }
function onPointerUp(event: PointerEvent) {
  if (pointerStart && Math.abs(event.clientX - pointerStart.x) > 45 && Math.abs(event.clientX - pointerStart.x) > Math.abs(event.clientY - pointerStart.y)) { step(event.clientX < pointerStart.x ? 1 : -1); swiped = true }
  pointerStart = null
}
function selectCard(index: number) { if (!swiped) active.value = index; swiped = false }
watch(() => props.items.length, () => { active.value = Math.min(active.value, Math.max(0, props.items.length - 1)); stopEdge() })
onMounted(() => { observer = new ResizeObserver(entries => { if (entries[0]?.contentRect.width) width.value = entries[0].contentRect.width }); if (stage.value) observer.observe(stage.value) })
onBeforeUnmount(() => { stopEdge(); observer?.disconnect() })
</script>

<style scoped>
.carousel-stage { position: relative; height: 430px; overflow: hidden; touch-action: pan-y; }
.carousel-card { position: absolute; left: 50%; top: 22px; width: min(360px, 72%); height: 386px; transform-origin: center center; transition: transform 550ms cubic-bezier(.22,.68,.2,1), opacity 400ms; cursor: pointer; }
.carousel-card.centered { cursor: default; }
.carousel-controls { display: flex; align-items: center; justify-content: center; gap: 20px; margin-top: 8px; }
.carousel-controls button { width: 38px; height: 38px; border-radius: 50%; border: 1px solid var(--color-border-light); background: var(--color-bg-card); color: var(--color-text-primary); cursor: pointer; font-size: 20px; }
.carousel-controls button:hover { background: var(--color-primary-soft); }
.carousel-controls button:disabled { opacity: .35; cursor: default; }
.carousel-controls span { font-size: 13px; color: var(--color-text-secondary); max-width: 65%; text-align: center; }
.carousel-hint { text-align: center; font-size: 12px; color: var(--color-text-tertiary); margin: 12px 0 0; }
@media (max-width: 600px) { .carousel-stage { height: 350px; margin: 0 -16px; } .carousel-card { height: 318px; top: 16px; } .carousel-hint { display: none; } }
@media (prefers-reduced-motion: reduce) { .carousel-card { transition: none; } }
</style>
