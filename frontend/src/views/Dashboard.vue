<template>
  <div>
    <n-space vertical size="large">
      <n-grid cols="4" x-gap="12" y-gap="12" responsive="screen">
        <n-grid-item span="4 m:1">
          <n-card size="small">
            <n-statistic label="总字数" :value="status.total_words || 0" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="4 m:1">
          <n-card size="small">
            <n-statistic label="章节数" :value="status.chapter_count || 0" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="4 m:1">
          <n-card size="small">
            <n-statistic label="大纲" :value="status.has_outline ? '已激活' : '无'" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="4 m:1">
          <n-card size="small">
            <n-statistic label="档案" :value="status.active_slot || '未初始化'" />
          </n-card>
        </n-grid-item>
      </n-grid>

      <n-card title="快速操作" size="small">
        <n-space>
          <n-button type="primary" @click="$router.push('/write')">
            <template #icon><n-icon><CreateOutline /></n-icon></template>
            写新章节
          </n-button>
          <n-button @click="runDemo" :loading="demoRunning">
            运行 Demo
          </n-button>
          <n-button @click="initProject" :loading="initRunning">
            初始化项目
          </n-button>
          <n-button @click="loadStatus" :loading="loading">
            刷新
          </n-button>
        </n-space>
      </n-card>

      <n-card title="章节列表" size="small">
        <n-data-table
          :columns="columns"
          :data="chapters"
          :loading="loading"
          :bordered="false"
          size="small"
        />
        <n-empty v-if="!loading && chapters.length === 0" description="暂无章节，先去写作页创建第一章吧" />
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { CreateOutline } from '@vicons/ionicons5'
import api from '../api'

const message = useMessage()
const loading = ref(false)
const demoRunning = ref(false)
const initRunning = ref(false)
const status = ref({})
const chapters = ref([])

const columns = [
  { title: '章节', key: 'chapter_no', width: 80 },
  { title: '标题', key: 'title' },
  { title: '字数', key: 'word_count', width: 100 },
  { title: '状态', key: 'status', width: 100 },
]

async function loadStatus() {
  loading.value = true
  try {
    const r = await api.menuStatus()
    status.value = r.data || {}
    const cr = await api.chapters()
    const lines = (cr.output || '').split('\n').filter(Boolean)
    const list = []
    for (const l of lines) {
      const m = l.match(/第(\d+)章\s+(.+?)\s+([\d,]+)字\s+\[(.+?)\]/)
      if (m) {
        list.push({ chapter_no: parseInt(m[1]), title: m[2].trim(), word_count: m[3], status: m[4] })
      }
    }
    chapters.value = list
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function runDemo() {
  demoRunning.value = true
  try {
    const r = await api.demo()
    message.success('Demo 运行完成')
    await loadStatus()
  } catch (e) {
    message.error(e.message)
  } finally {
    demoRunning.value = false
  }
}

async function initProject() {
  initRunning.value = true
  try {
    await api.init()
    message.success('项目初始化完成')
    await loadStatus()
  } catch (e) {
    message.error(e.message)
  } finally {
    initRunning.value = false
  }
}

onMounted(loadStatus)
</script>
