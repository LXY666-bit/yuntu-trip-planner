<template>
  <div class="discover-page">
    <!-- 顶部导航 -->
    <header class="discover-header">
      <div class="header-content">
        <button class="back-btn" @click="goBack">← 返回</button>
        <h2 class="header-title">{{ formData?.city }} · 景点发现</h2>
        <div class="header-info">{{ formData?.travel_days }}天行程</div>
      </div>
    </header>

    <!-- 阶段1: 景点发现与选择 -->
    <div v-if="phase === 'discover'" class="discover-layout">
      <!-- 左侧: 景点列表 -->
      <div class="left-panel">
        <!-- 搜索栏 -->
        <div class="search-bar">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="手动搜索添加景点..."
            :loading="searching"
            @search="handleManualSearch"
          />
        </div>

        <!-- 搜索结果下拉 -->
        <div v-if="searchResults.length > 0" class="search-results-dropdown">
          <div
            v-for="result in searchResults"
            :key="result.name + (result.poi_id || '')"
            class="search-result-item"
            @click="addSearchResult(result)"
          >
            <span class="result-name">{{ result.name }}</span>
            <span class="result-address">{{ result.address }}</span>
            <span class="result-add">+ 添加</span>
          </div>
          <div class="search-results-close" @click="searchResults = []">关闭</div>
        </div>

        <!-- 分类过滤 -->
        <div class="category-filters">
          <button
            v-for="cat in categories"
            :key="cat"
            class="filter-btn"
            :class="{ active: activeCategory === cat }"
            @click="activeCategory = cat"
          >
            {{ cat }}
          </button>
        </div>

        <!-- 加载进度 -->
        <div v-if="loading" class="loading-bar">
          <div class="loading-text">{{ loadingMessage }}</div>
          <a-progress :percent="loadingProgress" :show-info="false" size="small" />
        </div>

        <!-- 景点卡片网格 -->
        <div class="attractions-grid">
          <SelectableAttractionCard
            v-for="attr in filteredAttractions"
            :key="attr.name + (attr.poi_id || '')"
            :attraction="attr"
            :photo-url="attractionPhotos[attr.name]"
            :ref="(el: any) => { if (el) cardRefs[attr.name] = el }"
            @toggle="toggleAttraction"
          />
          <div v-if="!loading && filteredAttractions.length === 0" class="empty-state">
            <p>{{ attractions.length === 0 ? '正在搜索景点...' : '该分类下暂无景点' }}</p>
          </div>
        </div>
      </div>

      <!-- 右侧: 地图 -->
      <div class="right-panel">
        <DiscoveryMap
          ref="mapRef"
          :attractions="attractions"
          :highlighted-name="highlightedAttraction"
          @marker-click="handleMarkerClick"
        />
      </div>

      <!-- 底部操作栏 -->
      <div class="bottom-bar">
        <div class="selection-info">
          已选择 <strong>{{ selectedCount }}</strong> 个景点
          <span v-if="selectedCount < 2" class="hint">（至少选择2个景点）</span>
        </div>
        <a-button
          type="primary"
          size="large"
          :disabled="selectedCount < 2"
          @click="startDayAssignment"
        >
          开始规划 ({{ selectedCount }}个景点) →
        </a-button>
      </div>
    </div>

    <!-- 阶段2: 日程分配 -->
    <div v-else-if="phase === 'assign'" class="assign-layout">
      <div class="assign-header">
        <h3>调整日程分配</h3>
        <p>拖拽景点到不同天数以调整安排，或直接确认系统推荐的分配方案</p>
      </div>

      <div class="day-columns">
        <div
          v-for="(day, dayIdx) in dayAssignments"
          :key="dayIdx"
          class="day-column"
        >
          <div class="day-header">第 {{ dayIdx + 1 }} 天</div>
          <draggable
            v-model="dayAssignments[dayIdx]"
            group="days"
            item-key="name"
            class="day-attractions"
            ghost-class="draggable-ghost"
            :animation="200"
          >
            <template #item="{ element: attr }">
              <div class="draggable-mini-card">
                <span class="mini-card-name">{{ attr.name }}</span>
                <span v-if="attr.category" class="mini-card-tag">{{ attr.category }}</span>
              </div>
            </template>
          </draggable>
          <div v-if="day.length === 0" class="day-empty">拖拽景点到此处</div>
        </div>
      </div>

      <div class="assign-actions">
        <a-button @click="phase = 'discover'">← 返回选择</a-button>
        <a-button type="primary" size="large" @click="confirmAndPlan">
          确认并生成行程 →
        </a-button>
      </div>
    </div>

    <!-- 阶段3: 规划中 -->
    <div v-else-if="phase === 'planning'" class="planning-layout">
      <div class="planning-container">
        <h3>正在生成行程计划...</h3>
        <PlanProgress
          :steps="planningSteps"
          :current-node="planningCurrentNode"
          :completed-nodes="planningCompletedNodes"
          :current-message="planningMessage"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import draggable from 'vuedraggable'
