# V1.5 Native Validation

Status: **BLOCKED — release gate not green**（2026-07-18 复核：维持 BLOCKED，且下文部分证据行失效，见标注）

Repository SHA: `a679a92`
Execution date: 2026-07-18  
Local container runtime: Podman

> **2026-07-18 复核标注**：① 下表 "packaging tests and manifest/bundle builder / real Linux archive" 一行的 "real archive" 实为**源码包**（`packaging/native_bundle.py` 拷贝源码树 + 调系统 Python 的启动器），不是蓝图 V15-008 要求的 PyInstaller onedir 原生可执行包，该行证据**失效**。② `build-pkg.sh`/`build-deb.sh`/`build-rpm.sh`/`service_install.ps1` 均为 echo 占位脚本，安装器本身尚不可用。③ CLI 无 `web` 子命令，`proseforge.service` 引用的入口不存在。V15-008 基本未实现，V1.5 阻塞不只是"缺平台测试"。

## Evidence

| Area | Command/result | Exit |
|---|---|---:|
| lifecycle, scheduler, wiring, static Web API | Podman Python pytest, 8 passed | 0 |
| CLI doctor/backup and existing backup regression | Podman Python pytest, 12 passed | 0 |
| upgrade/rollback | Podman Python pytest, 5 passed | 0 |
| health/readiness/fault injection | Podman Python pytest, 4 passed | 0 |
| packaging tests and manifest/bundle builder | Podman Python pytest, 2 passed; real Linux archive + SHA256 manifest smoke passed | 0 |
| native queue + SQLite bootstrap/repositories | Podman Python pytest with read-only mounted `aiosqlite` 0.22.1, 20 passed | 0 |
| frontend unit/component tests | Podman Vitest, 18 files / 27 tests passed | 0 |
| frontend TypeScript | Podman `tsc --noEmit` | 0 |
| frontend production build | Podman Vite build to `/tmp/proseforge-web-dist` | 0 |
| Linux packaging smoke | Podman `scripts/build_native.sh --target linux --format tar.gz --skip-sign` | 0 |

## Blocking evidence

- Full Python matrix: 645 passed, 1 optional RAG test skipped because `chromadb` is not installed, 3 warnings.
- PostgreSQL and Redis were started explicitly with Podman CLI on `proseforge-test-net`; integration tests passed with the test database URL propagated through the environment.
- The checked-in test image omitted the declared `aiosqlite` dependency. The native queue/database slice was rerun with the existing project virtualenv package mounted read-only; the repository itself was not changed to bypass the dependency.
- Frontend dependency installation required a Linux-native Podman dependency volume; TypeScript and Vite now pass there.
- The bundle is a verified source-runtime distribution; PyInstaller/native executable wrapping still requires a target-OS build environment.
- macOS package/signing and Windows installer execution were not run on their native operating systems. They remain NOT TESTED.

V1.5 is therefore not marked complete, not tagged, and not pushed as a release.
