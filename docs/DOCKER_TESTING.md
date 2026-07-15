# Docker-only 运行与测试

ProseForge Web v1 的测试和构建固定在 Docker 中运行。宿主机只需要 Docker Desktop、Compose 和 Git。

## 启动基础服务

```bash
docker compose up -d postgres redis
docker compose ps
```

PostgreSQL 和 Redis 都必须显示 `healthy`。

## 数据库迁移

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm migration-test alembic upgrade head
```

从空库验证完整迁移链：

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm migration-test sh -lc "alembic downgrade base && alembic upgrade head"
```

## 测试命令

完整旧核心回归：

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm legacy-test
```

Web/API/迁移/恢复/前端测试：

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm api-test
docker compose -f compose.yaml -f compose.test.yaml run --rm contract-test
docker compose -f compose.yaml -f compose.test.yaml run --rm migration-test
docker compose -f compose.yaml -f compose.test.yaml run --rm recovery-test
docker compose -f compose.yaml -f compose.test.yaml run --rm web-test
```

JUnit 报告写入 `artifacts/`。聚焦测试可以覆盖服务默认 command：

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm api-test pytest tests/api/test_health.py -q
```

## 构建与运行

```bash
docker compose -f compose.yaml -f compose.test.yaml config --quiet
docker compose build api worker web
docker compose up -d api worker scheduler web
```

Web 地址为 `http://localhost:3000`，API 地址为 `http://localhost:8000`。

## 数据与安全

- `postgres-data`、`redis-data`、`proseforge-blobs` 和 `proseforge-backups` 使用 Docker volumes。
- 不要把真实 `.env`、API key、JWT secret 或 master key 提交到 Git。
- 上传文件使用 content-addressed BlobStore；备份必须经过 hash 校验。
- 生产环境禁止默认 secret 和相对路径。

## 停止

```bash
docker compose down
```

不使用 `-v`，这样不会删除数据库和 Redis volume。
