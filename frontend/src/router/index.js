import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/write', name: 'Write', component: () => import('../views/Write.vue') },
  { path: '/write/:chapterNo', name: 'WriteChapter', component: () => import('../views/Write.vue') },
  { path: '/reports', name: 'Reports', component: () => import('../views/Reports.vue') },
  { path: '/outlines', name: 'Outlines', component: () => import('../views/Outlines.vue') },
  { path: '/database', name: 'Database', component: () => import('../views/Database.vue') },
  { path: '/agents', name: 'Agents', component: () => import('../views/Agents.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue') },
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
})
