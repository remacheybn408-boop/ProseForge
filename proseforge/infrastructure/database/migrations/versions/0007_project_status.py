"""Add the project lifecycle status column."""

from alembic import op


revision = "0007_project_status"
down_revision = "0006_workflow_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF to_regclass('public.projects') IS NOT NULL THEN "
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS status VARCHAR(32); "
        "UPDATE projects SET status = 'ACTIVE' WHERE status IS NULL; "
        "ALTER TABLE projects ALTER COLUMN status SET NOT NULL; "
        "END IF; END $$"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS status")
