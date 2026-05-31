<template>
  <div class="result-container">
    <ResultHero
      v-if="tripPlan"
      :trip-plan="tripPlan"
      :is-saved="isSaved"
      :saving-trip="savingTrip"
      :edit-mode="editMode"
      @go-back="goBack"
      @save="handleSaveTrip"
      @edit="toggleEditMode"
      @save-changes="saveChanges"
      @cancel-edit="cancelEdit"
      @export-image="exportAsImage"
      @export-pdf="exportAsPDF"
    />

    <div v-if="tripPlan" class="tab-bar">
      <div class="tab-bar-inner">
        <button
          v-for="tab in visibleTabs"
          :key="tab.key"
          class="tab-pill"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <span class="tab-icon">{{ tab.icon }}</span>
          <span class="tab-label">{{ tab.label }}</span>
        </button>
      </div>
    </div>

    <div v-if="tripPlan" class="tab-content" ref="tabContentRef">
      <div v-show="activeTab === 'overview' || isExporting">
        <TabOverview
          :trip-plan="tripPlan"
          :attraction-photos="attractionPhotos"
          @go-to-day="(dayIdx: number) => { activeTab = 'itinerary'; activeDays = [dayIdx]; }"
        />
      </div>
      <Transition name="tab-fade" mode="out-in">
        <TabBudget v-if="(activeTab === 'budget' || isExporting) && tripPlan.budget" :budget="tripPlan.budget" :key="'budget'" />
      </Transition>
      <div v-show="activeTab === 'map' || isExporting">
        <TabMap
          ref="tabMapRef"
          :trip-plan="tripPlan"
          :attraction-photos="attractionPhotos"
          :visible="activeTab === 'map'"
        />
      </div>
      <Transition name="tab-fade" mode="out-in">
        <TabItinerary
          v-if="activeTab === 'itinerary' || isExporting"
          :trip-plan="tripPlan"
          :edit-mode="editMode"
          :attraction-photos="attractionPhotos"
          v-model:active-days="activeDays"
          @delete-attraction="deleteAttraction"
          @move-attraction="moveAttraction"
          :key="'itinerary'"
        />
      </Transition>
      <Transition name="tab-fade" mode="out-in">
        <TabGraph
          v-if="activeTab === 'graph' || isExporting"
          :trip-plan="tripPlan"
          :key="'graph'"
        />
      </Transition>
      <Transition name="tab-fade" mode="out-in">
        <TabWeather
          v-if="(activeTab === 'weather' || isExporting) && tripPlan.weather_info && tripPlan.weather_info.length > 0"
          :weather-info="tripPlan.weather_info"
          :key="'weather'"
        />
      </Transition>
    </div>

    <a-empty v-if="!tripPlan" description="没有找到旅行计划数据">
      <template #image>
        <div style="font-size: 80px;">🗺️</div>
      </template>
      <template #description>
        <span style="color: var(--color-text-tertiary);">暂无旅行计划数据,请先创建行程</span>
      </template>
      <a-button type="primary" @click="goBack">返回首页创建行程</a-button>
    </a-empty>

    <a-back-top :visibility-height="300">
      <div class="back-top-button">↑</div>
    </a-back-top>

    <AIChat :trip-plan="tripPlan" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import type { TripPlan } from '@/types'
import { saveTripToHistory, getTripDetail } from '@/services/api'
import ResultHero from '@/components/result/ResultHero.vue'
import TabOverview from '@/components/result/TabOverview.vue'
import TabBudget from '@/components/result/TabBudget.vue'
import TabMap from '@/components/result/TabMap.vue'
import TabItinerary from '@/components/result/TabItinerary.vue'
import TabWeather from '@/components/result/TabWeather.vue'
import TabGraph from '@/components/result/TabGraph.vue'
import AIChat from '@/components/AIChat.vue'

const router = useRouter()
const route = useRoute()

const tripPlan = ref<TripPlan | null>(null)
const editMode = ref(false)
const originalPlan = ref<TripPlan | null>(null)
const attractionPhotos = ref<Record<string, string>>({})
const activeTab = ref('overview')
const activeDays = ref<number[]>([0])
const isSaved = ref(false)
const savingTrip = ref(false)
const isExporting = ref(false)
const tabContentRef = ref<HTMLElement | null>(null)
const tabMapRef = ref<InstanceType<typeof TabMap> | null>(null)

