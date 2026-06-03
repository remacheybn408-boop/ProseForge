<template>
  <n-space vertical size="large">
    <n-card size="small">
      <n-space>
        <n-button type="primary" @click="showNew=true">新建档案</n-button>
        <n-button @click="loadSlots" :loading="loading">刷新</n-button>
      </n-space>
    </n-card>

    <n-modal v-model:show="showNew" title="新建 DB 档案" preset="card" style="width:400px">
      <n-space vertical>
        <n-input v-model:value="newName" placeholder="档案名称" />
        <n-input v-model:value="newDesc" placeholder="描述（可选）" />
      </n-space>
      <template #footer>
        <n-button type="primary" @click="doNew" :loading="newLoading">创建</n-button>
        <n-button @click="showNew=false">取消</n-button>
      </template>
    </n-modal>

    <n-data-table
      :columns="columns"
      :data="slots"
      :loading="loading"
      :bordered="false"
      size="small"
    />
    <n-empty v-if="!loading && slots.length===0" description="暂无档案，请先初始化项目" />

    <n-card title="回收站" size="small">
      <n-data-table
        :columns="trashCols"
        :data="trashItems"
        :bordered="false"
        size="small"
      />
    </n-card>
  </n-space>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { useMessage, NButton, NSpace, NPopconfirm } from 'naive-ui'
import api from '../api'

const message = useMessage()
const loading = ref(false)
const slots = ref([])
const showNew = ref(false)
const newLoading = ref(false)
const newName = ref('')
const newDesc = ref('')
const trashItems = ref([])

const columns = [
  { title: 'ID', key: 'id', width: 100 },
  { title: '名称', key: 'name' },
  { title: '状态', key: 'active', width: 80,
    render(row) {
      return row.active ? h('n-tag', { type: 'success', size: 'small' }, { default: () => '活跃' }) : ''
    }
  },
  { title: '操作', key: 'actions', width: 200,
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: 'tiny', disabled: row.active, onClick: () => switchSlot(row.id) }, { default: () => '切换' }),
          h(NButton, { size: 'tiny', onClick: () => backupSlot(row.id) }, { default: () => '备份' }),
          h(NPopconfirm, { onPositiveClick: () => delSlot(row.id) }, {
            default: () => '移入回收站？',
            trigger: () => h(NButton, { size: 'tiny', type: 'error', disabled: row.active }, { default: () => '删除' })
          }),
        ]
      })
    }
  },
]

const trashCols = [
  { title: '名称', key: 'name' },
  { title: '操作', key: 'actions', width: 100,
    render(row) {
      return h(NButton, { size: 'tiny', onClick: () => restoreSlot(row.id) }, { default: () => '恢复' })
    }
  },
]

async function loadSlots() {
  loading.value = true
  try {
    const r = await api.dbList()
    const lines = (r.output || '').split('\n').filter(Boolean)
    const list = []
    for (const l of lines) {
      const active = l.includes('*') || l.includes('活跃')
      const idMatch = l.match(/slot_\d+/)
      const id = idMatch ? idMatch[0] : ''
      list.push({ id, name: l.trim(), active })
    }
    slots.value = list

    const tr = await api.dbTrash()
    const tl = (tr.output || '').split('\n').filter(Boolean)
    trashItems.value = tl.map((l) => ({ id: l.trim(), name: l.trim() }))
  } catch (e) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function doNew() {
  newLoading.value = true
  try {
    await api.dbNew(newName.value, newDesc.value)
    message.success('创建成功')
    showNew.value = false
    newName.value = ''
    newDesc.value = ''
    await loadSlots()
  } catch (e) {
    message.error(e.message)
  } finally {
    newLoading.value = false
  }
}

async function switchSlot(id) {
  try {
    await api.dbSwitch(id)
    message.success('已切换')
    await loadSlots()
  } catch (e) {
    message.error(e.message)
  }
}

async function backupSlot(id) {
  try {
    await api.dbBackup(id)
    message.success('备份完成')
  } catch (e) {
    message.error(e.message)
  }
}

async function delSlot(id) {
  try {
    await api.dbDelete(id, true)
    message.success('已移入回收站')
    await loadSlots()
  } catch (e) {
    message.error(e.message)
  }
}

async function restoreSlot(id) {
  try {
    await api.dbRestore(id, true)
    message.success('已恢复')
    await loadSlots()
  } catch (e) {
    message.error(e.message)
  }
}

onMounted(loadSlots)
</script>