import SelectableAttractionCard from '@/components/SelectableAttractionCard.vue'
import DiscoveryMap from '@/components/DiscoveryMap.vue'
import PlanProgress from '@/components/PlanProgress.vue'
import { discoverAttractionsStream, searchAttractionManual, planFromSelectionsStream } from '@/services/api'
import type { StreamEvent } from '@/services/api'
import type { DiscoveredAttraction, TripFormData, DiscoveryStreamEvent } from '@/types'

const router = useRouter()

const formData = ref<TripFormData | null>(null)
const attractions = reactive<DiscoveredAttraction[]>([])
const attractionPhotos = ref<Record<string, string>>({})
const weatherInfo = ref('')
const loading = ref(true)
const loadingMessage = ref('正在搜索景点...')
const loadingProgress = ref(0)
const searchKeyword = ref('')
const searching = ref(false)
const searchResults = ref<DiscoveredAttraction[]>([])
const activeCategory = ref('全部')
const highlightedAttraction = ref('')
const phase = ref<'discover' | 'assign' | 'planning'>('discover')
const dayAssignments = ref<DiscoveredAttraction[][]>([])
const cardRefs: Record<string, any> = {}
const mapRef = ref<any>(null)

// Planning phase state
const planningCurrentNode = ref('')
const planningCompletedNodes = ref<Set<string>>(new Set())
const planningMessage = ref('')
const planningSteps = [
  { key: 'cluster_from_selections', label: '📊 聚类分析景点' },
  { key: 'search_food', label: '🍜 搜索美食' },
  { key: 'search_hotel', label: '🏨 搜索酒店' },
  { key: 'plan_route', label: '🗺️ 规划路线' },
  { key: 'macro_planner', label: '🏗️ 编排行程骨架' },
  { key: 'day_plan_subgraph', label: '📝 生成每日行程' },
  { key: 'reduce_assemble', label: '🔧 合并行程数据' },
  { key: 'global_synthesizer', label: '💡 生成全局建议' },
]

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

function loadPhotoForAttraction(name: string) {
  if (attractionPhotos.value[name]) return
  const city = formData.value?.city || ''
  fetch(`${API_BASE_URL}/api/poi/photo?name=${encodeURIComponent(name)}&city=${encodeURIComponent(city)}`)
    .then(res => res.json())
    .then(data => {
      if (data.data?.photo_url) {
        attractionPhotos.value[name] = data.data.photo_url
      }
    })
    .catch(() => {})
}

const categories = computed(() => {
  const cats = new Set<string>()
  cats.add('全部')
  for (const a of attractions) {
    if (a.category) cats.add(a.category)
  }
  return Array.from(cats)
})

const filteredAttractions = computed(() => {
  if (activeCategory.value === '全部') return attractions
  return attractions.filter(a => a.category === activeCategory.value)
})

const selectedCount = computed(() => attractions.filter(a => a.selected).length)

function goBack() {
  router.push('/')
}

function toggleAttraction(attr: DiscoveredAttraction) {
  const found = attractions.find(a => a.name === attr.name)
  if (found) {
    found.selected = !found.selected
  }
}

