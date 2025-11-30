"""Initial database schema."""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("yaml_content", sa.Text(), nullable=False),
        sa.Column("image_type", sa.String(length=50), nullable=False, server_default="fedora-sway-atomic"),
        sa.Column("fedora_version", sa.String(length=20), nullable=False, server_default="43"),
        sa.Column("enable_plymouth", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_config_name_version", "configs", ["name", "version"], unique=False)

    op.create_table(
        "builds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("config_id", sa.Integer(), nullable=True),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "queued",
                "in_progress",
                "success",
                "failure",
                "cancelled",
                name="buildstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("image_type", sa.String(length=50), nullable=False),
        sa.Column("fedora_version", sa.String(length=20), nullable=False),
        sa.Column("ref", sa.String(length=100), nullable=False, server_default="main"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["config_id"], ["configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_build_status", "builds", ["status"], unique=False)
    op.create_index("idx_build_config_ref", "builds", ["config_id", "ref", "status"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "build_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("build_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["builds.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_build_event_build_id", "build_events", ["build_id"], unique=False)
    op.create_index("idx_build_event_timestamp", "build_events", ["timestamp"], unique=False)
    op.create_index("idx_build_event_type", "build_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_build_event_type", table_name="build_events")
    op.drop_index("idx_build_event_timestamp", table_name="build_events")
    op.drop_index("idx_build_event_build_id", table_name="build_events")
    op.drop_table("build_events")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("idx_build_config_ref", table_name="builds")
    op.drop_index("idx_build_status", table_name="builds")
    op.drop_table("builds")

    op.drop_index("idx_config_name_version", table_name="configs")
    op.drop_table("configs")
