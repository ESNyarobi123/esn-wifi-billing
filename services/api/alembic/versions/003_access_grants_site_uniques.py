"""Access grants: optional site scope + idempotency uniques on payment / voucher.

``001_initial_schema`` already reflects current ORM columns/FKs on ``customer_access_grants``.
This revision still applies **partial unique** indexes (not declared on the ORM model) and
remains for legacy DBs that predate ``site_id``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003_access_grants_site_uniques"
down_revision = "002_audit_created_at"
branch_labels = None
depends_on = None

_PAYMENT_PARTIAL_UQ = "uq_customer_access_grants_payment_id"
_VOUCHER_PARTIAL_UQ = "uq_customer_access_grants_voucher_id"
_SITE_IX = "ix_customer_access_grants_site_id"
_FK_SITES = "fk_customer_access_grants_site_id_sites"


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("customer_access_grants")}

    if "site_id" not in cols:
        op.add_column(
            "customer_access_grants",
            sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        insp = sa.inspect(conn)

    ix_names = {i["name"] for i in insp.get_indexes("customer_access_grants")}
    if _SITE_IX not in ix_names:
        op.create_index(op.f(_SITE_IX), "customer_access_grants", ["site_id"], unique=False)
        insp = sa.inspect(conn)
        ix_names = {i["name"] for i in insp.get_indexes("customer_access_grants")}

    def _has_site_fk() -> bool:
        for fk in insp.get_foreign_keys("customer_access_grants"):
            if fk.get("referred_table") == "sites" and "site_id" in (fk.get("constrained_columns") or []):
                return True
        return False

    if not _has_site_fk():
        op.create_foreign_key(
            op.f(_FK_SITES),
            "customer_access_grants",
            "sites",
            ["site_id"],
            ["id"],
            ondelete="SET NULL",
        )
        insp = sa.inspect(conn)
        ix_names = {i["name"] for i in insp.get_indexes("customer_access_grants")}

    if _PAYMENT_PARTIAL_UQ not in ix_names:
        op.create_index(
            _PAYMENT_PARTIAL_UQ,
            "customer_access_grants",
            ["payment_id"],
            unique=True,
            postgresql_where=sa.text("payment_id IS NOT NULL"),
        )
    if _VOUCHER_PARTIAL_UQ not in ix_names:
        op.create_index(
            _VOUCHER_PARTIAL_UQ,
            "customer_access_grants",
            ["voucher_id"],
            unique=True,
            postgresql_where=sa.text("voucher_id IS NOT NULL"),
        )


def downgrade() -> None:
    """No-op: ORM baseline includes ``site_id``; partial uniques are required for idempotency."""