function handleMarkerClick(attr: DiscoveredAttraction) {
  highlightedAttraction.value = attr.name
  const cardEl = cardRefs[attr.name]?.$el
  if (cardEl) {
    cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

async function handleManualSearch() {
  if (!searchKeyword.value.trim() || !formData.value) return
  searching.value = true
  try {
    const result = await searchAttractionManual(searchKeyword.value.trim(), formData.value.city)
    if (result.success && result.data.length > 0) {
      const existingNames = new Set(attractions.map(a => a.name))
      searchResults.value = result.data.filter(a => !existingNames.has(a.name))
      if (searchResults.value.length === 0) {
        message.info('搜索到的景点已在列表中')
      }
    } else {
      message.info('未搜索到相关景点')
      searchResults.value = []
    }
  } catch (e: any) {
    message.error('搜索失败: ' + (e.message || '未知错误'))
  } finally {
    searching.value = false
  }
}

function addSearchResult(attr: DiscoveredAttraction) {
  attr.selected = true
  attr.manuallyAdded = true
  attractions.push(attr)
  searchResults.value = searchResults.value.filter(a => a.name !== attr.name)
  message.success(`已添加: ${attr.name}`)
}

function startDayAssignment() {
  const selected = attractions.filter(a => a.selected)
  if (selected.length < 2) return

  const days = formData.value?.travel_days || 1
  const perDay = Math.ceil(selected.length / days)
  const assignments: DiscoveredAttraction[][] = []
  for (let d = 0; d < days; d++) {
    assignments.push(selected.slice(d * perDay, (d + 1) * perDay))
  }
  dayAssignments.value = assignments
  phase.value = 'assign'
}

async function confirmAndPlan() {
  if (!formData.value) return

  const hasEmpty = dayAssignments.value.some(d => d.length === 0)
  if (hasEmpty) {
    message.warning('每天至少需要安排一个景点')
    return
  }

  phase.value = 'planning'
  planningCurrentNode.value = ''
  planningCompletedNodes.value = new Set()
  planningMessage.value = ''

  const selected = attractions.filter(a => a.selected)

  try {
    await planFromSelectionsStream(
      {
        request: formData.value,
        selected_attractions: selected.map(a => ({
          name: a.name,
          description: a.description,
          address: a.address,
          category: a.category,
          rating: a.rating,
          ticket_price: a.ticket_price,
          image_url: a.image_url,
          location: a.location,
          poi_id: a.poi_id,
        })),
        day_assignments: dayAssignments.value.map(day =>
          day.map(a => ({
            name: a.name,
            description: a.description,
            address: a.address,
            category: a.category,
            rating: a.rating,
            ticket_price: a.ticket_price,
            image_url: a.image_url,
            location: a.location,
            poi_id: a.poi_id,
          }))
        ),
        weather_info: weatherInfo.value,
      },
      (event: StreamEvent) => {
        if (event.type === 'node_complete' && event.node) {
          planningCompletedNodes.value = new Set([...planningCompletedNodes.value, event.node])
          planningCurrentNode.value = event.node
          planningMessage.value = event.message
        } else if (event.type === 'complete' && event.data) {
          sessionStorage.setItem('tripPlan', JSON.stringify(event.data))
          message.success('行程计划生成完成!')
          setTimeout(() => router.push('/result'), 500)
        } else if (event.type === 'error') {
          message.error(event.message || '规划失败')
          phase.value = 'assign'
        }
      }
    )
  } catch (e: any) {
    message.error('规划失败: ' + (e.message || '未知错误'))
    phase.value = 'assign'
  }
}

async function startDiscovery() {
  if (!formData.value) return

  loading.value = true
  loadingProgress.value = 5
  loadingMessage.value = '正在搜索景点...'

  try {
    await discoverAttractionsStream(
      formData.value,
      (event: DiscoveryStreamEvent) => {
        if (event.type === 'attraction' && event.data) {
          event.data.selected = false
          event.data.manuallyAdded = false
          attractions.push(event.data)
          if (!event.data.image_url) {
            loadPhotoForAttraction(event.data.name)
          }
        } else if (event.type === 'weather' && event.data) {
          weatherInfo.value = event.data
        } else if (event.type === 'progress') {
          loadingProgress.value = event.progress || 0
          loadingMessage.value = event.message || ''
        } else if (event.type === 'complete') {
          loading.value = false
          loadingProgress.value = 100
          const total = attractions.length
          message.success(`发现 ${total} 个景点，请选择您感兴趣的景点`)
        } else if (event.type === 'error') {
          loading.value = false
          message.error(event.message || '景点发现失败')
        }
      }
    )
  } catch (e: any) {
    loading.value = false
    message.error('景点发现失败: ' + (e.message || '未知错误'))
  }
}

onMounted(() => {
  const stored = sessionStorage.getItem('tripFormData')
  if (stored) {
    try {
      formData.value = JSON.parse(stored)
      startDiscovery()
    } catch {
      message.error('表单数据解析失败')
      router.push('/')
    }
  } else {
    message.error('未找到旅行表单数据')
    router.push('/')
  }
})
</script>

<style scoped>
/* ===== 页面底色: 柔和渐变 + 装饰光斑 ===== */
.discover-page {
  min-height: 100vh;
  padding-top: 64px;
  background:
    radial-gradient(ellipse 160% 60% at 20% 0%, rgba(102, 126, 234, 0.06) 0%, transparent 60%),
    radial-gradient(ellipse 140% 50% at 80% 30%, rgba(118, 75, 162, 0.04) 0%, transparent 55%),
    radial-gradient(ellipse 100% 40% at 50% 80%, rgba(102, 126, 234, 0.03) 0%, transparent 50%),
    var(--color-bg-primary);
}

/* ===== 头部: 玻璃拟态 ===== */
.discover-header {
  position: sticky;
  top: 64px;
  z-index: var(--z-sticky);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--color-border-light);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

[data-theme="dark"] .discover-header {
  background: rgba(26, 21, 48, 0.9);
}

.header-content {
  max-width: 1100px;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  background: var(--color-primary-soft);
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-primary);
  padding: 6px 16px;
  border-radius: 24px;
  font-weight: 600;
  font-family: var(--font-family-base);
  transition: all 150ms linear;
}

.back-btn:hover {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.header-title {
  margin: 0;
  font-size: 1.1em;
  font-weight: 600;
  color: var(--color-text-primary);
  flex: 1;
}

.header-info {
  font-size: 13px;
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.header-info {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-inverse);
  background: var(--color-gradient);
  padding: var(--space-1) var(--space-4);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-button);
}

/* ===== 发现布局 ===== */
.discover-layout {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-4) var(--space-6);
  padding-bottom: 80px;
  display: flex;
  gap: var(--space-5);
  min-height: calc(100vh - 64px);
}

