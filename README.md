# ProseForge

ProseForge 是一个本地部署的长篇小说 AI 写作工作台。你的文稿、设定和对话都存在自己的机器上，模型走你自己配置的接口(OpenAI 兼容),AI 只做参谋——**所有修改建议都必须经你批准才会写进正文**。

## 它能帮你做什么

- **写作工作室**:专注的章节编辑器,选中文段即可让 AI 审校或改写;每次采纳生成一个不可变版本,历史永远可回溯、可对比
- **AI 陪聊(Companion Chat)**:围绕当前作品对话,分支、重生成、候选对比一应俱全;AI 回答会自动带上你的设定上下文
- **故事圣经(Story Bible)**:结构化的设定库(人物、世界观、时间线),钉选的事实会注入后续每一次生成,防止 AI 写串设定
- **上下文透视(Context Inspector)**:每次生成前能看到 AI 到底读到了什么、为什么这些条目被选中、花了多少 token
- **工作流(Workflow)**:把"大纲→草稿→审校"这类多步流程编排在画布上运行,可暂停、恢复、重试、取消,刷新页面不丢状态
- **Agent 集群(Agent Swarm)**:让多个角色化 Agent(主策划、场景写手、连续性评审)并行干活、交叉评审;有冲突会保留证据交给主编 Agent,主编也只能提交修改提案,最终仍由你拍板
- **导出**:一键导出 Markdown / DOCX / EPUB,每份文件附带来源版本号和内容哈希,可校验未被篡改
- **用量统计**:每个项目、每场对话、每次工作流的 token 花费都可查

## 快速开始(Docker)

只需要 Docker Desktop,不需要安装 Python 或 Node。

```bash
git clone https://github.com/remacheybn408-boop/ProseForge.git
cd ProseForge
copy .env.example .env        # Windows;Linux/macOS 用 cp
```

编辑 `.env`,把两处占位值换成随机长字符串:`PROSEFORGE_MASTER_KEY`(32 字节 base64)和 `PROSEFORGE_JWT_SECRET`。生产环境会拒绝默认占位值。

```bash
docker compose up --build -d --wait
```

打开 <http://localhost:3000>:

1. **创建账号**——首次打开进入设置页,这个实例只有一个账号(数据全在你本地,账号只防误触)
2. **配置模型**——进 Settings,添加你的模型凭证:任意 OpenAI 兼容接口(base_url + API key),按项目选择模型
3. 新建项目,开始写作

API 健康检查:`GET http://localhost:8000/api/v1/health/live` 与 `/ready`。

## 原生安装包(免 Docker)

V1.5 起提供原生安装包:打包好的运行时,目标机器什么都不用装。解包后运行 `proseforge web` 即可(默认 <http://127.0.0.1:8000>),数据自动放在系统标准目录(Windows `%LOCALAPPDATA%\ProseForge`,Linux `~/.local/share/ProseForge`)。

- **Windows**:Inno Setup 安装器(安装/升级自动备份/卸载保留文稿)
- **Linux**:deb / rpm 包或免 root tarball,带 `systemctl --user` 服务
- **macOS**:打包脚本就绪,但需要 macOS 机器执行,当前未提供成品

运维命令:`proseforge doctor`(体检)、`proseforge backup create|verify|restore`(备份/校验/恢复)、`proseforge upgrade`(升级:锁定→备份→迁移→健康检查→失败自动回滚)。

自己构建安装包:

```bash
powershell -File scripts/build_native.ps1 -Target windows      # Windows
bash scripts/build_native.sh --target linux --skip-sign        # Linux(容器内构建)
```

## 数据与安全

- 文稿存 PostgreSQL(Docker 卷或本机数据目录),附件走内容寻址 BlobStore
- 模型凭证加密存储,密钥就是 `.env` 里的 `PROSEFORGE_MASTER_KEY`——丢了它凭证无法解密
- 升级前自动备份;`proseforge backup` 系列命令可随时手动备份并校验

## 开发与测试

全部测试在 Docker 内运行,宿主机零依赖:

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm legacy-test   # V1.x 回归 408
docker compose -f compose.yaml -f compose.test.yaml run --rm api-test      # API/Agent 940
docker compose -f compose.yaml -f compose.test.yaml run --rm web-test      # 前端 110 + 构建
docker compose -f compose.yaml -f compose.test.yaml run --rm e2e           # 浏览器端到端 14
```

完整矩阵另有 contract 43、migration 24、recovery 5、故障注入与安全套件;发布验证台账见 `artifacts/`(V1.5/V2/V3 均已 PASS,macOS 安装器除外)。

## 目录

```text
proseforge/    后端(API、领域服务、执行器)
apps/web/      前端(React)
docker/        镜像与编排
database/      表结构与迁移
docs/          设计文档(架构、行为规格、运维)
artifacts/     发布验证证据
src/           V1.x 遗留核心(保持回归)
packaging/     原生安装包构建
```

详细说明:[docs/DOCKER_TESTING.md](docs/DOCKER_TESTING.md)、[docs/architecture.md](docs/architecture.md)、[docs/USER_GUIDE_CN.md](docs/USER_GUIDE_CN.md)。

## License

AGPL-3.0
