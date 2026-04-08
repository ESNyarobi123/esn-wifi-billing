"""Add audit_logs.created_at for filtering and reporting.

``001_initial_schema`` already creates ``audit_logs`` from ORM metadata, which
includes ``created_at`` and its index. This revision remains for history and
for any legacy database that ran an older ``001`` without that column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_audit_created_at"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None

_INDEX = "ix_audit_logs_created_at"


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("audit_logs")}
    if "created_at" not in cols:
        op.add_column(
            "audit_logs",
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )
        insp = sa.inspect(conn)
    ix_names = {i["name"] for i in insp.get_indexes("audit_logs")}
    if _INDEX not in ix_names:
        op.create_index(op.f(_INDEX), "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    """No-op: current ``001`` always creates ``created_at`` via ORM metadata."""
