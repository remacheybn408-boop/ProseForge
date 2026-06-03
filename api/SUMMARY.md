# 前端构建FastAPI  开发文档

**日期**: 2026-05-31
**任务**: 将所有功能能封装为 FastAPI REST API 方便以后前端开发

## 创建的文件

```
api/
  __init__.py          — package init
  deps.py              — 共享依赖（capture_stdout, slot info, config loading）
  main.py              — FastAPI 主应用 (~800行，40+ 个 API 端点)
requirements-api.txt   — API 依赖 (fastapi, uvicorn, python-multipart)
```

## API 端点清单 (40+)

### 系统
- `GET  /api/health`            — 健康检查
- `GET  /api/status`            — 环境诊断 (支持 ?detail=true)
- `POST /api/init`              — 初始化项目
- `POST /api/demo`              — 运行 demo 全流程
- `POST /api/setup`             — 设置 novels_root 路径

### 写作流程（核心）
- `POST /api/pre/{chapter_no}`      — 写前任务卡
- `POST /api/post/{chapter_no}`     — 写后门禁+入库
- `POST /api/review/{chapter_no}`   — 审查章节
- `POST /api/check`                 — 对任意文件运行 guard
- `GET  /api/wc`                    — 中文字数统计

### 多 Agent 审稿
- `GET  /api/agents`                — 列出 8 个审查 Agent
- `POST /api/agents/review/{n}`     — 并行审稿 (?mode=light|full)

### 报告 & 导出
- `GET  /api/reports`               — 最近报告列表
- `GET  /api/reports/{filename}`    — 报告内容
- `GET  /api/guards`                — 21 个 guard 注册表
- `GET  /api/export`                — 导出小说

### 数据库管理
- `GET  /api/db/list`      — 列出 slots
- `GET  /api/db/current`   — 当前活跃 slot
- `GET  /api/db/info`      — slot 详细信息
- `POST /api/db/new`       — 创建新 slot
- `POST /api/db/switch/{id}`  — 切换 slot
- `POST /api/db/backup`    — 备份
- `DEL  /api/db/{id}`      — 删除（移入回收站）
- `GET  /api/db/trash`     — 回收站
- `POST /api/db/restore/{id}` — 恢复

### 大纲管理
- `GET  /api/outlines`          — 列出大纲
- `GET  /api/outlines/current`  — 当前激活大纲
- `POST /api/outlines/add`      — 添加大纲（含相似度检测）
- `POST /api/outlines/import`   — 导入大纲
- `POST /api/outlines/switch/{id}` — 切换
- `POST /api/outlines/diff/{a}/{b}` — 对比
- `POST /api/outlines/rollback/{id}` — 回滚
- `POST /api/outlines/compare`  — 对比文件与大纲
- `POST /api/outlines/undo`     — 撤销添加
- `DEL  /api/outlines/{id}`     — 删除

### 章节 & 菜单
- `GET  /api/chapters`              — 当前作品所有章节
- `GET  /api/chapters/{n}/content`  — 读取章节内容
- `POST /api/chapters/upload`       — 上传章节文件
- `GET  /api/board`                 — 状态面板
- `GET  /api/menu/status`           — 项目状态 JSON

### 其他
- `GET  /api/genres`          — 题材包列表
- `GET  /api/genres/{id}`     — 题材包详情
- `GET  /api/styles`          — 风格包列表
- `GET  /api/styles/{id}`     — 风格包详情
- `POST /api/story/init`      — 初始化 story contract
- `POST /api/story/contract/{n}` — 章节合同
- `POST /api/story/commit/{n}`   — 章节提交
- `GET  /api/story/health`    — 故事链健康
- `POST /api/query`           — 查询项目记忆
- `GET  /api/learn`           — 写作规则
- `GET  /api/rag/status`      — RAG 状态
- `POST /api/rag/query`       — RAG 查询
- `POST /api/stability-check` — 稳定性自检
- `GET  /api/help`            — 中文操作手册

## 设计决策

1. **最小侵入**：不修改原有代码，通过 subprocess 调用 novel.py / chapter_pipeline.py 的命令行接口
2. **统一响应格式**：`{"success": bool, "data": {...}, "output": "raw stdout"}`
3. **CORS 全开**：方便前端开发（localhost 跨域）
4. **大部分用 subprocess 调用**：保证行为与 CLI 完全一致
5. **关键查询用直接 import**：/api/menu/status, /api/guards 等性能敏感接口直接调用 Python 函数

## 启动方式

```bash
cd novel-pipeline-write-engine
pip install -r requirements-api.txt
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

然后打开 http://localhost:8000/docs 查看 Swagger UI。

## 验证结果

- `/api/health` → 200 OK ✓
- `/api/menu/status` → 返回项目状态 ✓
- `/api/guards` → 返回 21 个 guard 注册表 ✓
- `/api/agents` → 返回 8 个审查 Agent ✓
