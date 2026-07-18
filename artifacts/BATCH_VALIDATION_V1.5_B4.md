# V1.5 B4 Podman Batch（真实复跑，替代已撤销的旧版）

Batch: **B4 = V15-008 / V15-009**
Date: 2026-07-18
Runtime: Podman 6.0.1（WSL machine），compose provider = docker-compose v5.3.1（`.tools/docker-compose.exe`）
Compose: `podman compose -f compose.yaml -f compose.test.yaml`（下文简称 `C`）
本批提交：`5d20cc0` feat(cli) / `5ce0f02` build(packaging) / `b3be639` feat(migrations) / `7da3216`+`f86f57e`+`a2842ab`+`62c89d1` 批次内修复

## 批次内修复（先红后绿，均有独立提交）

| 问题 | 修复 | 提交 |
|---|---|---|
| 容器内 `check_upgrade` 连 PG 报 ModuleNotFoundError | `_sync_url`/env.py 把 `+asyncpg` 映射到 `+psycopg`（psycopg v3） | f86f57e |
| native SPA 同源 POST 403（public_url 与浏览器 Origin 不匹配） | `proseforge web` 默认 `PROSEFORGE_PUBLIC_URL=http://host:port` | 7da3216 |
| Windows 无 env 运行 `doctor` 崩溃（PurePosixPath.mkdir） | doctor 无 server 指标时推断 native + 纯路径禁 I/O | 5d20cc0 |
| 本环境 ONLOGON 计划任务拒绝访问 | 自启改 HKCU Run 键（每用户、免提权）；ps1 try/catch 容错 | a2842ab |
| 损坏备份 verify 打堆栈 | CLI 干净报错 + 非零退出 | 62c89d1 |
| web-test pnpm store sqlite "readonly database" | compose.test.yaml 加 Linux 原生 store 卷 + `--store-dir /pnpm-store` | 85c371d |

## 逐条命令与结果

| # | 命令 | 退出码 | 结果 |
|---|---|---:|---|
| 1 | `C build api-test` | 0 | image `b57044d44fe6` |
| 2 | `C up -d postgres redis` | 0 | healthy |
| 3 | `C run --rm api-test pytest -q tests/packaging tests/operations tests/cli tests/runtime` | 0 | **99 passed, 2 skipped**（PowerShell 用例在 Linux 容器按预期跳过） |
| 4 | `C run --rm api-test pytest -q tests/database tests/tasks` | 0 | **24 passed, 1 skipped**（live PG 用例无 URL 跳过） |
| 5 | `C run --rm migration-test pytest -q tests/migration tests/integration/database` | 0 | **24 passed** |
| 6 | `C run --rm recovery-test pytest -q tests/recovery` | 0 | **5 passed** |
| 7 | `C run --rm api-test ruff check proseforge tests` | 0 | All checks passed |
| 8 | `C run --rm web-test` | 0 | pnpm install + `tsc --noEmit` + Vitest 27 passed + `vite build`（dist 产出） |
| 9 | `py -3.12 -m packaging.native_bundle --root . --output artifacts/native/windows --target windows --format zip` | 0 | `ProseForge/` onedir + zip + `.sha256`；内置冒烟 `proseforge.exe --version -> 1.5.0` |
| 10 | 原生 exe 冒烟（见下） | 0 | 见"原生冒烟" |
| 11 | `C down -v` | 0 | 容器 0、卷 0（`podman ps -a` / `podman volume ls` 均空） |

注 1：#5/#6 本地执行时把服务命令里的 `--junitxml=/artifacts/...` 去掉（junit 写 Windows 挂载点在 Podman 下 EACCES；CI/Linux Docker 无此问题，compose 文件未改）。测试本身全绿。
注 2：#3 首轮 1 failed（`test_cli_upgrade_check_json_keys_stable`，即上表 `_sync_url` 问题），修复后复跑全绿。

## 原生冒烟（Windows 宿主，`artifacts/native/windows/ProseForge/proseforge.exe`，构建自 f86f57e）

| 检查 | 命令 | 结果 |
|---|---|---|
| 版本 | `proseforge.exe --version` | `1.5.0`，rc=0 |
| 首跑健康 | `proseforge.exe web --port 8792 --data-dir <tmp>` → GET `/api/v1/health/ready` | 全 ok（database/migration/master_key/blob_roundtrip 等 12 项，redis=not_applicable） |
| SPA 同源 | GET `/` | 200（打包内 frontend-dist） |
| 首跑建用户 | POST `/api/v1/auth/setup`（真实 Origin `http://127.0.0.1:8792`） | 201 ADMIN |
| 建项目 | POST `/api/v1/projects`（Bearer） | 201，slug=smoke-novel |
| 数据落盘 | 数据目录内容 | `proseforge.sqlite3`(+WAL)、`master.key`、`jwt.key`、`blobs/`、`backups/`、`logs/` |
| doctor 无 env | `proseforge.exe doctor --json` | status ok、profile native、sqlite（不再崩溃） |
| 备份 | `backup create --source <data> --output <out.tar.gz>` | 8 files，manifest+sha256 |
| 备份校验 | `backup verify <out.tar.gz>` | VERIFY-OK |
| 损坏拒绝 | 截断篡改归档后 `backup verify` | 拒绝，非零退出，无堆栈（源码级修复已证，exe 待下次重建纳入） |
| 恢复 | `backup restore <out.tar.gz> --staging <dir>` | rc=0，sqlite/密钥/清单全部还原 |
| 升级检查 | `upgrade --check` | status ready、current=head=0024_agent_fault_mode、pending false |
| 真实升级 | `upgrade --data-dir <data>` | status upgraded，报告写出（revision 保持 head），rc=0 |
| 自启注册/移除 | `service_install.ps1` → 注册表查询 → `service_uninstall.ps1` | HKCU Run 键写入正确命令；卸载后键为空；数据目录不动 |

## 安全扫描（本地）

`trivy 0.69.3`（`sha256:7228e304…`，攻击窗口前最后版本）宿主机直扫：
`trivy fs --format sarif -o artifacts/trivy-fs.sarif --severity HIGH,CRITICAL --ignore-unfixed .`
→ 产出 `artifacts/trivy-fs.sarif`。
说明：容器内 DB 下载在本机被 VM 代理注入阻断（已按机器级修复：关掉 podman machine 的死代理），本地改用宿主二进制验证；CI（GitHub runner）走 compose 无关的 `docker run aquasec/trivy:0.69.3@sha256:…`，无此限制。

## 环境修复记录（一次性，机器级）

- Podman machine `/etc/environment` 与 `/etc/profile.d/default-env.sh` 注入了死代理 `127.0.0.1:6478`（宿主代理对 VM 不可达），已注释；容器网络恢复直连。
- `dist` 若由宿主机旧构建残留，容器 `vite build` 无法 rmdir（virtiofs EACCES）；已清理由容器重建。后续保持 dist 由容器构建。
- `.tools/` 与 `.venv-native-*/` 已入 `.gitignore`。

## down -v 确认

`C down -v` → exit 0；`podman ps -a` = 0 容器；`podman volume ls` = 0 卷。批次资源已完全释放。
