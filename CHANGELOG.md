# Changelog

## v0.6.5_GUI - 正式推出GUI页面可视化版本 (2026-05-31)


- 将程序所有功能封装为FastAPI适配前端开发
- 本地可视化操作

## v0.6.5 - Archive Jury Multi-DB Release (2026-05-27)

- 18 项 P0/P1/P2 稳定性修复：demo 自动激活大纲、Story Contract 零填充统一、每 slot 独立 novel.db、3 slot 注册一致、大纲智能处理、Agent 陪审团 20 代理、安全删除（回收站）、自然语言菜单、命令别名
- 新增 Outline 大纲管理系统（添加/列出/切换/对比/回滚/删除）+ 五维度相似度检测
- 新增 Jury 评审团配置系统（4 模式 + 8 Agent）+ 增强 Doctor 诊断（33 项）
- 新增 Multi-DB 工作区系统（每 slot 独立 novel.db + registry.json）
- 296 tests 全通过

## v0.6.2 - Cross-Platform Release (2026-05-27)

- 版本号统一至 v0.6.2 (VERSION / version.py / novel.py / README.md / config.example.json)
- 修复硬编码 Windows 路径：smoke_test.py 使用 Path(__file__).parents[2] 动态解析；fts_health.py 使用配置驱动路径
- 统一 Shell 脚本 Python 检测模式：支持 venv 自动激活、$PYTHON 变量、可执行权限
- 新增 scripts/cross_platform_check.py 跨平台自检工具（平台/版本/SQLite FTS5/路径/脚本）
- README 增加 Windows/macOS/Linux 三平台安装说明

## v0.6.1 - Clean Release (2026-05-26)

- 版本号统一至 v0.6.1 (VERSION / version.py / novel.py / README.md)
- 从 Git 追踪中移除 .story/ 目录（运行时状态，非源码）
- Demo 输出顺序修复：所有子进程调用前添加 flush=True，使用 capture_output=True
- wc 命令支持章节号：`python novel.py wc 1` 自动解析到章节文件路径
- check 命令帮助文本修正：移除 "v0.5.0" 引用
- query 命令显示合同详情：开放伏笔数、禁止变更项、活跃角色数
- story health 三档输出：OK / WARN / FAIL（空合同字段→WARN，缺提交→WARN，word_count≤0→FAIL）
- README 当前版本更新至 v0.6.1，CHANGELOG 添加本条目

## v0.6.0 - Story Contract CLI Release (2026-05-26)

- 新增 Story Contract 命令组：story init / contract / commit / health
- 新增 query / learn / board 项目记忆和只读状态看板
- 修复 nested config(paths/novel/gates) 与旧脚本顶层字段不兼容的问题
- 修复 init 建库路径与 status 检查路径不一致的问题
- 修复 demo 未先运行 pre 导致 post 必失败的问题
- 清理发布包中的旧后端残留、.vite 缓存、嵌套 write-engine 副本和乱码 README
- 修复 tests/test_agent_run_guard.py 子进程测试不稳定问题，296 tests 全绿

## v0.5.6 - Clean CLI Release (2026-05-26)

### Fixed
- chapter_pipeline.py: chapter dir path now includes novel slug (novels/<slug>/第01卷)
- agents review: path resolution now includes novel slug
- Report directory: unified from reports/ to exports/reports/
- Demo: now runs post (ingest to DB) after creating chapter
- test_agent_run_guard.py: hardened subprocess handling to prevent hangs
- tmp/ removed from git tracking

### Changed
- README updated to v0.5.6 (title, test count 296, version lines)
- novel.py header updated to v0.5.6
- cmd_init creates exports/reports instead of reports/

## v0.5.5 - Stable & Easy Mode (2026-05-25)

### Added
- 统一命令入口 novel.py（init/demo/status/pre/post/review/report/export）
- status 健康检查命令
- 增强 Voice Pack（41 个语言包，含方言/语体/梗/英语/旁白/禁用）
- 增强 Meme Pack（梗浓度控制 + 角色绑定 + 场景绑定 + 冷静期）
- 写前任务卡 Task Card（承接/推进/禁止 + Voice/Meme 提醒）
- Reader Pull Guard 追读力门禁（钩子/兑现/悬念/爽点/代价）
- 章节风险评分 risk_score.py（8 维度）
- HTML 只读报告（纯静态，无 CDN，双击即开）
- 5 种题材模板（修仙/都市异能/规则怪谈/悬疑/科幻）
- YAML Voice Pack / Meme Pack 资产格式
- Windows 一键体验脚本（install.bat → run_demo.bat → run_report.bat）
- 多 Agent 预留目录（默认关闭，不影响主流程）

### Changed
- README 全面更新到 v0.5.5（重点、快速开始、目录结构、版本历史）
- Voice Pack 核心与小说角色解耦
- 对白密度门禁（>10% WARNING, >20% SEVERE）
- 破折号密度门禁（>5/千字 WARNING, >12/千字 SEVERE）
- 无引号对白检测 fallback 模式

### Not Included (for future versions)
- 完整多 Agent 写作系统
- Web Dashboard 前端工程
- Vector / Graph Hybrid RAG
- 37 个题材模板
