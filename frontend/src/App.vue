<template>
  <div id="app" :data-theme="resolvedTheme">
    <div class="app-shell">
      <nav class="navbar navbar-transparent" :class="{ 'navbar-scrolled': scrolled }">
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
            <button class="theme-toggle-btn" @click="toggleTheme" :title="resolvedTheme === 'dark' ? '亮色' : '暗色'">
              <span v-if="resolvedTheme === 'dark'">☀️</span>
              <span v-else>🌙</span>
            </button>
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
import { ref, onMounted, onUnmounted } from 'vue'
import { useTheme } from '@/composables/useTheme'

const { resolvedTheme, toggleTheme } = useTheme()
const scrolled = ref(false)

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
  z-index: var(--z-fixed);
  padding: 0 32px;
  height: 64px;
  display: flex;
  align-items: center;
  transition: var(--transition-normal);
  background: transparent;
}

.navbar-scrolled {
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

[data-theme="dark"] .navbar-scrolled {
  background: rgba(26, 21, 48, 0.92);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

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
  color: #fff !important;
  text-decoration: none;
  cursor: pointer;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 14px;
}
.navbar-scrolled .navbar-brand { color: #333 !important; }
[data-theme="dark"] .navbar-scrolled .navbar-brand { color: #fff !important; }

.brand-icon { width: 28px; height: 28px; }
.brand-sub { font-size: 11px; font-weight: 400; opacity: 0.7; }

.navbar-links { display: flex; gap: 4px; }

.nav-link {
  color: rgba(255, 255, 255, 0.8) !important;
  text-decoration: none;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 10px 16px;
  border-radius: 6px;
  transition: var(--transition-fast);
  letter-spacing: 0.5px;
}
.nav-link:hover { color: #fff !important; background: rgba(255, 255, 255, 0.1); }
.navbar-scrolled .nav-link { color: rgba(0, 0, 0, 0.65) !important; }
.navbar-scrolled .nav-link:hover { color: #333 !important; background: rgba(0, 0, 0, 0.05); }
[data-theme="dark"] .navbar-scrolled .nav-link { color: rgba(255, 255, 255, 0.7) !important; }
[data-theme="dark"] .navbar-scrolled .nav-link:hover { color: #fff !important; background: rgba(255,255,255,0.1); }
.nav-link-active { color: var(--color-primary) !important; }

.navbar-actions { display: flex; align-items: center; gap: 12px; }

.gh-link {
  color: rgba(255, 255, 255, 0.7);
  transition: var(--transition-fast);
  display: flex;
  padding: 4px;
}
.gh-link:hover { color: #fff; }
.navbar-scrolled .gh-link { color: rgba(0, 0, 0, 0.5); }
[data-theme="dark"] .navbar-scrolled .gh-link { color: rgba(255, 255, 255, 0.5); }

.theme-toggle-btn {
  width: 32px; height: 32px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition-fast);
}
.navbar-scrolled .theme-toggle-btn { border-color: rgba(0, 0, 0, 0.2); }
[data-theme="dark"] .navbar-scrolled .theme-toggle-btn { border-color: rgba(255, 255, 255, 0.2); }

.app-main { min-height: calc(100vh - 60px); }

@media (max-width: 768px) {
  .navbar { padding: 0 16px; }
  .brand-sub { display: none; }
  .nav-link { padding: 8px 12px; font-size: 11px; }
}
</style>
