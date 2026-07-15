# Docker-only 运行与测试

宿主机不需要安装 Python、pytest、RAG 依赖或项目虚拟环境。所有命令都在 Docker 容器中执行。

## 首次构建

```bash
docker compose build proseforge
```

## 测试

运行完整测试并把 JUnit 报告保留在 `artifacts/pytest.xml`：

```bash
docker compose run --rm test
```

运行单个测试文件：

```bash
docker compose run --rm test -m pytest tests/test_quality_gate_enforcement.py -q
```

## 日常运行

正式 CLI（仍在容器内执行）：

```bash
docker compose run --rm proseforge -m src.interfaces.cli doctor
docker compose run --rm proseforge -m src.interfaces.cli project create --slug my_novel --title "我的小说"
docker compose run --rm proseforge -m src.interfaces.cli chapter pre 1
```

一次性执行任务：

```bash
docker compose run --rm proseforge plugin/proseforge-codex/scripts/nf_project.py --help
```

启动常驻容器：

```bash
docker compose up -d proseforge
docker compose exec proseforge -m pytest -q
```

工作区和测试报告挂载到宿主机；RAG 模型、向量数据和 Python 依赖保存在 Docker volume 中。

章节 post 的完整审计产物按 `exports/runs/post/chapter_NNN/run_<id>/` 保存；旧版
`exports/reports/` 路径仅作为兼容镜像保留。
