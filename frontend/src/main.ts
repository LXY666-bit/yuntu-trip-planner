import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import './styles/design-tokens.css'
import './styles/dark-tokens.css'
import './styles/animations.css'
import './styles/ui.css'
import App from './App.vue'

// 首页直接加载，其余路由懒加载：echarts / jspdf / html2canvas 不再进首屏 bundle
const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition || { top: 0 }
  },
  routes: [
    {
      path: '/',
      name: 'Home',
      component: () => import('./views/Home.vue')
    },
    {
      path: '/result',
      name: 'Result',
      component: () => import('./views/Result.vue')
    },
    {
      path: '/discover',
      name: 'Discover',
      component: () => import('./views/DiscoverView.vue')
    },
    {
      path: '/my-trips',
      name: 'MyTrips',
      component: () => import('./views/MyTrips.vue')
    },
    {
      path: '/draft/:id',
      name: 'Draft',
      component: () => import('./views/DraftView.vue'),
      props: true
    },
    {
      path: '/trip/:id',
      name: 'trip-detail',
      component: () => import('./views/Result.vue'),
      props: true
    }
  ]
})

const app = createApp(App)

app.use(router)
app.use(Antd)

app.mount('#app')
