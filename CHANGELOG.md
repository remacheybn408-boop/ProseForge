## v0.7.2 — Guard 扩展 + 角色叙事层 (2026-06-06)

### Added
- **Guard 新增 5 个** — 情感渲染力、开篇吸引力、感官描写浓度、节奏变化、视角一致性（总数 22→27）
  - 三种模式同步更新：draft(5)/standard(18)/submission(26)
  - 每个 Guard 含独立 scores 字典，支持按维度评分
- **角色叙事层 (10 字段)** — 角色卡新增第5维度：动机、致命缺陷、秘密、关键创伤、短期/长期目标、特长、短板、预定弧线、弧线当前
  - `_ensure_nested` 自动升级旧卡，缺失分组自动补齐
  - `character edit` 和 `character show` 完整支持新字段显示与编辑
- **Story Arc 规划** — Context + Promise + Plot Threads 合并方案，见 `plans/story-arc-merge-plan.md`
- **都市言情 30 章 Demo** — 内置「城与光之间」(71,710 汉字)，28 张角色卡，全 pipeline 验证

### Fixed
- **`.story/` 自动创建** — `commit_builder.py` 三个函数加 `mkdir(parents=True)`，story commit 不再报 `[WinError 3]`

## v0.7.1 - 角色精神状态系统 (2026-06-04)

### Added
- **角色精神状态系统** — 角色卡新增第四层 `mental_state`，支持 15 类精神状况
  - 数据模型：severity 0-5 + 诱因 + 触发词 + 表现 + 章节追踪
  - 15 类全覆盖：抑郁症、PTSD、焦虑症、强迫症、PTSD（战场型）、人格障碍等
- **CLI 命令** — `character mental <角色名>` 查看/管理精神状态
  - sub 命令: `set` / `onset` / `trigger` / `manifest` / `check`
  - `character mental-scan` 从大纲自动扫描推荐精神状态
  - `outline mental-scan` 同上（outline 子命令别名）
- **mental_state_guard** — 4 条审核规则（过度检测/一致性/偏离/章节追踪）
  - 已注册到 guard_registry，standard + submission 模式自动运行
  - 题材弹性阈值（修仙宽松、都市严格、惊悚更宽松）
- **关键词词库** — `configs/human_texture/mental_state_presets.yaml` 15 类 × 4 维度
- **角色卡展示** — `character show` 新增精神状态区块

### Changed
- `voice_diversity_guard.py` — 新增 `MENTAL_STATE_CATEGORIES` 导出、`_upgrade_flat_card` 保留 mental_state
- `genre_presets.yaml` — 新增 `mental_state` 弹性阈值区块（12 题材 + default）
- `guard_registry.py` — 注册 mental_state_guard（level 2）
- `commands_character.py` — 新增 mental/mental-scan 子命令
- `commands_outline.py` — 新增 mental-scan 子命令

### Test
- 新增 `tests/test_mental_state.py` — 11 个测试（guard 规则 + 数据模型 + 词库）
- 全量 323 测试通过

## v0.7.0 - MCP 中文菜单桥接层 (2026-06-04)

### Added
- **MCP 中文菜单桥接层** — 全新 `mcp_server/` 模块，支持 MCP 协议的 AI 客户端通过中文自然语言调用引擎
  - 10 个安全工具：novel_menu / novel_status / novel_db_list / novel_outline_list / novel_outline_add / novel_chapters / novel_agents_review / novel_story_health / novel_report / novel_export_txt
  - 全中文输出，不暴露终端命令、路径、源码
  - 白名单安全机制（safety.py），正则匹配预定义命令模式
  - 审计日志（audit.py），记录到 logs/mcp_audit.log
  - 超时控制（状态查询 10s / 审稿 60s / 导出 60s）
  - 大纲添加二次确认机制（preview → confirm_action）
  - 支持 Claude Code / Cursor / Hermes 等客户端接入
- **文档** — docs/MCP_CN_GUIDE.md 中文用户指南
- **依赖** — pyproject.toml 添加 mcp>=1.0.0，注册 novel-mcp 控制台入口

### Changed
- 版本号 v0.6.7 → v0.7.0（README / CHANGELOG / pyproject.toml / novel.py / scc_menu.json / hermes_menu.py / command headers 全统一）

## v0.6.7 - 综合管理模块 (2026-06-03)

### Added
- **角色综合管理模块** — character 命令，14个子命令统一管理角色
  - 声纹 + 性格 + 做事风格 + 身份 + 关系 + 成长弧 + 元数据
  - character relate/unrelate/relation-graph 关系管理
  - character export/import 跨项目搬卡
  - character focus 聚焦状态（活跃/暂离/退场）
  - character arc-check 弧线进度检查
  - character chapters 出场章节查询
  - character sync-story 同步到故事合同系统
  - character outline-check --create 大纲→角色一键补齐
- **旧声纹系统标记废弃** — voice_profile_loader.py 加 DEPRECATED

### Fixed
- README / scc_menu.json / pyproject.toml / CHANGELOG 版本统一为 v0.6.7
- 打包脚本修复 demo/novels 误排除
- 删除根目录遗留导出文件

# Changelog

