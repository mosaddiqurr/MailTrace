"""Persist complete analysis results and local settings."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_analysis_results"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.add_column(
            sa.Column("mime_structure", sa.JSON(), nullable=False, server_default="{}")
        )
        batch.add_column(sa.Column("urls", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("assessment", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("limitations", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("timings", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(
            sa.Column("analysis_status", sa.String(20), nullable=False, server_default="complete")
        )
        batch.add_column(
            sa.Column(
                "analysis_stage", sa.String(40), nullable=False, server_default="building_report"
            )
        )
        batch.add_column(sa.Column("error_code", sa.String(50), nullable=True))
        batch.add_column(sa.Column("error_message", sa.String(300), nullable=True))
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    with op.batch_alter_table("evidence") as batch:
        for name in (
            "error_message",
            "error_code",
            "analysis_stage",
            "analysis_status",
            "timings",
            "limitations",
            "assessment",
            "urls",
            "mime_structure",
        ):
            batch.drop_column(name)
