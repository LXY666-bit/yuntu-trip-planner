<template>
  <div class="my-trips-page">
    <div class="page-header">
      <h1 class="page-title">🗺️ 我的行程</h1>
      <p class="page-subtitle">查看和管理你的旅行计划</p>
    </div>

    <div class="toolbar">
      <div class="filter-pills">
        <button
          v-for="filter in filters"
          :key="filter.value"
          class="filter-pill"
          :class="{ active: currentFilter === filter.value }"
          @click="setFilter(filter.value)"
        >
          <span class="pill-icon">{{ filter.icon }}</span>
          <span class="pill-label">{{ filter.label }}</span>
        </button>
      </div>
      <div class="search-box">
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索城市、标题..."
          @search="handleSearch"
          style="width: 260px"
          allow-clear
        />
      </div>
    </div>

    <a-spin :spinning="loading" tip="加载中...">
      <div v-if="trips.length === 0 && !loading" class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-text">还没有行程记录</div>
        <div class="empty-hint">去首页创建你的第一个旅行计划吧！</div>
        <a-button type="primary" @click="goHome" size="large" class="empty-btn">
          ✨ 开始规划
        </a-button>
      </div>

      <div v-else class="trips-grid">
        <div
          v-for="(trip, idx) in trips"
          :key="trip.id"
          class="trip-card animate-fade-in-up"
          :class="`stagger-${Math.min(idx + 1, 8)}`"
          @click="viewTrip(trip)"
        >
          <div class="card-cover" :style="getCoverStyle(trip)">
            <div class="card-cover-overlay"></div>
            <div class="card-status-badge" :class="trip.status">
              {{ getStatusLabel(trip.status) }}
            </div>
            <div class="card-city">{{ trip.city }}</div>
          </div>
          <div class="card-body">
            <div class="card-title">{{ trip.title }}</div>
            <div class="card-meta">
              <span class="meta-item">📅 {{ formatDateRange(trip) }}</span>
              <span class="meta-item">⏱️ {{ trip.travel_days }}天</span>
            </div>
            <div class="card-meta">
              <span v-if="trip.total_cost" class="meta-item cost">💰 ¥{{ trip.total_cost }}</span>
              <span v-if="trip.companion_type" class="meta-item">{{ getCompanionLabel(trip.companion_type) }}</span>
            </div>
            <div v-if="trip.tags && trip.tags.length" class="card-tags">
              <span v-for="tag in trip.tags.slice(0, 3)" :key="tag" class="tag-pill">{{ tag }}</span>
            </div>
          </div>
          <div class="card-actions" @click.stop>
            <button
              class="action-btn"
              :class="{ 'fav-active': trip.status === 'favorite' }"
              @click="toggleFavorite(trip)"
              :title="trip.status === 'favorite' ? '取消收藏' : '收藏'"
            >
              {{ trip.status === 'favorite' ? '⭐' : '☆' }}
            </button>
            <button
              class="action-btn"
              @click="toggleArchive(trip)"
              :title="trip.status === 'archived' ? '取消归档' : '归档'"
            >
              {{ trip.status === 'archived' ? '📂' : '📁' }}
            </button>
            <a-popconfirm title="确定删除此行程？" @confirm="handleDelete(trip)" ok-text="删除" cancel-text="取消">
              <button class="action-btn danger" title="删除">🗑️</button>
            </a-popconfirm>
          </div>
        </div>
      </div>

      <div v-if="total > pageSize" class="pagination-wrapper">
        <a-pagination
          v-model:current="currentPage"
          :total="total"
          :page-size="pageSize"
          @change="handlePageChange"
          show-less-items
        />
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { TripRecord } from '@/types'
import { getTripList, deleteTripFromHistory, updateTripStatus, searchTrips } from '@/services/api'

const router = useRouter()