const visibleTabs = computed(() => {
  const tabs = [{ key: 'overview', icon: '📋', label: '行程概览' }]
  if (tripPlan.value?.budget) tabs.push({ key: 'budget', icon: '💰', label: '预算明细' })
  tabs.push({ key: 'map', icon: '📍', label: '景点地图' })
  tabs.push({ key: 'itinerary', icon: '📅', label: '每日行程' })
  tabs.push({ key: 'graph', icon: '🔗', label: '知识图谱' })
  if (tripPlan.value?.weather_info?.length) tabs.push({ key: 'weather', icon: '🌤️', label: '天气信息' })
  return tabs
})

onMounted(async () => {
  const tripId = route.params.id
  if (tripId) {
    await loadTripFromHistory(Number(tripId))
  } else {
    const stored = sessionStorage.getItem('tripPlan')
    if (stored) {
      try {
        tripPlan.value = JSON.parse(stored)
      } catch (e) {
        console.error('sessionStorage tripPlan 解析失败:', e)
      }
    }
  }
  if (tripPlan.value) {
    await loadAttractionPhotos()
  }
})

const goBack = () => {
  router.push(route.params.id ? '/my-trips' : '/')
}

const loadTripFromHistory = async (tripId: number) => {
  try {
    const res = await getTripDetail(tripId)
    console.log('loadTripFromHistory 响应:', res)
    if (res.data?.plan) {
      tripPlan.value = res.data.plan
      isSaved.value = true
    } else if (res.data && !res.data.plan) {
      console.warn('行程数据缺少plan字段:', res.data)
      message.error('行程数据格式不正确，可能需要重新规划行程')
    } else {
      console.warn('行程响应异常:', res)
      message.error('行程数据格式不正确，可能需要重新规划行程')
    }
  } catch (error: any) {
    console.error('加载行程失败:', error)
    message.error('加载行程失败: ' + (error.response?.data?.detail || error.message || '未知错误'))
  }
}

const handleSaveTrip = async () => {
  if (!tripPlan.value) return
  savingTrip.value = true
  try {
    const formData = sessionStorage.getItem('tripFormData')
    const request = formData ? JSON.parse(formData) : undefined
    await saveTripToHistory(tripPlan.value, request)
    isSaved.value = true
    message.success('行程已保存到我的行程！')
  } catch (e: any) {
    message.error('保存失败：' + (e.message || '未知错误'))
  } finally {
    savingTrip.value = false
  }
}

const toggleEditMode = () => {
  editMode.value = true
  originalPlan.value = JSON.parse(JSON.stringify(tripPlan.value))
  activeTab.value = 'itinerary'
  message.info('进入编辑模式')
}

const saveChanges = () => {
  editMode.value = false
  if (tripPlan.value) {
    sessionStorage.setItem('tripPlan', JSON.stringify(tripPlan.value))
  }
  message.success('修改已保存')
  tabMapRef.value?.refreshMap()
}

const cancelEdit = () => {
  if (originalPlan.value) {
    tripPlan.value = JSON.parse(JSON.stringify(originalPlan.value))
  }
  editMode.value = false
  message.info('已取消编辑')
}

const deleteAttraction = (dayIndex: number, attrIndex: number) => {
  if (!tripPlan.value) return
  const day = tripPlan.value.days[dayIndex]
  if (day.attractions.length <= 1) {
    message.warning('每天至少需要保留一个景点')
    return
  }
  day.attractions.splice(attrIndex, 1)
  message.success('景点已删除')
}

const moveAttraction = (dayIndex: number, attrIndex: number, direction: 'up' | 'down') => {
  if (!tripPlan.value) return
  const day = tripPlan.value.days[dayIndex]
  const attractions = day.attractions
  if (direction === 'up' && attrIndex > 0) {
    [attractions[attrIndex], attractions[attrIndex - 1]] = [attractions[attrIndex - 1], attractions[attrIndex]]
  } else if (direction === 'down' && attrIndex < attractions.length - 1) {
    [attractions[attrIndex], attractions[attrIndex + 1]] = [attractions[attrIndex + 1], attractions[attrIndex]]
  }
}

