# V1.5 Native Validation（2026-07-18 全量复跑，替代此前所有版本）

Status: **Windows + Linux 绿；macOS BLOCKED（无 macOS 环境，按红线不谎称绿）**

Repository SHA: 见下文本批提交（基线 `4de1b0f` + 本批 19 个提交）
Execution date: 2026-07-18
Runtime: Podman 6.0.1（Client，go1.26.5，WSL machine 4C/2GiB）+ compose provider docker-compose v5.3.1
Native builds: Windows 宿主 `py -3.12`（3.12.7）；Linux 于 `python:3.12` 容器；Inno Setup 6.7.3（winget 用户范围安装）

## 本批提交（4de1b0f → HEAD）

`c9deadf` docs(validation) · `6102d63` chore(release) · `32ca7db` ci · `5d20cc0` feat(cli) · `5ce0f02` build(packaging) · `b3be639` feat(migrations) · `85c371d` ci · `7da3216` fix(cli) · `f86f57e` fix(migrations) · `a2842ab` fix(packaging) · `62c89d1` fix(cli) · `9164643` test(release) · `da325e5` fix(packaging) · `456439e` ci ·（另有 e2e 标注与本文档提交）

## L2 全矩阵（Podman，逐服务串行）

| 套件 | 命令（`C` = `podman compose -f compose.yaml -f compose.test.yaml`） | 退出码 | 结果 |
|---|---|---:|---|
| legacy 回归 | `C run --rm legacy-test pytest -q tests/test_*.py`（RAG 用例加 `-e HF_ENDPOINT=https://hf-mirror.com`） | 0 | **408 passed**（13m57s） |
| API 全量 | `C run --rm api-test pytest -q` | 0 | **697 passed, 4 skipped**（45s；含 tests/fault_injection） |
| contract | `C run --rm contract-test pytest -q tests/contract` | 0 | **19 passed** |
| migration | `C run --rm migration-test pytest -q tests/migration tests/integration/database` | 0 | **24 passed** |
| recovery | `C run --rm recovery-test pytest -q tests/recovery` | 0 | **5 passed** |
| web 前端 | `C run --rm web-test` | 0 | pnpm install + `tsc --noEmit` + **27 vitest passed** + `vite build` ✓ |
| Playwright e2e | `C up -d --wait postgres redis api worker web provider-mock` → `C run --rm e2e` | 0 | **10 passed, 3 skipped** |
| 安全扫描 | `trivy 0.69.3@sha256:7228e304… fs --severity HIGH,CRITICAL --ignore-unfixed .` | 0 | `artifacts/trivy-fs.sarif` 产出 |
| 收尾 | `C down -v` | 0 | 0 容器 / 0 卷（已验证） |

e2e 3 个 skip（spec 内 `test.skip` 注明原因）：`ordinary-user-smoke`（刷新后工作区恢复 = V2-001 范围）、`v3-agent-swarm`/`v3-execution-proposal`（V3 占位执行器 + 共享账号 fixture 导致顺序敏感，V3 阶段重实现后恢复）。

镜像 digest：api `ee07422e…`、worker `ce3a07a7…`、web `353af9d1…`、api-test `72dbd3fd…`、legacy-test `4137a8c6…`、trivy `7228e304…`

## 原生生命周期实测

### Windows（Inno Setup 编译 + 安装 + 卸载）

