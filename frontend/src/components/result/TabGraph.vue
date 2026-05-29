<template>
  <div class="tab-graph">
    <div class="graph-chart" ref="graphChartRef"></div>
    <div v-if="!hasData" class="graph-empty">
      <div class="empty-icon">🔗</div>
      <p>暂无知识图谱数据</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import type { TripPlan } from '@/types'

const props = defineProps<{
  tripPlan: TripPlan
}>()

const graphChartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const hasData = computed(() => {
  return props.tripPlan?.days?.length > 0
})

function buildGraphData(): { nodes: any[]; edges: any[]; categories: any[] } {
  const nodes: any[] = []
  const edges: any[] = []
  const nodeIds = new Set<string>()

  const categories = [
    { name: '城市' }, { name: '日程' }, { name: '景点' },
    { name: '酒店' }, { name: '餐饮' }, { name: '天气' },
    { name: '预算' }, { name: '建议' }
  ]

  const nodeColors: Record<string, string> = {
    '城市': '#4A90D9', '日程': '#5B8FF9', '景点': '#5AD8A6',
    '酒店': '#F6BD16', '餐饮': '#E8684A', '天气': '#6DC8EC',
    '预算': '#FF9845', '建议': '#B37FEB'
  }

  const nodeSizes: Record<string, number> = {
    '城市': 65, '日程': 45, '景点': 35, '酒店': 35, '餐饮': 25,
    '天气': 28, '预算': 40, '建议': 30
  }

  function addNode(id: string, name: string, category: string, extraValue: string = '') {
    if (nodeIds.has(id)) return
    nodeIds.add(id)
    const catIdx = categories.findIndex(c => c.name === category)
    nodes.push({
      id, name,
      category: Math.max(0, catIdx),
      symbolSize: nodeSizes[category] || 30,
      itemStyle: { color: nodeColors[category] || '#999' },
      value: extraValue,
    })
  }

  function addEdge(source: string, target: string, label: string = '') {
    edges.push({ source, target, label })
  }

  const cities = props.tripPlan.cities || [props.tripPlan.city]
  const rootId = `city_${props.tripPlan.city}`
  addNode(rootId, cities.join(' → '), '城市', `${props.tripPlan.start_date} ~ ${props.tripPlan.end_date}`)

  // Days
  props.tripPlan.days.forEach((day, di) => {
    const dayId = `day_${di}`
    addNode(dayId, `第${di + 1}天`, '日程', day.date)
    addEdge(rootId, dayId, '行程')

    // Attractions
    day.attractions.forEach((attr, ai) => {
      const attrId = `attr_${di}_${ai}`
      const parts = [attr.address || '', `游览${attr.visit_duration || 0}分钟`]
      if (attr.ticket_price) parts.push(`¥${attr.ticket_price}`)
      if (attr.reservation_required) parts.push('需预约')
      addNode(attrId, attr.name, '景点', parts.filter(Boolean).join(' | '))
      addEdge(dayId, attrId, '游览')

      if (ai > 0) {
        const prevId = `attr_${di}_${ai - 1}`
        addEdge(prevId, attrId, '下一站')
      }
    })

    // Hotel
    if (day.hotel) {
      const hotelId = `hotel_${di}`
      addNode(hotelId, day.hotel.name, '酒店', `${day.hotel.price_range || ''} | ¥${day.hotel.estimated_cost || 0}/晚`)
      addEdge(dayId, hotelId, '入住')
    }

    // Meals
    day.meals.forEach((meal, mi) => {
      const mealTypeMap: Record<string, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '小吃' }
      const mealLabel = mealTypeMap[meal.type] || meal.type
      const mealId = `meal_${di}_${mi}`
      addNode(mealId, `${mealLabel}: ${meal.name}`, '餐饮', meal.estimated_cost ? `¥${meal.estimated_cost}` : '')
      addEdge(dayId, mealId, mealLabel)
    })
  })

  // Weather
  props.tripPlan.weather_info?.forEach((w) => {
    const wId = `weather_${w.date}`
    addNode(wId, `${w.day_weather || ''} ${w.day_temp || 0}°C`, '天气', w.date)
    props.tripPlan.days.forEach((day) => {
      if (day.date === w.date) addEdge(`day_${day.day_index}`, wId, '天气')
    })
  })

  // Budget
  if (props.tripPlan.budget) {
    const b = props.tripPlan.budget
    addNode('budget_total', `总预算 ¥${b.total}`, '预算', '')
    addEdge(rootId, 'budget_total', '预算')

    const budgetItems: [string, number][] = [
      ['景点 ¥', b.total_attractions || 0],
      ['酒店 ¥', b.total_hotels || 0],
      ['餐饮 ¥', b.total_meals || 0],
      ['交通 ¥', b.total_transportation || 0],
    ]
    if (b.total_inter_city_transport) budgetItems.push(['城际交通 ¥', b.total_inter_city_transport])
    budgetItems.forEach(([label, value], i) => {
      if (value) {
        addNode(`budget_${i}`, `${label}${value}`, '预算', '')
        addEdge('budget_total', `budget_${i}`, label.replace(' ¥', ''))
      }
    })
  }

  // Suggestions
  if (props.tripPlan.overall_suggestions) {
    const text = props.tripPlan.overall_suggestions
    addNode('suggestion', text.length > 25 ? text.slice(0, 25) + '...' : text, '建议', text)
    addEdge(rootId, 'suggestion', '建议')
  }

  return { nodes, edges, categories }
}

function initChart() {
  if (!graphChartRef.value || !hasData.value) return

  if (chartInstance) chartInstance.dispose()

  chartInstance = echarts.init(graphChartRef.value)
  const { nodes, edges, categories } = buildGraphData()

  chartInstance.setOption({
    tooltip: {
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const d = params.data
          return `<strong>${d.name}</strong>${d.value ? '<br/>' + d.value : ''}`
        }
        return params.data?.label || ''
      }
    },
    legend: [{
      data: categories.map(c => c.name),
      orient: 'vertical',
      left: 10,
      top: 20,
    }],
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      links: edges,
      categories,
      roam: true,
      draggable: true,
      force: {
        repulsion: 400,
        edgeLength: [120, 300],
        gravity: 0.15,
        friction: 0.6,
      },
      label: {
        show: true,
        position: 'right',
        fontSize: 11,
        formatter: (p: any) => p.name.length > 12 ? p.name.slice(0, 12) + '...' : p.name,
      },
      lineStyle: {
        color: '#ccc',
        curveness: 0.2,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3 },
      },
    }],
  })

  window.addEventListener('resize', () => chartInstance?.resize())
}

onMounted(() => {
  nextTick(() => initChart())
})

watch(() => props.tripPlan, () => {
  nextTick(() => initChart())
}, { deep: true })
</script>

<style scoped>
.tab-graph {
  background: var(--color-bg-primary);
  border-radius: 16px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
}

.graph-chart {
  width: 100%;
  height: 580px;
}

.graph-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: var(--color-text-tertiary);
}

.empty-icon { font-size: 60px; margin-bottom: 16px; }
</style>