.left-panel {
  flex: 6;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.right-panel {
  flex: 4;
  position: sticky;
  top: 130px;
  height: calc(100vh - 146px);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-elevated);
  border: 1px solid var(--color-border-light);
}

/* ===== 搜索栏 ===== */
.search-bar {
  max-width: 420px;
}

.search-bar :deep(.ant-input-affix-wrapper) {
  border-radius: var(--radius-pill) !important;
  border: 1.5px solid var(--color-border-strong) !important;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.06);
  transition: all var(--transition-fast);
}

.search-bar :deep(.ant-input-affix-wrapper:hover) {
  border-color: var(--color-primary) !important;
}

.search-bar :deep(.ant-input-affix-wrapper:focus-within) {
  border-color: var(--color-primary) !important;
  box-shadow: 0 0 0 3px var(--color-primary-bg), 0 4px 12px rgba(102, 126, 234, 0.1) !important;
}

.search-results-dropdown {
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-elevated);
  max-height: 240px;
  overflow-y: auto;
}

.search-result-item {
  padding: var(--space-2) var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light);
  transition: background var(--transition-fast);
}

.search-result-item:hover {
  background: var(--color-primary-bg);
}

.result-name {
  font-weight: var(--font-weight-medium);
  flex-shrink: 0;
  color: var(--color-text-primary);
}

.result-address {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.result-add {
  color: var(--color-primary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;
  padding: 2px var(--space-2);
  border-radius: var(--radius-pill);
  background: var(--color-primary-bg);
  transition: all var(--transition-fast);
}

.search-result-item:hover .result-add {
  background: var(--color-primary);
  color: var(--color-text-inverse);
}

.search-results-close {
  padding: var(--space-2);
  text-align: center;
  color: var(--color-text-tertiary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: color var(--transition-fast);
}

.search-results-close:hover {
  color: var(--color-primary);
}

/* ===== 分类过滤 ===== */
.category-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.filter-btn {
  padding: var(--space-1) var(--space-4);
  border: 1.5px solid var(--color-border-strong);
  border-radius: var(--radius-pill);
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  transition: all var(--transition-fast);
}

.filter-btn:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
  background: var(--color-primary-bg);
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.12);
}

.filter-btn.active {
  background: var(--color-gradient);
  border-color: transparent;
  color: var(--color-text-inverse);
  box-shadow: var(--shadow-button);
  transform: translateY(-1px);
}

.filter-btn:active {
  transform: scale(0.96);
}

/* ===== 加载条 ===== */
.loading-bar {
  padding: var(--space-3) var(--space-4);
  background: var(--color-primary-bg);
  border-radius: var(--radius-md);
  border: 1px solid rgba(102, 126, 234, 0.1);
}

.loading-text {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-primary-dark);
  margin-bottom: var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.loading-text::before {
  content: '✨';
  animation: pulse 2s ease-in-out infinite;
}

.loading-bar :deep(.ant-progress-bg) {
  background: var(--color-gradient) !important;
}

.attractions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-4);
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: var(--space-16) var(--space-10);
  color: var(--color-text-tertiary);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-lg);
  border: 2px dashed var(--color-border);
  font-size: var(--font-size-md);
}

