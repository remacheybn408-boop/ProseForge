import axios from 'axios'
import { useMessage } from 'naive-ui'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 300000,
})

api.interceptors.response.use(
  (r) => r.data,
  (e) => {
    const msg = e.response?.data?.detail || e.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

export default {
  health: () => api.get('/health'),
  status: (detail) => api.get('/status', { params: { detail } }),
  init: () => api.post('/init'),
  demo: () => api.post('/demo'),

  pre: (chapterNo, slug, volumeNo) =>
    api.post(`/pre/${chapterNo}`, null, { params: { slug, volume_no: volumeNo } }),
  post: (chapterNo, slug, volumeNo, filePath, story) =>
    api.post(`/post/${chapterNo}`, null, { params: { slug, volume_no: volumeNo, file_path: filePath, story } }),
  review: (chapterNo, slug, volumeNo) =>
    api.post(`/review/${chapterNo}`, null, { params: { slug, volume_no: volumeNo } }),
  check: (filePath) => api.post('/check', { file_path: filePath }),
  wc: (filePath) => api.get('/wc', { params: { file_path: filePath } }),

  agents: () => api.get('/agents'),
  agentsReview: (chapterNo, mode, slug) =>
    api.post(`/agents/review/${chapterNo}`, null, { params: { mode, slug } }),

  reports: (limit) => api.get('/reports', { params: { limit } }),
  reportContent: (filename) => api.get(`/reports/${filename}`),
  guards: () => api.get('/guards'),
  exportNovel: (slug, fmt) => api.get('/export', { params: { slug, format: fmt } }),

  dbList: () => api.get('/db/list'),
  dbCurrent: () => api.get('/db/current'),
  dbInfo: () => api.get('/db/info'),
  dbNew: (name, description) => api.post('/db/new', { name, description }),
  dbSwitch: (slotId) => api.post(`/db/switch/${slotId}`),
  dbBackup: (slotId) => api.post('/db/backup', null, { params: { slot_id: slotId } }),
  dbDelete: (slotId, confirm) => api.delete(`/db/${slotId}`, { params: { confirm } }),
  dbTrash: () => api.get('/db/trash'),
  dbRestore: (slotId, fromTrash, backupId) =>
    api.post(`/db/restore/${slotId}`, null, { params: { from_trash: fromTrash, backup_id: backupId } }),

  outlines: () => api.get('/outlines'),
  outlinesCurrent: () => api.get('/outlines/current'),
  outlineAdd: (data) => api.post('/outlines/add', data),
  outlineSwitch: (id) => api.post(`/outlines/switch/${id}`),
  outlineImport: (data) => api.post('/outlines/import', data),
  outlineDiff: (id1, id2) => api.post(`/outlines/diff/${id1}/${id2}`),
  outlineRollback: (id) => api.post(`/outlines/rollback/${id}`),
  outlineCompare: (file) => api.post('/outlines/compare', { compare_file: file }),
  outlineDelete: (id) => api.delete(`/outlines/${id}`),
  outlineUndo: () => api.post('/outlines/undo'),

  chapters: () => api.get('/chapters'),
  chapterContent: (no, slug) => api.get(`/chapters/${no}/content`, { params: { slug } }),
  uploadChapter: (file, chapterNo, slug) => {
    const fd = new FormData()
    fd.append('file', file)
    if (chapterNo) fd.append('chapter_no', chapterNo)
    if (slug) fd.append('slug', slug)
    return api.post('/chapters/upload', fd)
  },

  genres: () => api.get('/genres'),
  genreDetail: (id) => api.get(`/genres/${id}`),
  styles: () => api.get('/styles'),
  styleDetail: (id) => api.get(`/styles/${id}`),

  storyInit: () => api.post('/story/init'),
  storyContract: (no) => api.post(`/story/contract/${no}`),
  storyCommit: (no) => api.post(`/story/commit/${no}`),
  storyHealth: () => api.get('/story/health'),

  query: (q) => api.post('/query', { question: q }),
  learn: (action, rule) => api.get('/learn', { params: { action, rule } }),
  ragStatus: () => api.get('/rag/status'),
  ragQuery: (q) => api.post('/rag/query', { question: q }),
  stabilityCheck: (full) => api.post('/stability-check', null, { params: { full } }),
  help: () => api.get('/help'),

  menuStatus: () => api.get('/menu/status'),
  board: () => api.get('/board'),
  setup: (novelsRoot) => api.post('/setup', { novels_root: novelsRoot }),
}
