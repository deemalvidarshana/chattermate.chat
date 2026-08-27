"""add Cloudflare Workers AI provider

Revision ID: add_cloudflare_ai_provider_001
Revises: add_openrouter_ai_provider_001
"""

from typing import Sequence, Union

from alembic import op


revision: str = "add_cloudflare_ai_provider_001"
down_revision: Union[str, Sequence[str], None] = "add_openrouter_ai_provider_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE aimodeltype ADD VALUE IF NOT EXISTS 'CLOUDFLARE'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed in place.
    pass