/* ===== 底部操作栏: 玻璃拟态 ===== */
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: var(--z-sticky);
  background: var(--color-glass-bg);
  backdrop-filter: blur(var(--blur-glass));
  -webkit-backdrop-filter: blur(var(--blur-glass));
  border-top: 1px solid var(--color-glass-border);
  box-shadow: 0 -4px 20px rgba(102, 126, 234, 0.08);
  padding: var(--space-3) var(--space-6);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.selection-info {
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.selection-info strong {
  color: var(--color-primary);
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  min-width: 28px;
  text-align: center;
}

.hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin-left: var(--space-1);
}

.bottom-bar :deep(.ant-btn-primary) {
  border-radius: var(--radius-pill) !important;
  background: var(--color-gradient) !important;
  border: none !important;
  box-shadow: var(--shadow-button) !important;
  font-weight: var(--font-weight-semibold);
  padding: 0 var(--space-8);
  transition: all var(--transition-normal);
}

.bottom-bar :deep(.ant-btn-primary:hover:not(:disabled)) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-button-hover) !important;
}

.bottom-bar :deep(.ant-btn-primary:active:not(:disabled)) {
  transform: translateY(0) scale(0.98);
}

/* ===== 日程分配阶段 ===== */
.assign-layout {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-6);
}

.assign-header {
  text-align: center;
  margin-bottom: var(--space-6);
}

.assign-header h3 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  background: var(--color-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.assign-header p {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
}

.day-columns {
  display: flex;
  gap: var(--space-4);
  overflow-x: auto;
  padding-bottom: var(--space-4);
}

.day-column {
  flex: 1;
  min-width: 200px;
  background: var(--color-bg-elevated);
  border-radius: var(--radius-lg);
  border: 2px dashed var(--color-border-strong);
  padding: 0;
  min-height: 240px;
  overflow: hidden;
  transition: all var(--transition-normal);
  box-shadow: var(--shadow-card);
}

.day-column:hover {
  border-color: var(--color-primary);
  border-style: solid;
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}

.day-header {
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-md);
  color: var(--color-text-inverse);
  padding: var(--space-3) var(--space-4);
  background: var(--color-gradient);
  letter-spacing: 0.02em;
}

.day-attractions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
}

.draggable-mini-card {
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  cursor: grab;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  transition: all var(--transition-fast);
  border-left: 3px solid var(--color-primary-light);
}

.draggable-ghost {
  opacity: 0.4;
  background: var(--color-primary-bg);
  border: 2px dashed var(--color-primary);
}

.draggable-mini-card:hover {
  background: var(--color-primary-bg);
  border-left-color: var(--color-primary);
  transform: translateX(3px);
  box-shadow: var(--shadow-card);
}

.draggable-mini-card:active {
  cursor: grabbing;
  box-shadow: var(--shadow-elevated);
  transform: scale(1.02);
}

.mini-card-name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  flex: 1;
}

.mini-card-tag {
  font-size: var(--font-size-xs);
  padding: 1px var(--space-2);
  border-radius: var(--radius-pill);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
}

.day-empty {
  padding: var(--space-8) var(--space-5);
  text-align: center;
  color: var(--color-text-disabled);
  font-size: var(--font-size-sm);
  border: 2px dashed var(--color-border-light);
  border-radius: var(--radius-md);
  margin: var(--space-3);
}

.assign-actions {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

.assign-actions :deep(.ant-btn-primary) {
  border-radius: var(--radius-pill) !important;
  background: var(--color-gradient) !important;
  border: none !important;
  box-shadow: var(--shadow-button) !important;
  font-weight: var(--font-weight-semibold);
  padding: 0 var(--space-8);
}

.assign-actions :deep(.ant-btn-primary:hover) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-button-hover) !important;
}

.planning-layout {
  max-width: 600px;
  margin: 0 auto;
  padding: var(--space-16) var(--space-6);
}

.planning-container h3 {
  text-align: center;
  margin-bottom: var(--space-6);
  font-size: var(--font-size-xl);
  color: var(--color-text-primary);
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .discover-layout {
    flex-direction: column;
    padding: var(--space-3);
  }

  .right-panel {
    position: relative;
    top: 0;
    height: 300px;
    order: -1;
  }

  .attractions-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--space-2);
  }

  .header-title {
    font-size: var(--font-size-lg);
  }

  .day-columns {
    flex-direction: column;
  }

  .day-column {
    min-width: auto;
    min-height: 120px;
  }

  .bottom-bar {
    padding: var(--space-2) var(--space-4);
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .selection-info {
    font-size: var(--font-size-sm);
  }
}
</style>
