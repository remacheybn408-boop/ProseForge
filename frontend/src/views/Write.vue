<template>
  <n-space vertical size="large">
    <n-card size="small">
      <n-space align="center">
        <n-text strong>章节号</n-text>
        <n-input-number v-model:value="chapterNo" :min="1" :max="9999" style="width:100px" />
        <n-button type="primary" @click="doPre" :loading="preLoading" :disabled="!chapterNo">
          生成任务卡
        </n-button>
        <n-button @click="loadChapter" :loading="loadLoading" :disabled="!chapterNo">
          加载已有章节
        </n-button>
        <n-divider vertical />
        <n-text type="success" v-if="wordCount > 0">字数：{{ wordCount.toLocaleString() }}</n-text>
        <n-button type="error" @click="doPost" :loading="postLoading" :disabled="!chapterContent">
          提交入库
        </n-button>
      </n-space>
    </n-card>

    <n-grid cols="2" x-gap="12" responsive="screen" v-if="taskCard">
      <n-grid-item span="2 m:1">
        <n-card title="写前任务卡" size="small">
          <n-scrollbar style="max-height:400px">
            <pre style="white-space:pre-wrap;font-size:13px;line-height:1.7;color:#c9d1d9;margin:0">{{ taskCard }}</pre>
          </n-scrollbar>
        </n-card>
      </n-grid-item>
    </n-grid>

    <n-card title="章节编辑" size="small">
      <n-input
        v-model:value="chapterContent"
        type="textarea"
        :autosize="{ minRows: 15, maxRows: 30 }"
        placeholder="在此写作你的章节内容…"
        style="font-size:15px;line-height:1.8;font-family:'PingFang SC','Microsoft YaHei',serif"
      />
      <template #footer>
        <n-space justify="end" style="margin-top:8px">
          <n-button @click="uploadFile" :loading="upLoading">上传 TXT 文件</n-button>
          <n-button type="primary" @click="doPost" :loading="postLoading" :disabled="!chapterContent">
            提交入库
          </n-button>
        </n-space>
      </template>
    </n-card>

    <n-card v-if="postResult" title="入库结果" size="small">
      <n-scrollbar style="max-height:300px">
        <pre style="white-space:pre-wrap;font-size:12px;line-height:1.5;color:#8b949e;margin:0">{{ postResult }}</pre>
      </n-scrollbar>
    </n-card>
  </n-space>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import api from '../api'

const route = useRoute()
const message = useMessage()

const chapterNo = ref(1)
const chapterContent = ref('')
const taskCard = ref('')
const postResult = ref('')
const preLoading = ref(false)
const postLoading = ref(false)
const loadLoading = ref(false)
const upLoading = ref(false)

const wordCount = ref(0)

watch(chapterContent, (v) => {
  let c = 0
  for (const ch of v) {
    if ((ch >= '\u4e00' && ch <= '\u9fff') || (ch >= '\u3400' && ch <= '\u4dbf')) c++
  }
  wordCount.value = c
})

async function doPre() {
  preLoading.value = true
  taskCard.value = ''
  try {
    const r = await api.pre(chapterNo.value)
    taskCard.value = r.output || '任务卡生成完成'
  } catch (e) {
    message.error(e.message)
  } finally {
    preLoading.value = false
  }
}

async function doPost() {
  if (!chapterContent.value.trim()) {
    message.warning('请先写入章节内容')
    return
  }
  postLoading.value = true
  postResult.value = ''
  try {
    const blob = new Blob([chapterContent.value], { type: 'text/plain' })
    const file = new File([blob], `第${chapterNo.value}章.txt`, { type: 'text/plain' })
    await api.uploadChapter(file, chapterNo.value)

    const r = await api.post(chapterNo.value)
    postResult.value = r.output || '入库完成'
    if (r.data?.exit_code === 0) {
      message.success('第' + chapterNo.value + '章入库成功')
    } else {
      message.warning('入库有警告，查看下方结果')
    }
  } catch (e) {
    message.error(e.message)
    postResult.value = e.message
  } finally {
    postLoading.value = false
  }
}

async function loadChapter() {
  loadLoading.value = true
  try {
    const r = await api.chapterContent(chapterNo.value)
    chapterContent.value = r.data?.content || ''
    if (chapterContent.value) {
      message.success('已加载第' + chapterNo.value + '章')
    } else {
      message.info('章节为空')
    }
  } catch (e) {
    message.info('该章节尚未创建')
  } finally {
    loadLoading.value = false
  }
}

async function uploadFile() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.txt'
  input.onchange = async (e) => {
    const f = e.target.files[0]
    if (!f) return
    upLoading.value = true
    try {
      const text = await f.text()
      chapterContent.value = text
      message.success('文件加载成功')
    } catch (e) {
      message.error('文件读取失败')
    } finally {
      upLoading.value = false
    }
  }
  input.click()
}

onMounted(() => {
  if (route.params.chapterNo) {
    chapterNo.value = parseInt(route.params.chapterNo) || 1
  }
})
</script>
