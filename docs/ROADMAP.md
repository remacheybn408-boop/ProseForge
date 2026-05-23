# Roadmap

Novel Pipeline - Write Engine 开发路线图。

## Phase 1: 项目可运行 ✅ (已完成)

- [x] README 对齐真实仓库结构，标注"早期原型"
- [x] config.example.json — 配置模板（3300 红线，4 场景）
- [x] database/schema.sql — 完整 SQLite 表结构（26 表 + 6 FTS5）
- [x] scripts/init_db.py — 一键建库
- [x] scripts/check_schema.py — Schema 完整性检查
- [x] scripts/import_outline_skeleton.py — JSON 标题骨架 → SQLite
- [x] scripts/chapter_pipeline.py — argparse + config 驱动，无硬编码
- [x] 字数门禁：<3300 失败，3500-3900 最佳
- [x] 场景门禁：>=4 有效场景
- [x] examples/demo_novel/ — 25 章 demo 项目
- [x] docs/skills/long_novel_writing_SKILL.md — 通用写作行为规范
- [x] 14 个基础测试 + GitHub Actions CI

**验证命令：**
```bash
git clone https://github.com/remacheybn408-boop/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine
cp config.example.json config.json
python scripts/init_db.py --config config.json
python scripts/check_schema.py --config config.json
python scripts/import_outline_skeleton.py --config config.json --input examples/demo_novel/outline_skeleton.json
pytest tests/ -v
```

---

## Phase 2: 标题骨架与卷级连续性 ✅ (已完成)

**全部完成：**
- [x] import_outline_skeleton.py — JSON 标题骨架导入
- [x] volume_plans / chapter_plans 基础写入与校验
- [x] pre 阶段读取标题骨架 + TASK CARD 展示
- [x] volume_post + volume_report.json
- [x] chapter_brief JSON 输出 + pre 读取上章 brief
- [x] ingest 自动更新 chapter_plans 状态 + title_history
- [x] 卷序强制检查 + 端到端测试（21 个测试）
- [x] Demo 项目 + CI

---

## Phase 2.5: Agent 路由控制 ✅ (已完成)

- [x] novel_factory_router_SKILL.md — PLAN_MODE / NOVEL_WRITE_MODE 路由器
- [x] long_novel_writing_SKILL 顶部 Section 0：优先读取 Router
- [x] README 强制规则段：NOVEL_WRITE_MODE 执行头 + 禁止聊天模式
- [x] agent_run_guard.py — chapter_run_report.json 自检脚本
- [x] ingest 自动生成 chapter_run_report.json
- [x] Skills 列表挂载 novel_factory_router 链接

---

## Phase 2.6: v0.3.1 — Quality Guard Release ✅

- [x] Hallucination Guard hard gate（FAIL 禁止 ingest）
- [x] Chunked Writing Mode（chunk 300~900 字，assembled_chapter ≥3300）
- [x] Anti-padding Guard（水文检测：同义重复/设定堆砌/尾部补独白）
- [x] assembled_chapter word count gate
- [x] chapter_run_report 质量字段（write_mode/chunk_count/hallucination/padding）
- [x] agent_run_guard 全量质量检查（17 项硬门禁）

---

## Phase 3: 工具增强

- [ ] scripts/create_novel.py — 创建新小说项目
- [ ] scripts/export_novel.py — 导出完整小说
- [x] scripts/backup_db.py — 一键备份（online backup，使用中也可备份）
- [ ] 端到端流水线测试

**未来可考虑（backlog）：**
- Web UI
- FastAPI 后端
- 向量数据库（写作参考检索）
- Agent 编排增强

---

> 当前：Phase 2.5 已完成，下一步 Phase 3 工具增强。
