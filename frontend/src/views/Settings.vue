<template>
  <n-space vertical size="large" style="max-width:600px">
    <n-card title="小说文件夹" size="small">
      <n-space vertical>
        <n-input v-model:value="novelsRoot" placeholder="小说文件夹路径，如 D:\小说" />
        <n-text depth="3">每部小说一个子文件夹，大纲、章节、导出都在这里</n-text>
        <n-button type="primary" @click="saveSetup" :loading="saving">保存路径</n-button>
      </n-space>
    </n-card>

    <n-card title="项目状态" size="small">
      <n-descriptions bordered :column="1" size="small">
        <n-descriptions-item label="版本">v0.6.5</n-descriptions-item>
        <n-descriptions-item label="当前小说">{{ status.novel_title || '未设置' }}</n-descriptions-item>
        <n-descriptions-item label="活跃档案">{{ status.active_slot || '无' }}</n-descriptions-item>
        <n-descriptions-item label="章节数">{{ status.chapter_count || 0 }}</n-descriptions-item>
        <n-descriptions-item label="总字数">{{ (status.total_words || 0).toLocaleString() }}</n-descriptions-item>
        <n-descriptions-item label="大纲">{{ status.has_outline ? '已激活' : '未激活' }}</n-descriptions-item>
      </n-descriptions>
    </n-card>

    <n-card title="维护" size="small">
      <n-space vertical>
        <n-button @click="runStability" :loading="checking">运行稳定性检查</n-button>
        <n-button @click="runInit" :loading="initRunning">初始化项目</n-button>
        <n-button @click="exportNovel" :loading="exporting">导出小说</n-button>
        <n-popconfirm @positive-click="runDemo">
          <template #trigger><n-button type="warning">运行 Demo（会创建 demo_novel）</n-button></template>
          确认运行 Demo？
        </n-popconfirm>
      </n-space>
    </n-card>
  </n-space>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '../api'

const message = useMessage()
const status = ref({})
const novelsRoot = ref('')
const saving = ref(false)
const checking = ref(false)
const exporting = ref(false)
const initRunning = ref(false)

async function loadStatus() {
  try {
    const r = await api.menuStatus()
    status.value = r.data || {}
  } catch (e) {}
}

async function saveSetup() {
  saving.value = true
  try {
    await api.setup(novelsRoot.value)
    message.success('路径已保存')
  } catch (e) {
    message.error(e.message)
  } finally {
    saving.value = false
  }
}

async function runStability() {
  checking.value = true
  try {
    const r = await api.stabilityCheck(false)
    message.success('检查完成')
  } catch (e) {
    message.error(e.message)
  } finally {
    checking.value = false
  }
}

async function runDemo() {
  try {
    const r = await api.demo()
    message.success('Demo 完成')
    await loadStatus()
  } catch (e) {
    message.error(e.message)
  }
}

async function runInit() {
  initRunning.value = true
  try {
    await api.init()
    message.success('初始化完成')
  } catch (e) {
    message.error(e.message)
  } finally {
    initRunning.value = false
  }
}

async function exportNovel() {
  exporting.value = true
  try {
    const r = await api.exportNovel()
    message.success('导出完成')
  } catch (e) {
    message.error(e.message)
  } finally {
    exporting.value = false
  }
}

onMounted(loadStatus)
</script>
