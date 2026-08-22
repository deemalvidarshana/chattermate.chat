"""add per-agent business identity

Revision ID: add_agent_business_identity_001
Revises: fcm_tokens_per_device_001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_agent_business_identity_001"
down_revision: Union[str, Sequence[str], None] = "fcm_tokens_per_device_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("business_name", sa.String(length=100), nullable=True))
    op.add_column("agents", sa.Column("business_domain", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "business_domain")
    op.drop_column("agents", "business_name")
