"""create products

Revision ID: 0001
Revises:
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("image_key", sa.String(255), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("external_id", name="uq_products_external_id"),
    )


def downgrade() -> None:
    op.drop_table("products")
