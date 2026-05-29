<template>
  <div class="swiper-slide" :class="{ 'swiper-slide-active': active }"
       @mouseenter="$emit('hover')" @focusin="$emit('hover')">
    <div class="slide-img">
      <img v-if="imageSrc" :src="imageSrc" :alt="item.name" loading="lazy" />
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
        <button class="show-more" @click.prevent="$emit('selectDay')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface OverviewAttractionItem {
  name: string
  description?: string
  visit_duration?: number
  ticket_price?: number
  reservation_required?: boolean
  dayNumber: number
  dayArrayIndex: number
  order: number
}

defineProps<{
  item: OverviewAttractionItem
  imageSrc: string
  active: boolean
}>()

defineEmits<{
  hover: []
  selectDay: []
}>()
</script>

<style scoped>
.swiper-slide {
  width: 12rem;
  height: 27rem;
  flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  background: var(--color-bg-card, #fff);
  box-shadow: 0 6px 24px rgba(0,0,0,0.12);
  transition: all 0.3s ease;
  cursor: pointer;
}

.slide-img {
  height: 18rem;
  width: 100%;
  overflow: hidden;
  position: relative;
  background: #1a262f;
  flex-shrink: 0;
}

.slide-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.45s ease;
}

.swiper-slide-active:hover .slide-img img {
  transform: scale(1.2) rotate(-5deg);
}

.slide-wave {
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 100%;
  height: 3rem;
  z-index: 1;
  color: var(--color-bg-card, #fff);
}

/* Placeholder when no image */
.img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a262f, #2d3a45);
  color: rgba(255,255,255,0.25);
  font-size: 1.5rem;
  font-weight: 700;
}

/* Content below image */
.slide-content {
  padding: 0 1.25rem;
  background: var(--color-bg-card, #fff);
  display: flex;
  flex-direction: column;
}

.slide-content > div {
  transform: translateY(-0.6rem);
}

.slide-content h2 {
  margin: 0 0 0.25rem;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.slide-content p {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-tertiary, #999);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Animated circular "show more" button */
.show-more {
  width: 3.25rem;
  border-radius: 50%;
  background: var(--color-primary, #f5593d);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-top: 0.5rem;
  opacity: 0;
  height: 0;
  padding: 0;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.swiper-slide-active:hover .show-more {
  opacity: 1;
  height: 3.25rem;
}

.show-more:hover {
  filter: brightness(1.1);
}

/* Dark mode */
[data-theme="dark"] .slide-img { background: #0d0d1a; }
[data-theme="dark"] .img-placeholder { background: linear-gradient(135deg, #0d0d1a, #1a1a2e); }
[data-theme="dark"] .slide-wave { color: var(--color-bg-card, #1e1840); }
</style>
