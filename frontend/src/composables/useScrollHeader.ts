import { onMounted, onUnmounted, ref } from 'vue'

/**
 * 导航栏滚动状态（模块级单例, 多组件共享同一份状态与监听）：
 * - hidden: 下滑隐藏、上滑浮现（阈值 10px 防触抖）
 * - 接近页面底部时始终浮现（用户能看到 footer 信息）
 * - floating: 已滚离顶部，用于投影等"悬浮"质感
 */
const hidden = ref(false)
const floating = ref(false)
let anchor = 0
let listenerCount = 0

function onScroll() {
  const y = Math.max(0, window.scrollY)
  floating.value = y > 24
  const doc = document.documentElement.scrollHeight - window.innerHeight
  const nearBottom = doc - y < 80
  if (y < 24 || nearBottom) {
    hidden.value = false
    anchor = y
  } else if (Math.abs(y - anchor) >= 10) {
    hidden.value = y > anchor && y > 96
    anchor = y
  }
}

export function useScrollHeader() {
  onMounted(() => {
    listenerCount += 1
    anchor = Math.max(0, window.scrollY)
    onScroll()
    if (listenerCount === 1) {
      window.addEventListener('scroll', onScroll, { passive: true })
    }
  })
  onUnmounted(() => {
    listenerCount = Math.max(0, listenerCount - 1)
    if (listenerCount === 0) {
      window.removeEventListener('scroll', onScroll)
      hidden.value = false
      floating.value = false
    }
  })
  return { hidden, floating }
}
