FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PROSEFORGE_HOME=/app

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir -e ".[api,dev,rag]" pytest

ARG SOURCE_REV=dev
RUN echo "building ProseForge source revision ${SOURCE_REV}"
# Explicit copies keep untracked local source files visible to Docker's
# incremental context on Windows as well as in CI.
COPY pyproject.toml ./pyproject.toml
COPY src ./src
COPY tests ./tests
COPY . .

ENTRYPOINT ["python"]
CMD ["-m", "pytest", "-q"]
