"""add subscription event ordering

Revision ID: 002eventorder
Revises: 001initial
"""

import sqlalchemy as sa

from alembic import op

revision = "002eventorder"
down_revision = "001initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("last_stripe_event_created", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "last_stripe_event_created")
