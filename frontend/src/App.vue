<template>
  <a-config-provider :theme="antdTheme">
  <div id="app">
    <div class="app-shell">
      <nav class="navbar" :class="{ 'navbar-floating': floating && !headerHidden, 'navbar-light': !isHome, 'navbar-discover': isDiscover, 'navbar-hidden': headerHidden }">
        <div class="navbar-inner">
          <router-link to="/" class="navbar-brand" aria-label="云途首页">
            <svg class="brand-icon" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2"/>
              <path d="M8 18C8 18 10 14 16 14C22 14 24 18 24 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              <circle cx="16" cy="11" r="2" fill="currentColor"/>
            </svg>
            <span class="brand-text">YunTu</span>
            <span class="brand-sub">云途</span>
          </router-link>
          <nav class="navbar-links" aria-label="主导航">
            <router-link to="/" class="nav-link" active-class="nav-link-active">规划行程</router-link>
            <router-link to="/my-trips" class="nav-link" active-class="nav-link-active">我的行程</router-link>
          </nav>
          <div class="navbar-actions">
            <button type="button" class="theme-toggle" :title="resolvedTheme === 'dark' ? '切换到亮色' : '切换到暗色'"
                    :aria-label="resolvedTheme === 'dark' ? '切换到亮色主题' : '切换到暗色主题'"
                    @click="toggleTheme">
              <!-- 太阳 / 月亮：跟随当前主题切换 -->
              <svg v-if="resolvedTheme === 'dark'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <circle cx="12" cy="12" r="4"/>
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            </button>
            <a href="https://github.com/LXY666-bit/yuntu-trip-planner" target="_blank" rel="noopener"
               class="gh-link" title="GitHub 仓库" aria-label="GitHub 仓库">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.387.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.73.083-.73 1.205.085 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.418-1.305.762-1.604-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z"/></svg>
            </a>
          </div>
        </div>
      </nav>

      <main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
  </a-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useScrollHeader } from '@/composables/useScrollHeader'
import { useRoute } from 'vue-router'
import { theme as antdThemeAlgorithm } from 'ant-design-vue'
import { useTheme } from '@/composables/useTheme'

const route = useRoute()
const isDiscover = computed(() => route.path === '/discover')
const { hidden: headerHidden, floating } = useScrollHeader()
const isHome = computed(() => route.name === 'Home')

const { resolvedTheme, toggleTheme } = useTheme()

// antd 组件跟随品牌色与暗色算法（CSS 变量由 dark-tokens.css 通过 data-theme 负责）
const antdTheme = computed(() => ({
  token: {
    colorPrimary: resolvedTheme.value === 'dark' ? '#78bba5' : '#245f50',
    colorInfo: '#245f50',
    colorLink: '#245f50',
    fontFamily: 'Inter, PingFang SC, Microsoft YaHei, sans-serif',
    controlHeight: 38,
    controlHeightLG: 44,
    borderRadius: 8,
  },
  algorithm:
    resolvedTheme.value === 'dark'
      ? antdThemeAlgorithm.darkAlgorithm
      : antdThemeAlgorithm.defaultAlgorithm,
}))
</script>

<style>
#app {
  font-family: var(--font-family-base);
  color: var(--color-text-primary);
  background: var(--color-bg-secondary);
  min-height: 100vh;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to { opacity: 0; transform: translateY(-8px); }

</style>

<style scoped>
.app-shell { min-height: 100vh; }
.navbar {
  position: fixed; inset: 0 0 auto; z-index: 100; height: 56px;
  padding: 0 32px; display: flex; align-items: center;
  background: var(--color-glass-bg); border-bottom: 1px solid var(--color-border-light);
  backdrop-filter: blur(24px) saturate(160%); -webkit-backdrop-filter: blur(24px) saturate(160%);
  transition: transform 260ms cubic-bezier(0.4, 0, 0.2, 1), box-shadow 260ms ease;
}
.navbar-discover { height: 48px; }
.navbar-hidden:not(:focus-within) { transform: translateY(-100%); }
.navbar-floating { box-shadow: 0 10px 28px rgb(23 53 43 / 8%); }
.navbar-inner { width: 100%; max-width: 1280px; margin: auto; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.navbar-brand { display: flex; gap: 8px; align-items: center; color: var(--color-text-primary); white-space: nowrap; }
.brand-icon { width: 27px; height: 27px; color: var(--color-primary); }
.brand-text { font-size: 20px; font-weight: 750; letter-spacing: -0.8px; }
.brand-sub { border-left: 1px solid var(--color-border); padding-left: 10px; margin-left: 2px; font-size: 13px; color: var(--color-text-secondary); }
.navbar-links {
  display: flex; gap: 2px; align-items: center;
  background: var(--color-bg-tertiary); border: 1px solid var(--color-border-light);
  border-radius: 999px; padding: 3px;
}
.nav-link {
  color: var(--color-text-secondary); font-size: 13px; padding: 6px 16px;
  border-radius: 999px; font-weight: 500; white-space: nowrap;
  transition: color 180ms ease, background-color 180ms ease;
}
.nav-link:hover:not(.nav-link-active) { color: var(--color-text-primary); }
.nav-link-active {
  color: var(--color-bg-card);
  background: var(--color-primary);
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 12%);
}
.navbar-actions { display: flex; gap: 8px; align-items: center; }
.theme-toggle, .gh-link {
  width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center;
  color: var(--color-text-secondary); border: 1px solid var(--color-border-light);
  background: var(--color-bg-card); border-radius: 50%; cursor: pointer;
  transition: color 180ms ease, border-color 180ms ease;
}
.theme-toggle:hover, .gh-link:hover { color: var(--color-primary); border-color: var(--color-primary); }
@media (max-width: 600px) {
  .navbar { padding: 0 16px; }
  .navbar-inner { gap: 8px; }
  .brand-sub, .gh-link { display: none; }
  .nav-link { padding: 6px 11px; font-size: 12px; }
  .brand-text { font-size: 18px; }
}
@media (prefers-reduced-motion: reduce) { .navbar { transition: none; } }
</style>
