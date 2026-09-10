<template>
  <div
    class="selectable-card-wrapper"
    :class="{ selected: attraction.selected }"
    role="checkbox" tabindex="0" :aria-checked="!!attraction.selected" :aria-label="attraction.name"
    @keydown.enter.prevent="$emit('toggle', attraction)"
    @keydown.space.prevent="$emit('toggle', attraction)"
    @click="$emit('toggle', attraction)"
  >
    <div class="selection-checkbox">
      <div class="checkbox-inner" :class="{ checked: attraction.selected }">
        <span v-if="attraction.selected" class="check-icon">✓</span>
      </div>
    </div>
    <div v-if="attraction.manuallyAdded" class="manual-badge">手动添加</div>
    <div v-if="attraction.aiPick" class="ai-badge" :class="`ai-badge-${attraction.aiPick}`">
      {{ attraction.aiPick === 'must' ? '⭐ 必去' : '💡 备选' }}
    </div>
    <div class="card-content">
      <div class="card-image">
        <img v-if="imageUrl && !imageFailed" :src="imageUrl" alt="" loading="lazy" @error="imageFailed = true" />
        <div v-else class="image-placeholder" aria-hidden="true"><span>{{ attraction.category || '发现风景' }}</span><strong>{{ attraction.name.slice(0, 6) }}</strong><i>YUNTU · NEXT STOP</i></div>
        <div v-if="attraction.ticket_price" class="price-tag">¥{{ attraction.ticket_price }}</div>
        <div v-if="attraction.category" class="category-tag">{{ attraction.category }}</div>
      </div>
      <div class="card-body">
        <h4 class="card-name">{{ attraction.name }}</h4>
        <div class="card-meta">
          <span v-if="attraction.rating" class="rating">
            <span class="star">★</span> {{ attraction.rating }}
          </span>
          <span v-if="attraction.visit_minutes" class="duration">约 {{ formatMinutes(attraction.visit_minutes) }}</span>
          <span v-if="attraction.address" class="address">{{ attraction.address }}</span>
        </div>
        <p v-if="attraction.description" class="card-desc">{{ attraction.description }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DiscoveredAttraction } from '@/types'
import { formatMinutes } from '@/composables/useFormat'

const props = defineProps<{
  attraction: DiscoveredAttraction
  photoUrl?: string
}>()

defineEmits<{
  toggle: [attraction: DiscoveredAttraction]
}>()

const imageFailed = ref(false)
const imageUrl = computed(() => props.photoUrl || props.attraction.image_url || '')
watch(imageUrl, () => { imageFailed.value = false })
</script>

<style scoped>
.selectable-card-wrapper {
  position: relative;
  border-radius: var(--radius-lg, 12px);
  background: var(--color-bg-elevated, #fff);
  border: 2px solid transparent;
  box-shadow: var(--shadow-card, 0 2px 8px rgba(0,0,0,0.08));
  cursor: pointer;
  transition: all var(--transition-normal, 0.3s) ease;
  overflow: hidden;
}

.selectable-card-wrapper:hover {
  box-shadow: var(--shadow-card-hover, 0 4px 16px rgba(0,0,0,0.12));
  transform: translateY(-2px);
}

.selectable-card-wrapper.selected {
  border-color: var(--color-primary, #667eea);
  box-shadow: 0 0 0 1px var(--color-primary, #667eea), var(--shadow-card-hover, 0 4px 16px rgba(0,0,0,0.12));
}

.selection-checkbox {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
}

.checkbox-inner {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.8);
  background: rgba(0,0,0,0.2);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.checkbox-inner.checked {
  background: var(--color-primary, #667eea);
  border-color: var(--color-primary, #667eea);
}

.check-icon {
  color: white;
  font-size: 14px;
  font-weight: bold;
}

.manual-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  padding: 2px 8px;
  border-radius: var(--radius-pill, 9999px);
  background: var(--color-accent, #764ba2);
  color: white;
  font-size: 11px;
}

.ai-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  padding: 2px 8px;
  border-radius: var(--radius-pill, 9999px);
  color: white;
  font-size: 11px;
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
}

.ai-badge-must {
  background: linear-gradient(135deg, #f5593d, #f7765f);
}

.ai-badge-optional {
  background: linear-gradient(135deg, #4a90d9, #51bcda);
}

/* 同时有"手动添加"角标时错开位置，避免重叠 */
.manual-badge + .ai-badge {
  top: 34px;
}

.duration {
  flex: none;
  color: var(--color-text-tertiary, #999);
}

.card-image {
  width: 100%;
  height: 140px;
  background-size: cover;
  background-position: center;
  position: relative;
}

.price-tag {
  position: absolute;
  top: 36px;
  right: 8px;
  padding: 2px 8px;
  border-radius: var(--radius-sm, 6px);
  background: rgba(245, 87, 108, 0.9);
  color: white;
  font-size: 12px;
  font-weight: 600;
}

.category-tag {
  position: absolute;
  bottom: 8px;
  left: 8px;
  padding: 2px 8px;
  border-radius: var(--radius-pill, 9999px);
  background: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
  color: white;
  font-size: 11px;
}

.card-body {
  padding: 10px 12px;
}

.card-name {
  margin: 0;
  font-size: var(--font-size-sm, 14px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.star {
  color: #faad14;
}

.address {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.card-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-tertiary);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.selectable-card-wrapper { border: 1px solid var(--color-border-light); border-radius: 13px; box-shadow: 0 2px 6px rgba(23,53,43,.025); transition: transform 180ms ease, box-shadow 180ms ease; }
.selectable-card-wrapper.selected { border-color: var(--color-primary); box-shadow: 0 0 0 1px var(--color-primary); }
.selectable-card-wrapper:hover { box-shadow: 0 6px 18px rgba(23,53,43,.08); }
.card-image { height: 155px; background: var(--color-bg-secondary); overflow: hidden; }
.card-image > img { width: 100%; height: 100%; object-fit: cover; }
.image-placeholder { height: 100%; padding: 30px 20px; color: var(--color-primary); background: linear-gradient(145deg, var(--color-primary-soft), transparent); display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 8px; }
.image-placeholder > span { font-size: 9px; letter-spacing: 2px; opacity: .7; }
.image-placeholder strong { font-size: 22px; font-weight: 500; letter-spacing: 2px; }
.image-placeholder i { font-size: 8px; font-style: normal; letter-spacing: 2px; opacity: .5; }
.card-body { padding: 15px; }
.card-name { font-size: 15px; }
.card-desc { line-height: 1.7; margin-top: 9px; min-height: 40px; }
.category-tag { background: var(--color-glass-bg); color: var(--color-text-primary); border-radius: 5px; font-size: 10px; }
.ai-badge-must { background: #ce785b; }
.ai-badge-optional { background: #557b69; }
.ai-badge, .manual-badge { box-shadow: none; border-radius: 5px; }
.selection-checkbox, .manual-badge, .ai-badge { z-index: 2; }
.price-tag { background: var(--color-glass-bg); color: var(--color-text-primary); }
@media (max-width: 600px) { .card-image { height: 126px; } .card-body { padding: 12px; } .card-name { font-size: 14px; } .image-placeholder { padding: 22px 12px; } .image-placeholder strong { font-size: 17px; } }
</style>
