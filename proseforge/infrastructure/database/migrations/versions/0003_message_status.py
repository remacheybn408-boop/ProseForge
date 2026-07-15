"""Add durable assistant message status."""

from alembic import op
import sqlalchemy as sa

revision = "0003_message_status"
down_revision = "0002_remaining_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED'")
    op.execute("ALTER TABLE messages ALTER COLUMN status DROP DEFAULT")


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS status")
