"""payment_callbacks.dedupe_key + unique (provider, dedupe_key) for webhook replay protection.

``001_initial_schema`` already creates these from the ``PaymentCallback`` ORM model.
This revision remains for legacy databases.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004_payment_callback_dedupe"
down_revision = "003_access_grants_site_uniques"
branch_labels = None
depends_on = None

_UQ_DEDUPE = "uq_payment_callback_provider_dedupe"


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("payment_callbacks")}

    if "dedupe_key" not in cols:
        op.add_column("payment_callbacks", sa.Column("dedupe_key", sa.String(length=160), nullable=True))

    uq_names = {u["name"] for u in insp.get_unique_constraints("payment_callbacks")}
    if _UQ_DEDUPE not in uq_names:
        op.create_unique_constraint(_UQ_DEDUPE, "payment_callbacks", ["provider", "dedupe_key"])


def downgrade() -> None:
    """No-op: constraint and column exist on current ORM baseline."""
