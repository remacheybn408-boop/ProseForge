"""Add provider, context, workflow, quality, health, and audit tables."""

from alembic import op
from proseforge.infrastructure.database.base import Base

revision = "0002_remaining_schema"
down_revision = "0001_web_core"
branch_labels = None
depends_on = None

_TABLES = (
    "provider_credentials", "model_catalog", "model_profiles", "attachments", "artifacts",
    "context_items", "context_snapshots", "embeddings", "workflow_runs", "workflow_steps",
    "workflow_events", "model_calls", "quality_reports", "health_checks", "audit_logs",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    bind = op.get_bind()
    for name in _TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade() -> None:
    for name in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {name} CASCADE")
