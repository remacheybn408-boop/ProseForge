# Roadmap

Novel Pipeline - Write Engine 开发路线图。

## Phase 1: 项目可运行 ✅ (当前已完成)

- [x] README 对齐真实仓库结构
- [x] config.example.json — 配置模板
- [x] chapter_pipeline.py 去硬编码，改为 CLI 参数 + config.json 驱动
- [x] 字数门禁同步：3300 红线，3500-3900 最佳
- [x] 场景门禁同步：>= 4 有效场景
- [x] database/schema.sql — 完整 SQLite 表结构
- [x] scripts/init_db.py — 数据库初始化
- [x] scripts/check_schema.py — Schema 完整性检查
- [x] volume_plans / chapter_plans / title_history 表已在 schema 中
- [x] docs/skills/long_novel_writing_SKILL.md — 写作行为规范

**验证命令：**
```bash
git clone <repo-url>
cp config.example.json config.json
python scripts/init_db.py --config config.json
python scripts/check_schema.py --config config.json
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel
```

## Phase 2: 标题骨架与卷级连续性

规划中：

- [ ] import_outline_skeleton.py — 从 JSON 导入标题骨架
- [ ] volume_plans / chapter_plans 的写入与校验
- [ ] 卷级 post（volume_post）：生成卷级总结、状态、下一卷承接点
- [ ] chapter_brief 输出增强
- [ ] 标题骨架入库（pre 阶段从 volume_plans/chapter_plans 读取）
- [ ] 卷序强制检查（跨卷连续性验证）

**预计：** Phase 2 完成后，可以从 JSON 骨架初始化整本书结构，逐章推进时自动读取/更新计划。

## Phase 3: 工具增强

- [ ] tests/ — 单元测试
  - test_word_count_gate.py
  - test_scene_quality_gate.py
  - test_config_load.py
  - test_schema_init.py
- [ ] GitHub Actions CI
- [ ] scripts/export_novel.py — 导出完整小说
- [ ] scripts/backup_db.py — 数据库备份
- [ ] scripts/create_novel.py — 创建新小说项目

**未来可考虑（backlog）：**
- Web UI
- FastAPI 后端
- 向量数据库（用于写作参考检索）
- Agent 编排增强

---

> 当前阶段：Phase 1 已完成。Phase 2 是下一步重点。
