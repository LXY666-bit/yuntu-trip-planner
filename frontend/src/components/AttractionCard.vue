<template>
  <div class="attraction-card" :class="{ 'edit-mode': editMode }">
    <div class="attraction-image-wrapper">
      <img
        :src="imageUrl"
        :alt="attraction.name"
        class="attraction-image"
        @error="handleImageError"
      />
      <div class="attraction-badge">
        <span class="badge-number">{{ globalIndex }}</span>
      </div>
      <div v-if="attraction.ticket_price" class="price-tag">
        ¥{{ attraction.ticket_price }}
      </div>
      <div v-if="attraction.category" class="category-tag">
        {{ attraction.category }}
      </div>
    </div>
    <div class="attraction-body">
      <template v-if="editMode">
        <div class="edit-field">
          <label>地址</label>
          <a-input v-model:value="attraction.address" size="small" />
        </div>
        <div class="edit-field">
          <label>游览时长(分钟)</label>
          <a-input-number v-model:value="attraction.visit_duration" :min="10" :max="480" size="small" style="width: 100%" />
        </div>
        <div class="edit-field">
          <label>描述</label>
          <a-textarea v-model:value="attraction.description" :rows="2" size="small" />
        </div>
      </template>
      <template v-else>
        <h4 class="attraction-name">{{ attraction.name }}</h4>
        <div class="attraction-meta">
          <span v-if="attraction.rating" class="meta-item rating">
            <span class="star">★</span>{{ attraction.rating }}
          </span>
          <span class="meta-item">
            <span class="meta-icon">⏱</span>{{ attraction.visit_duration }}分钟
          </span>
        </div>
        <p class="attraction-address">{{ attraction.address }}</p>
        <p class="attraction-desc">{{ attraction.description }}</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Attraction } from '@/types'

const props = defineProps<{
  attraction: Attraction
  globalIndex: number
  editMode?: boolean
  photoUrl?: string
}>()

const gradientPairs = [
  ['#667eea', '#764ba2'], ['#4facfe', '#00f2fe'],
  ['#43e97b', '#38f9d7'], ['#f093fb', '#f5576c'], ['#fa709a', '#fee140'],
]

const fallbackSvg = computed(() => {
  const idx = props.globalIndex % gradientPairs.length
  const [start, end] = gradientPairs[idx]
  const name = props.attraction.name.slice(0, 6)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
    <defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:${start}"/><stop offset="100%" style="stop-color:${end}"/>
    </linearGradient></defs>
    <rect width="400" height="300" fill="url(#g)"/>
    <text x="200" y="140" text-anchor="middle" font-family="sans-serif" font-size="26" font-weight="bold" fill="white" opacity="0.9">${name}</text>
    <text x="200" y="175" text-anchor="middle" font-family="sans-serif" font-size="13" fill="white" opacity="0.6">图片加载中...</text>
  </svg>`
  return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`
})

const imageUrl = computed(() => {
  if (props.photoUrl) return props.photoUrl
  return fallbackSvg.value
})

// 图片加载失败计数, 第二次失败时永久切到 fallback
const errorCount = ref(0)
const handleImageError = (event: Event) => {
  const img = event.target as HTMLImageElement
  errorCount.value++
  if (errorCount.value <= 1 && props.photoUrl) {
    // 第一次失败: 重试一次 (可能网络抖动)
    setTimeout(() => { img.src = props.photoUrl + (props.photoUrl.includes('?') ? '&' : '?') + '_retry=' + Date.now() }, 1000)
  } else {
    // 第二次失败: 永久使用渐变色占位
    img.src = fallbackSvg.value
    img.onerror = null
  }
}
</script>

<style scoped>
.attraction-card {
  background: var(--color-bg-elevated);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-card);
  transition: all var(--transition-normal);
  border: 1px solid var(--color-border-light);
}

.attraction-card:hover {
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}

.attraction-image-wrapper {
  position: relative;
  overflow: hidden;
}

.attraction-image {
  width: 100%;
  height: 180px;
  object-fit: cover;
  transition: transform var(--transition-slow);
}

.attraction-card:hover .attraction-image {
  transform: scale(1.05);
}

.attraction-badge {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  background: var(--color-gradient);
  color: var(--color-text-inverse);
  width: 32px;
  height: 32px;
  border-radius: var(--radius-circle);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-sm);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.price-tag {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
  background: var(--color-error);
  color: var(--color-text-inverse);
  padding: 2px var(--space-2);
  border-radius: var(--radius-pill);
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-sm);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.category-tag {
  position: absolute;
  bottom: var(--space-2);
  left: var(--space-2);
  background: rgba(0, 0, 0, 0.5);
  color: var(--color-text-inverse);
  padding: 2px var(--space-2);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-xs);
  backdrop-filter: blur(4px);
}

.attraction-body {
  padding: var(--space-4);
}

.attraction-name {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--space-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attraction-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.meta-item.rating {
  color: #faad14;
}

.star {
  color: #faad14;
}

.meta-icon {
  font-size: var(--font-size-xs);
}

.attraction-address {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin: 0 0 var(--space-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attraction-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: 0;
  line-height: var(--line-height-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.edit-field {
  margin-bottom: var(--space-2);
}

.edit-field label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}
</style>
