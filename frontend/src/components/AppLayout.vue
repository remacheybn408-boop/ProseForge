<template>
  <n-config-provider :theme="darkTheme" :locale="zhCN" :date-locale="dateZhCN">
    <n-message-provider>
      <n-layout style="min-height:100vh">
        <n-layout-sider bordered collapse-mode="width" :collapsed-width="64" :width="200" :collapsed="collapsed">
          <n-menu
            v-model:value="activeKey"
            :collapsed="collapsed"
            :collapsed-width="64"
            :collapsed-icon-size="22"
            :options="menuOptions"
            @update:value="onMenuClick"
          />
        </n-layout-sider>
        <n-layout>
          <n-layout-header bordered style="height:48px;padding:0 16px;display:flex;align-items:center;justify-content:space-between">
            <div style="display:flex;align-items:center;gap:8px">
              <n-button quaternary circle @click="collapsed=!collapsed">
                <template #icon><n-icon><MenuOutline /></n-icon></template>
              </n-button>
              <n-text strong style="font-size:16px">{{ pageTitle }}</n-text>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
              <a href="/tutorial/index.html" target="_blank" style="color:#58a6ff;font-size:13px;text-decoration:none">新手教程</a>
              <n-tag v-if="status.novel_title" type="success" size="small">{{ status.novel_title }}</n-tag>
            </div>
          </n-layout-header>
          <n-layout-content style="padding:16px 24px;min-height:calc(100vh - 48px)">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in">
                <component :is="Component" :key="$route.fullPath" />
              </transition>
            </router-view>
          </n-layout-content>
        </n-layout>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { darkTheme, zhCN, dateZhCN } from 'naive-ui'
import { MenuOutline, HomeOutline, CreateOutline, DocumentTextOutline, LayersOutline, ServerOutline, PeopleOutline, SettingsOutline } from '@vicons/ionicons5'
import api from '../api'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)
const status = ref({})

const renderIcon = (icon) => () => h('span', null, h(icon))

const menuOptions = [
  { label: '工作台', key: '/', icon: renderIcon(HomeOutline) },
  { label: '写作', key: '/write', icon: renderIcon(CreateOutline) },
  { label: '审稿', key: '/agents', icon: renderIcon(PeopleOutline) },
  { label: '报告', key: '/reports', icon: renderIcon(DocumentTextOutline) },
  { label: '大纲', key: '/outlines', icon: renderIcon(LayersOutline) },
  { label: '数据', key: '/database', icon: renderIcon(ServerOutline) },
  { label: '设置', key: '/settings', icon: renderIcon(SettingsOutline) },
]

const pageTitle = computed(() => {
  const m = menuOptions.find((m) => m.key === route.path)
  return m ? m.label : 'Novel Pipeline'
})

const activeKey = ref(route.path)

function onMenuClick(key) {
  router.push(key)
}

onMounted(async () => {
  try {
    const r = await api.menuStatus()
    status.value = r.data || {}
  } catch (e) {}
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