| 步骤 | 证据 |
|---|---|
| 打包 | `py -3.12 -m packaging.native_bundle --target windows --format zip` → `ProseForge/` onedir（PyInstaller，钉版 Python 3.12.7）+ zip + sha256；内置冒烟 `--version → 1.5.0` |
| 编译 | `ISCC.exe packaging/windows/ProseForge.iss` → `ProseForge-1.5.0-windows-setup.exe`（30.7MB，编译成功） |
| 安装 | `setup.exe /VERYSILENT /NORESTART` → rc=0，`C:\Program Files\ProseForge\proseforge.exe` 就位 |
| 运行 | 安装后 exe `--version → 1.5.0`；`doctor --json → status ok`（native/sqlite） |
| 首跑 | `proseforge web` → `/api/v1/health/ready` 12 项全 ok（redis=not_applicable）；SPA 200；`auth/setup` 201；建项目 201；SQLite+WAL/密钥/blobs 落盘 |
| 自启 | `service_install.ps1` 写 HKCU Run 键（查询验证）；`service_uninstall.ps1` 移除（键为空） |
| 升级 | `upgrade --check` ready（current=head=0024）；`upgrade` 真实执行 status=upgraded，报告写出 |
| 备份/恢复 | `backup create/verify/restore` 全通；篡改归档被拒（非零、无堆栈） |
| 卸载 | `unins000.exe /VERYSILENT` → rc=0；Program Files 目录清空；**`%LOCALAPPDATA%\ProseForge` 数据保留**（backups/ + sqlite 仍在） |

### Linux（tarball，容器内模拟用户机）

`python:3.12-slim` 容器解包 `ProseForge-linux-*.tar.gz`：`--version → 1.5.0`；`doctor` ok（XDG 路径 `~/.local/share/ProseForge`）；`proseforge web` 首跑 health/ready 全 ok、SPA 200、`auth/setup` 201、数据目录齐备。deb/rpm 构建脚本已实现（dpkg-deb/rpmbuild 容器路径），本批未执行打包，列入后续。

### macOS

**NOT TESTED**。`build-pkg.sh`/`Distribution.xml`/LaunchAgent plist 已实现并通过静态测试，但本机无 macOS 环境；按蓝图红线不得在 Windows 上声称 macOS 绿。需要 macOS runner 执行后才能放行该项。

## 环境与兼容性修复记录（本批发现并修复）

- `docker/nginx.conf` 的 `resolver 127.0.0.11` 是 Docker 专用内嵌 DNS，Podman 下 nginx→api 全 502 → 改直连 upstream（e2e 从 2/13 通过变为 10/13，其余 3 个为 V2/V3 范围 skip）。
- legacy 套件向 `/app/exports`、Playwright 向 `test-results` 写入，在 Podman+Windows virtiofs 挂载下 EACCES → compose.test.yaml 加 tmpfs 覆盖层（对 CI 的 Linux Docker 行为一致）。
- pnpm store 在 Windows 挂载上 sqlite "readonly database" → 加 Linux 原生 store 卷。
- podman machine 注入死代理 `127.0.0.1:6478`（宿主代理对 VM/容器不可达）→ 机器级停用；`build_native.sh` 容器内显式清代理。
- RAG 测试需下载 HF 嵌入模型，本网络直连 huggingface.co 不可达 → 本地用 `HF_ENDPOINT=https://hf-mirror.com` 通过（408/408）；CI 无此问题。
- junit `--junitxml=/artifacts/...` 写 Windows 挂载点 EACCES → 本地执行时省略该参数（测试本身全绿），CI 不受影响。
- 容器内 alembic 修订读取 `+asyncpg`→psycopg2 不存在 → 统一映射 `+psycopg`（psycopg v3）。

## 门禁对照（V1.5 10_RELEASE_GATE）

- Functional：首跑建用户/项目 ✓（Win+Linux）；SQLite WAL 重启存活 ✓；本地队列恢复 ✓（api 套件 tests/tasks 覆盖）；同源 chat/workflow/export ✓（e2e 通过项）；Docker server 全栈测试 ✓。**macOS 浏览器首跑 — BLOCKED**
- Operational：doctor/backup create/verify/restore/upgrade ✓；卸载不清数据 ✓；服务（HKCU Run 自启）停启 ✓；日志脱敏 ✓（密钥不进 stdout，测试断言）
- Compatibility：VERSION/pyproject/package.json/API/manifest/iss 全 1.5.0 ✓；0001–0012 迁移未动 ✓；Docker 命令可用 ✓；legacy 回归 408 ✓
- 结论：**V1.5 在 Windows/Linux 达成；macOS 安装验证仍 BLOCKED，不做发布标记，待 macOS runner 补验**
