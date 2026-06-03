<template>
  <n-space vertical size="large">
    <n-card size="small">
      <n-space align="center">
        <n-button @click="loadReports" :loading="loading">刷新</n-button>
        <n-text depth="3">共 {{ reports.length }} 份报告</n-text>
      </n-space>
    </n-card>

    <n-card v-if="selectedReport" title="报告详情" size="small">
      <n-button size="tiny" @click="selectedReport=null" style="margin-bottom:8px">← 返回列表</n-button>
      <n-scrollbar style="max-height:500px">
        <pre style="white-space:pre-wrap;font-size:12px;line-height:1.5;color:#c9d1d9;margin:0">{{ JSON.stringify(selectedReport, null, 2) }}</pre>
      </n-scrollbar>
    </n-card>

    <n-data-table
      v-else
      :columns="columns"
      :data="reports"
      :loading="loading"
      :bordered="false"
      size="small"
      @update:checked-row-keys="onCheck"
    />
    <n-empty v-if="!loading && reports.length===0" description="暂无报告" />
  </n-space>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { useMessage, NButton } from 'naive-ui'
import api from '../api'

const message = useMessage()
const loading = ref(false)
const reports = ref([])
const selectedReport = ref(null)

const columns = [
  { title: '时间', key: 'mtime', width: 150 },
  { title: '状态', key: 'status', width: 80,
    render(row) {
      const c = row.status === 'PASS' ? 'success' : row.status === 'FAIL' ? 'error' : 'warning'
      return h('n-tag', { type: c, size: 'small' }, { default: () => row.status })
    }
  },
  { title: '大小', key: 'size', width: 80,
    render(row) {
      return row.size < 1024 ? `${row.size}B` : `${(row.size/1024).toFixed(1)}KB`
    }
  },
  { title: '文件', key: 'path', ellipsis: { tooltip: true } },
  { title: '操作', key: 'actions', width: 80,
    render(row) {
      return h(NButton, { size: 'tiny', onClick: () => openReport(row) }, { default: () => '查看' })
    }
  },
]

async function loadReports() {
  loading.value = true
  try {
    const r = await api.reports(50)
    reports.value = r.data?.reports || []
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function openReport(row) {
  try {
    const r = await api.reportContent(row.path)
    selectedReport.value = r.data
  } catch (e) {
    message.error(e.message)
  }
}

function onCheck(keys) {}

onMounted(loadReports)
</script>
