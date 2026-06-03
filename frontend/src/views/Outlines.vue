<template>
  <n-space vertical size="large">
    <n-card size="small">
      <n-space>
        <n-button type="primary" @click="showAdd=true">添加大纲</n-button>
        <n-button @click="loadOutlines" :loading="loading">刷新</n-button>
      </n-space>
    </n-card>

    <n-modal v-model:show="showAdd" title="添加大纲" preset="card" style="width:600px">
      <n-space vertical>
        <n-input v-model:value="addForm.file" placeholder="大纲文件路径 (.txt)" />
        <n-input v-model:value="addForm.title" placeholder="大纲标题" />
        <n-input v-model:value="addForm.genre" placeholder="题材" />
        <n-input v-model:value="addForm.style" placeholder="风格" />
      </n-space>
      <template #footer>
        <n-button type="primary" @click="doAdd" :loading="addLoading">确定</n-button>
        <n-button @click="showAdd=false">取消</n-button>
      </template>
    </n-modal>

    <n-data-table
      :columns="columns"
      :data="outlines"
      :loading="loading"
      :bordered="false"
      size="small"
    />
    <n-empty v-if="!loading && outlines.length===0" description="暂无大纲" />
  </n-space>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { useMessage, NButton, NSpace, NPopconfirm } from 'naive-ui'
import api from '../api'

const message = useMessage()
const loading = ref(false)
const outlines = ref([])
const showAdd = ref(false)
const addLoading = ref(false)
const addForm = ref({ file: '', title: '', genre: '', style: '' })

const columns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '标题', key: 'title' },
  { title: '题材', key: 'genre', width: 100 },
  { title: '状态', key: 'status', width: 80 },
  { title: '操作', key: 'actions', width: 200,
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: 'tiny', onClick: () => switchOutline(row.id) }, { default: () => '激活' }),
          h(NPopconfirm, { onPositiveClick: () => delOutline(row.id) }, {
            default: () => '确认删除？',
            trigger: () => h(NButton, { size: 'tiny', type: 'error' }, { default: () => '删除' })
          }),
        ]
      })
    }
  },
]

async function loadOutlines() {
  loading.value = true
  try {
    const r = await api.outlines()
    const lines = (r.output || '').split('\n').filter(Boolean)
    const list = []
    for (const l of lines) {
      const m = l.match(/\[(.+?)\]\s+(.+?)\s+\[(.+?)\]\s+\[(.+?)\]/)
      if (m) list.push({ id: m[1], title: m[2], genre: m[3], status: m[4] })
      else if (l.trim()) list.push({ id: '?', title: l.trim(), genre: '', status: '' })
    }
    outlines.value = list
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function doAdd() {
  addLoading.value = true
  try {
    await api.outlineAdd({
      outline_file: addForm.value.file,
      title: addForm.value.title,
      genre: addForm.value.genre,
      style: addForm.value.style,
    })
    message.success('大纲添加成功')
    showAdd.value = false
    addForm.value = { file: '', title: '', genre: '', style: '' }
    await loadOutlines()
  } catch (e) {
    message.error(e.message)
  } finally {
    addLoading.value = false
  }
}

async function switchOutline(id) {
  try {
    await api.outlineSwitch(id)
    message.success('已切换大纲')
    await loadOutlines()
  } catch (e) {
    message.error(e.message)
  }
}

async function delOutline(id) {
  try {
    await api.outlineDelete(id)
    message.success('已删除')
    await loadOutlines()
  } catch (e) {
    message.error(e.message)
  }
}

onMounted(loadOutlines)
</script>
