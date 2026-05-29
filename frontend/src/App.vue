<template>
  <div id="app">
    <div class="app-shell">
      <nav class="navbar" :class="{ 'navbar-scrolled': scrolled, 'navbar-light': !isHome }">
        <div class="navbar-inner">
          <a class="navbar-brand" @click.prevent="$router.push('/')">
            <svg class="brand-icon" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2"/>
              <path d="M8 18C8 18 10 14 16 14C22 14 24 18 24 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              <circle cx="16" cy="11" r="2" fill="currentColor"/>
            </svg>
            <span class="brand-text">YunTu</span>
            <span class="brand-sub">云途</span>
          </a>
          <div class="navbar-links">
            <router-link to="/" class="nav-link" active-class="nav-link-active">规划行程</router-link>
            <router-link to="/my-trips" class="nav-link" active-class="nav-link-active">我的行程</router-link>
          </div>
          <div class="navbar-actions">
            <a href="https://github.com" target="_blank" class="gh-link" title="GitHub">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.387.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.73.083-.73 1.205.085 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.418-1.305.762-1.604-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z"/></svg>
            </a>
          </div>
        </div>
      </nav>

      <main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const scrolled = ref(false)
const isHome = computed(() => route.name === 'Home')

const onScroll = () => {
  scrolled.value = window.scrollY > 60
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
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
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  padding: 0 32px;
  height: 64px;
  display: flex;
  align-items: center;
  transition: var(--transition-normal);
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03), 0 2px 4px rgba(0, 0, 0, 0.02);
}

/* 首页: 透明导航栏 + 白色文字，叠加在暗色 Hero 上 */
.navbar:not(.navbar-light) {
  background: transparent;
  backdrop-filter: none;
  box-shadow: none;
}
.navbar:not(.navbar-light) .navbar-brand { color: #fff !important; }
/* 首页透明导航: 覆盖胶囊容器背景 + 链接用白色 */
.navbar:not(.navbar-light) .navbar-links {
  background: transparent;
  border-radius: 0;
  padding: 0;
  width: auto;
  gap: 4px;
}
.navbar:not(.navbar-light) .nav-link {
  color: rgba(255, 255, 255, 0.8) !important;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 10px 16px;
  border-radius: 6px;
  flex: none;
}
.navbar:not(.navbar-light) .nav-link:hover { color: #fff !important; background: rgba(255, 255, 255, 0.1); }
.navbar:not(.navbar-light) .nav-link-active { background: transparent !important; color: var(--color-primary) !important; box-shadow: none; font-weight: 600; }
.navbar:not(.navbar-light) .gh-link { color: rgba(255, 255, 255, 0.7); }
.navbar:not(.navbar-light) .gh-link:hover { color: #fff; }

.navbar.navbar-scrolled {
  background: #ffffff !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03), 0 2px 4px rgba(0, 0, 0, 0.02) !important;
}
.navbar.navbar-scrolled .navbar-brand { color: #333 !important; }
.navbar.navbar-scrolled .navbar-links {
  background: #f1f3f5;
  border-radius: 12px;
  padding: 4px;
  width: 240px;
  gap: 0;
  justify-content: center;
  margin: 0 auto;
}
.navbar.navbar-scrolled .nav-link {
  color: #666666 !important;
  font-size: 14px;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
  padding: 8px 24px;
  border-radius: 8px;
  flex: 1;
  text-align: center;
}
.navbar.navbar-scrolled .nav-link:hover { color: #444 !important; background: transparent; }
.navbar.navbar-scrolled .nav-link-active { background: #ffffff !important; color: #e53e3e !important; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.navbar.navbar-scrolled .gh-link { color: rgba(0, 0, 0, 0.5); }
.navbar.navbar-scrolled .gh-link:hover { color: #333; }

.navbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #333 !important;
  text-decoration: none;
  cursor: pointer;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 14px;
}

.brand-icon { width: 28px; height: 28px; }
.brand-sub { font-size: 11px; font-weight: 400; opacity: 0.7; }

/* 胶囊标签容器 */
.navbar-links {
  display: flex;
  gap: 0;
  background: #f1f3f5;
  border-radius: 12px;
  padding: 4px;
  width: 240px;
  justify-content: center;
  margin: 0 auto;
}

.nav-link {
  color: #666666 !important;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
  padding: 8px 24px;
  border-radius: 8px;
  transition: all 0.2s ease;
  flex: 1;
  text-align: center;
  white-space: nowrap;
  line-height: 1.4;
}
.nav-link:hover { color: #444 !important; background: transparent; }
.nav-link-active {
  background: #ffffff !important;
  color: #e53e3e !important;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.navbar-actions { display: flex; align-items: center; gap: 12px; }

.gh-link {
  color: rgba(0, 0, 0, 0.5);
  transition: var(--transition-fast);
  display: flex;
  padding: 4px;
}
.gh-link:hover { color: #333; }

.app-main { min-height: calc(100vh - 60px); }

@media (max-width: 768px) {
  .navbar { padding: 0 16px; }
  .brand-sub { display: none; }
  .navbar-links { width: 200px; }
  .nav-link { padding: 8px 14px; font-size: 13px; }
  .navbar:not(.navbar-light) .navbar-links { width: auto; }
}
</style>