const trips = ref<TripRecord[]>([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(12)
const currentFilter = ref('')
const searchKeyword = ref('')

const filters = [
  { value: '', label: '全部', icon: '📋' },
  { value: 'favorite', label: '收藏', icon: '⭐' },
  { value: 'archived', label: '归档', icon: '📦' },
]

const setFilter = (value: string) => {
  currentFilter.value = value
  currentPage.value = 1
  searchKeyword.value = ''
  loadTrips()
}

const loadTrips = async () => {
  loading.value = true
  try {
    const res = await getTripList({
      status: currentFilter.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    trips.value = res.data
    total.value = res.total
  } catch (e: any) {
    message.error('加载行程列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = async (value: string) => {
  if (!value.trim()) {
    loadTrips()
    return
  }
  loading.value = true
  try {
    const res = await searchTrips(value, currentPage.value, pageSize.value)
    trips.value = res.data
    total.value = res.total
  } catch {
    message.error('搜索失败')
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadTrips()
}

const viewTrip = (trip: TripRecord) => {
  router.push(`/trip/${trip.id}`)
}

const goHome = () => { router.push('/') }

const toggleFavorite = async (trip: TripRecord) => {
  const newStatus = trip.status === 'favorite' ? 'completed' : 'favorite'
  try {
    await updateTripStatus(trip.id, newStatus)
    trip.status = newStatus as any
    message.success(newStatus === 'favorite' ? '已收藏' : '已取消收藏')
  } catch {
    message.error('操作失败')
  }
}

const toggleArchive = async (trip: TripRecord) => {
  const newStatus = trip.status === 'archived' ? 'completed' : 'archived'
  try {
    await updateTripStatus(trip.id, newStatus)
    trip.status = newStatus as any
    message.success(newStatus === 'archived' ? '已归档' : '已取消归档')
  } catch {
    message.error('操作失败')
  }
}

const handleDelete = async (trip: TripRecord) => {
  try {
    await deleteTripFromHistory(trip.id)
    message.success('行程已删除')
    loadTrips()
  } catch {
    message.error('删除失败')
  }
}

const getCoverStyle = (trip: TripRecord) => {
  if (trip.cover_image) {
    return { backgroundImage: `url(${trip.cover_image})` }
  }
  const colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a']
  const idx = trip.id % colors.length
  return { background: `linear-gradient(135deg, ${colors[idx]}, ${colors[(idx + 1) % colors.length]})` }
}

const formatDateRange = (trip: TripRecord) => `${trip.start_date} ~ ${trip.end_date}`

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = { completed: '已完成', favorite: '⭐ 收藏', archived: '📦 归档' }
  return map[status] || status
}

const getCompanionLabel = (type: string) => {
  const map: Record<string, string> = {
    solo: '🧑 独自', couple: '💑 情侣', family: '👨‍👩‍👧 亲子',
    friends: '👫 朋友', elderly: '👴 带老人', group: '👥 团队'
  }
  return map[type] || type
}

onMounted(loadTrips)
</script>

<style scoped>
.my-trips-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 24px;
}

.page-header {
  text-align: center;
  margin-bottom: 36px;
}

.page-title {
  font-size: 2em;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.page-subtitle {
  color: var(--color-text-tertiary);
  font-size: 14px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
  flex-wrap: wrap;
  gap: 16px;
}

.filter-pills {
  display: flex;
  gap: 8px;
}

.filter-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border: 1px solid var(--color-border);
  border-radius: 24px;
  background: var(--color-bg-card);
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms linear;
  font-family: var(--font-family-base);
}

.filter-pill:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.filter-pill.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
  box-shadow: 0 4px 12px rgba(245, 89, 61, 0.3);
}

.pill-icon {
  font-size: 14px;
}

.trips-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.trip-card {
  background: var(--color-bg-card);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: var(--shadow-md);
  cursor: pointer;
  transition: transform 300ms cubic-bezier(0.34, 2, 0.6, 1), box-shadow 200ms ease;
  position: relative;
  border: 0 none;
}

.trip-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-card-hover);
}

.card-cover {
  height: 140px;
  background-size: cover;
  background-position: center;
  position: relative;
  display: flex;
  align-items: flex-end;
  padding: 16px;
}

.card-cover-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.55) 0%, transparent 60%);
}

.card-status-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.92);
  color: #333;
  backdrop-filter: blur(4px);
}

.card-status-badge.favorite {
  background: rgba(251, 198, 88, 0.9);
  color: #8b6914;
}

.card-status-badge.archived {
  background: rgba(0, 0, 0, 0.08);
  color: var(--color-text-tertiary);
}

.card-city {
  position: relative;
  z-index: 1;
  color: #fff;
  font-size: 1.5em;
  font-weight: 700;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}

.card-body {
  padding: 16px;
}

.card-title {
  font-size: 1em;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-meta {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
  font-size: 13px;
  color: var(--color-text-tertiary);
}

.meta-item.cost {
  color: var(--color-primary);
  font-weight: 600;
}

.card-tags {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  padding: 8px 12px;
  border-top: 1px solid var(--color-border-light);
  gap: 4px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  transition: all 150ms linear;
}

.action-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  transform: scale(1.1);
}

.action-btn:active {
  transform: scale(0.95);
}

.action-btn.fav-active {
  color: var(--color-warning);
}

.action-btn.danger:hover {
  background: rgba(245, 89, 61, 0.1);
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.empty-text {
  font-size: 1.2em;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.empty-hint {
  color: var(--color-text-tertiary);
  font-size: 14px;
  margin-bottom: 24px;
}

.empty-btn {
  border-radius: 24px !important;
  height: 44px;
  padding: 0 32px;
  font-weight: 600;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 36px;
}

@media (max-width: 768px) {
  .my-trips-page {
    padding: 20px 12px;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-pills {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .search-box {
    width: 100%;
  }

  .search-box :deep(.ant-input-search) {
    width: 100% !important;
  }

  .trips-grid {
    grid-template-columns: 1fr;
  }
}
</style>
