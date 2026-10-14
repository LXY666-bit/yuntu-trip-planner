<template>
  <div class="swiper-slide" :class="{ 'swiper-slide-active': active }"
       >
    <div class="slide-img">
      <img v-if="imageSrc && !imageFailed" :src="imageSrc" :alt="item.name" loading="lazy" @error="imageFailed = true" />
      <div v-else class="img-placeholder">
        <span>{{ item.name.slice(0, 6) }}</span>
      </div>
      <svg class="slide-wave" viewBox="0 0 1440 120" preserveAspectRatio="none">
        <path d="M0,60 C240,120 480,0 720,60 C960,120 1200,0 1440,60 L1440,120 L0,120 Z" fill="currentColor"/>
      </svg>
    </div>
    <div class="slide-content">
      <div>
        <h2>{{ item.name }}</h2>
        <p>{{ item.description || '暂无描述' }}</p>
        <button :tabindex="active ? 0 : -1" :aria-label="`查看第 ${item.dayNumber} 天行程`" class="show-more" @click.prevent="$emit('selectDay')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
const imageFailed = ref(false)
export interface OverviewAttractionItem {
  name: string
  description?: string
  visit_duration?: number
  ticket_price?: number
  reservation_required?: boolean | null
  dayNumber: number
  dayArrayIndex: number
  order: number
}

const props = defineProps<{
  item: OverviewAttractionItem
  imageSrc: string
  active: boolean
}>()

watch(() => props.imageSrc, () => { imageFailed.value = false })

defineEmits<{
  hover: []
  selectDay: []
}>()
</script>

<style scoped>
.swiper-slide { width: 100%; height: 100%; border-radius: 14px; overflow: hidden; background: var(--color-bg-card); box-shadow: 0 16px 44px #0003; border: 1px solid var(--color-border-light); }
.slide-img { height: 68%; position: relative; overflow: hidden; background: var(--color-primary-soft); }
.slide-img img { width: 100%; height: 100%; object-fit: cover; transition: transform 650ms cubic-bezier(.2,.7,.2,1); }
.swiper-slide-active:hover .slide-img img { transform: scale(1.12) rotate(-2deg); }
.img-placeholder { height: 100%; display: grid; place-items: center; background: linear-gradient(135deg, var(--color-primary-soft), var(--color-bg-secondary)); color: var(--color-primary); font-size: 26px; }
.slide-wave { position: absolute; bottom: -1px; width: 100%; height: 38px; color: var(--color-bg-card); }
.slide-content { padding: 4px 20px 14px; position: relative; }
.slide-content h2 { font-size: 21px; margin: 0 0 7px; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.slide-content p { margin: 0; padding-right: 28px; font-size: 13px; line-height: 1.6; color: var(--color-text-secondary); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.show-more { position: absolute; right: 14px; bottom: 14px; width: 30px; height: 30px; display: grid; place-items: center; border: 0; border-radius: 50%; background: var(--color-primary); cursor: pointer; }
@media (prefers-reduced-motion: reduce) { .slide-img img { transition: none; } .swiper-slide-active:hover .slide-img img { transform: none; } }
</style>
