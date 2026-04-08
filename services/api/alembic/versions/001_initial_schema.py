"""Create all tables from ORM metadata (baseline revision).

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-04-06

Subsequent migrations should use explicit ``op.add_column`` / ``op.create_table`` as the schema evolves.
"""

from __future__ import annotations

from alembic import op

from app.db import models_registry  # noqa: F401 — register models
from app.db.base import Base

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
