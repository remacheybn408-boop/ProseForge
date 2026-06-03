<template>
  <n-space vertical size="large">
    <n-card size="small">
      <n-space align="center">
        <n-text strong>章节号</n-text>
        <n-input-number v-model:value="chapterNo" :min="1" :max="9999" style="width:100px" />
        <n-select v-model:value="mode" :options="modeOpts" style="width:120px" />
        <n-button type="primary" @click="runReview" :loading="reviewing">
          开始审稿
        </n-button>
      </n-space>
    </n-card>

    <n-card title="可用审查 Agent" size="small">
      <n-space>
        <n-tag v-for="a in agents" :key="a" :bordered="false">{{ a }}</n-tag>
      </n-space>
    </n-card>

    <n-card v-if="reviewResult" title="审稿结果" size="small">
      <n-space vertical>
        <n-grid cols="3" x-gap="12">
          <n-grid-item>
            <n-statistic label="总评分" :value="reviewResult.overall_score || 'N/A'" />
          </n-grid-item>
          <n-grid-item>
            <n-statistic label="状态" :value="reviewResult.status || 'N/A'" />
          </n-grid-item>
        </n-grid>

        <n-card v-if="reviewResult.chief_editor" title="主编建议" size="small" type="info">
          <n-space vertical>
            <div v-if="reviewResult.chief_editor.must_fix?.length">
              <n-text type="error" strong>必须修复：</n-text>
              <ul style="color:#f85149">
                <li v-for="(item,i) in reviewResult.chief_editor.must_fix" :key="'mf'+i">{{ item }}</li>
              </ul>
            </div>
            <div v-if="reviewResult.chief_editor.should_fix?.length">
              <n-text type="warning" strong>建议修复：</n-text>
              <ul style="color:#d2991d">
                <li v-for="(item,i) in reviewResult.chief_editor.should_fix" :key="'sf'+i">{{ item }}</li>
              </ul>
            </div>
            <div v-if="reviewResult.chief_editor.keep?.length">
              <n-text type="success" strong>保持：</n-text>
              <ul style="color:#3fb950">
                <li v-for="(item,i) in reviewResult.chief_editor.keep" :key="'k'+i">{{ item }}</li>
              </ul>
            </div>
          </n-space>
        </n-card>

        <n-card title="原始输出" size="small" v-if="reviewResult.raw">
          <n-scrollbar style="max-height:300px">
            <pre style="white-space:pre-wrap;font-size:12px;line-height:1.5;color:#8b949e;margin:0">{{ JSON.stringify(reviewResult, null, 2) }}</pre>
          </n-scrollbar>
        </n-card>
      </n-space>
    </n-card>
  </n-space>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '../api'

const message = useMessage()
const agents = ref([])
const chapterNo = ref(1)
const mode = ref('light')
const modeOpts = [
  { label: '轻量审稿', value: 'light' },
  { label: '完整审稿', value: 'full' },
]
const reviewing = ref(false)
const reviewResult = ref(null)

async function loadAgents() {
  try {
    const r = await api.agents()
    agents.value = r.data?.agents || []
  } catch (e) {}
}

async function runReview() {
  reviewing.value = true
  reviewResult.value = null
  try {
    const r = await api.agentsReview(chapterNo.value, mode.value)
    reviewResult.value = r.data
    message.success('审稿完成')
  } catch (e) {
    message.error(e.message)
  } finally {
    reviewing.value = false
  }
}

onMounted(loadAgents)
</script>