## v0.6.5-fixed.3 - 剧情进度控制器 v2: 复合题材 + 弹性加权 (2026-06-03)

### Added
- **复合题材支持**：`--genre "xianxia+爽文"` 自动加权合并规则（主题材权重递减）
- **弹性加权评分**：每类增量按题材权重计算，而非刚性阈值
- **爽文题材预设**：power_delta 权重 2.0，重视快速升级打脸节奏
- 8 种题材 pacing 规则完善：default/xianxia/爽文/mystery/suspense/romance/urban/horror/history
- 增量强度评分：同一类增量有多个关键词时计分更高
- **genre_presets.yaml 全字段复合**：water_density / conflict_pressure / life_texture 等阈值也支持复合题材加权合并

### Changed
- `_load_genre_pacing()` 支持复合题材解析与加权合并
- `_load_genre_preset()` 支持复合题材阈值加权合并
- `water_density_guard._get_density_threshold()` 改用 YAML 配置 + 复合加权
- `run_plot_pacing_check()` metrics 返回 genres_parsed/weighted_score/progress_ratio
- `genre_presets.yaml` 每个题材增加 pacing 区块（weighted_deltas + focus_deltas）

## v0.6.5-fixed.2 - Voice Card System v2: per-novel card sets + outline integration (2026-06-03)

### Added
- **声纹卡组系统** — 每本小说独立声纹卡组，互不干扰
  - `python novel.py voice set list` 列出声纹卡组
  - `python novel.py voice set use <卡组名>` 切换卡组
  - `project.json` 新增 `active_voice_card_set` 字段
- 声纹卡存储路径: `workspace/<slot>/voice_cards/<卡组名>/<角色>.json`
- 切换小说 slot 时自动切换对应的声纹卡组

### Changed
- `get_voice_cards_dir()` 支持 set_name 参数
- 所有 voice CRUD 命令操作当前激活卡组

## v0.6.5-fixed - Human Texture Quality Layer Integration (2026-06-03)

### Added
- **Human Texture 人工味质量层** — 8 个质量 guard 集成到 post 流水线自动运行：
  - `water_density_guard` 水文密度检测
  - `plot_pacing_controller` 剧情进度控制器（5 档速度 × 8 类进度增量 × 题材预设）
  - `cliche_sentence_guard` 陈词滥句检测
  - `conflict_pressure_guard` 冲突压力检测
  - `emotion_summary_guard` 情绪总结合理性
  - `life_texture_guard` 生活质感检测
  - `prompt_specificity_guard` 提示词具体性
  - `rhythm_guard` 节奏控制
  - `voice_diversity_guard` 声音多样性
- **题材阈值预设** `configs/human_texture/genre_presets.yaml`：9 种题材独立阈值（xianxia/mystery/suspense/romance/urban/horror/history + default）
- **CLI 参数扩展**：`python novel.py post 1 --genre xianxia --pace slow`
- **单独调用命令**：`python novel.py texture check <章节号>` 查看详细报告
- `requirements.txt` 核心依赖文件

### Fixed
- 一键启动.bat UTF-8 编码修复，去除 Node.js 前端依赖
- CLAUDE.md / AGENTS.md guard 数量 23→21（与实际注册一致）
- GitHub URL 统一到 `remacheybn408-boop/Novel-Forge`
- pyproject.toml build backend 从 `setuptools.backends._legacy` 修复为 `setuptools.build_meta`

### Changed
- post 流程完成步骤增加 human_texture 质量报告输出
- 报告文件保存到 `exports/reports/chapter_XXX_texture_report.json`

## v0.6.5_GUI - 正式推出GUI页面可视化版本 (2026-05-31)

### Added
- **Human Texture 人工味质量层** — 8 个质量 guard 集成到 post 流水线自动运行：
  - `water_density_guard` 水文密度检测
  - `plot_pacing_controller` 剧情进度控制器（5 档速度 × 8 类进度增量 × 题材预设）
  - `cliche_sentence_guard` 陈词滥句检测
  - `conflict_pressure_guard` 冲突压力检测
  - `emotion_summary_guard` 情绪总结合理性
  - `life_texture_guard` 生活质感检测
  - `prompt_specificity_guard` 提示词具体性
  - `rhythm_guard` 节奏控制
  - `voice_diversity_guard` 声音多样性
- **题材阈值预设** `configs/human_texture/genre_presets.yaml`：9 种题材独立阈值（xianxia/mystery/suspense/romance/urban/horror/history + default）
- **CLI 参数扩展**：`python novel.py post 1 --genre xianxia --pace slow`
- **单独调用命令**：`python novel.py texture check <章节号>` 查看详细报告
- `requirements.txt` 核心依赖文件

### Fixed
- 一键启动.bat UTF-8 编码修复，去除 Node.js 前端依赖
- CLAUDE.md / AGENTS.md guard 数量 23→21（与实际注册一致）
- GitHub URL 统一到 `remacheybn408-boop/Novel-Forge`
- pyproject.toml build backend 从 `setuptools.backends._legacy` 修复为 `setuptools.build_meta`

### Changed
- post 流程完成步骤增加 human_texture 质量报告输出
- 报告文件保存到 `exports/reports/chapter_XXX_texture_report.json`

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
