# ProseForge

ProseForge is a local, Docker-first engineering workflow for long-form fiction: outline management, pre-writing context, post-writing quality gates, revision validation, versioned ingestion, and export.

The core system does not call an LLM. External agents such as Codex, Hermes, or Claude provide writing and semantic review; ProseForge provides project context, deterministic checks, state management, and persistence.

## Quick start

Requirements:

- Docker Desktop with Compose
- Git

Clone the repository and build the application image:

```bash
git clone https://github.com/remacheybn408-boop/ProseForge.git
cd ProseForge
docker compose build proseforge
```

Initialize a project and inspect its health:

```bash
docker compose run --rm proseforge -m src.interfaces.cli project init
docker compose run --rm proseforge -m src.interfaces.cli project create --slug my_novel --title "我的小说"
docker compose run --rm proseforge -m src.interfaces.cli doctor
```

The default genre and style are intentionally empty. Configure them per project instead of inheriting a hard-coded genre.

## Writing workflow

The normal chapter lifecycle is:

```text
pre → write chapter text → post → ingest/version → export
```

Run the chapter pipeline inside the container:

```bash
docker compose run --rm proseforge -m src.interfaces.cli chapter pre 1
docker compose run --rm proseforge -m src.interfaces.cli chapter post 1
```

Use `--slot` when a task must explicitly bind to a project rather than the interactive active project:

```bash
docker compose run --rm proseforge -m src.interfaces.cli chapter pre 1 --slot my_novel
docker compose run --rm proseforge -m src.interfaces.cli chapter post 1 --slot my_novel
```

`post` requires a valid `pre` state. It blocks when the project, chapter type, context pack, or state does not match. Short-chapter merging uses staging and restores both source files if a later check fails.

## Testing

Tests must run in Docker; the host does not need Python, pytest, or RAG dependencies:

```bash
docker compose run --rm test
```

The JUnit report is written to `artifacts/pytest.xml`. Run a focused test file with:

```bash
docker compose run --rm test -m pytest tests/test_quality_gate_enforcement.py -q
```

The current merged branch has 413 passing tests in the Docker test service.

More Docker commands and volume details are documented in [docs/DOCKER_TESTING.md](docs/DOCKER_TESTING.md).

## Project layout

```text
workspace/<slot>/
├── project.json
├── novel.db
├── chapters/
├── outlines/
├── reports/
└── exports/
```

Each slot is an isolated novel project. Runtime contexts can bind explicitly to a slot, so background tasks do not depend on a changing global active-slot selection.

## Interfaces

- `src.interfaces.cli`: formal JSON-producing CLI
- `src.application`: application services shared by CLI and agent adapters
- `plugin/proseforge-codex`: Codex wrappers
- `plugin/proseforge-Hermes`: Hermes tools and skills
- `plugin/proseforge-claude`: Claude workflow skill

## License

AGPL-3.0