const loadAttractionPhotos = async () => {
  if (!tripPlan.value) return
  const promises: Promise<void>[] = []
  tripPlan.value.days.forEach(day => {
    day.attractions.forEach(attraction => {
      const promise = fetch(`/api/poi/photo?name=${encodeURIComponent(attraction.name)}`)
        .then(res => res.json())
        .then(data => {
          if (data.success && data.data.photo_url) {
            attractionPhotos.value[attraction.name] = data.data.photo_url
          }
        })
        .catch(() => {})
      promises.push(promise)
    })
  })
  await Promise.all(promises)
}

const exportAsImage = async () => {
  try {
    message.loading({ content: '正在生成图片...', key: 'export', duration: 0 })
    isExporting.value = true
    await nextTick()
    const element = tabContentRef.value
    if (!element) throw new Error('未找到内容元素')
    const canvas = await html2canvas(element, { backgroundColor: '#f5f7fa', scale: 2, logging: false, useCORS: true, allowTaint: true })
    isExporting.value = false
    const link = document.createElement('a')
    link.download = `旅行计划_${tripPlan.value?.city}_${new Date().getTime()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
    message.success({ content: '图片导出成功!', key: 'export' })
  } catch (error: any) {
    isExporting.value = false
    message.error({ content: `导出图片失败: ${error.message}`, key: 'export' })
  }
}

const exportAsPDF = async () => {
  try {
    message.loading({ content: '正在生成PDF...', key: 'export', duration: 0 })
    isExporting.value = true
    await nextTick()
    const element = tabContentRef.value
    if (!element) throw new Error('未找到内容元素')
    const canvas = await html2canvas(element, { backgroundColor: '#f5f7fa', scale: 2, logging: false, useCORS: true, allowTaint: true })
    isExporting.value = false
    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
    const imgWidth = 210
    const imgHeight = (canvas.height * imgWidth) / canvas.width
    let heightLeft = imgHeight
    let position = 0
    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
    heightLeft -= 297
    while (heightLeft > 0) {
      position = heightLeft - imgHeight
      pdf.addPage()
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
      heightLeft -= 297
    }
    pdf.save(`旅行计划_${tripPlan.value?.city}_${new Date().getTime()}.pdf`)
    message.success({ content: 'PDF导出成功!', key: 'export' })
  } catch (error: any) {
    isExporting.value = false
    message.error({ content: `导出PDF失败: ${error.message}`, key: 'export' })
  }
}
</script>

<style scoped>
.result-container {
  min-height: 100vh;
  padding-top: 32px;
  background: var(--color-bg-secondary);
  transition: background var(--transition-normal);
}

.tab-bar {
  position: sticky;
  top: var(--header-height);
  z-index: 10;
  background: #ffffff;
  padding: 12px 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03), 0 2px 4px rgba(0, 0, 0, 0.02);
}

.tab-bar-inner {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  gap: 4px;
  justify-content: center;
}

.tab-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-family-base);
  cursor: pointer;
  transition: all 150ms linear;
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tab-pill:hover {
  background: rgba(245, 89, 61, 0.08);
  color: var(--color-primary);
}

.tab-pill.active {
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 4px 12px rgba(245, 89, 61, 0.3);
}

.tab-icon { font-size: 14px; }

.tab-content {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

.back-top-button {
  width: 40px;
  height: 40px;
  background: var(--color-primary);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(245, 89, 61, 0.3);
  cursor: pointer;
  transition: all 0.3s ease;
}

.back-top-button:hover {
  transform: scale(1.1);
}

@media (max-width: 768px) {
  .tab-bar { padding: 8px 12px; }
  .tab-bar-inner { overflow-x: auto; justify-content: flex-start; scrollbar-width: none; }
  .tab-bar-inner::-webkit-scrollbar { display: none; }
  .tab-content { padding: 16px 12px; }
}

@media (max-width: 480px) {
  .tab-pill { padding: 6px 12px; font-size: 12px; }
  .tab-label { display: none; }
}
</style>
