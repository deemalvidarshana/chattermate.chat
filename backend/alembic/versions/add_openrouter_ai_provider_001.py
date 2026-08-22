"""add OpenRouter AI provider

Revision ID: add_openrouter_ai_provider_001
Revises: add_agent_business_identity_001
"""

from typing import Sequence, Union

from alembic import op


revision: str = "add_openrouter_ai_provider_001"
down_revision: Union[str, Sequence[str], None] = "add_agent_business_identity_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enum values must be added before SQLAlchemy can persist the
    # corresponding AIModelType member.
    op.execute("ALTER TYPE aimodeltype ADD VALUE IF NOT EXISTS 'OPENROUTER'")


def downgrade() -> None:
    # PostgreSQL cannot safely remove an enum value in place. Leaving the value
    # is harmless and avoids rebuilding aimodeltype plus every dependent column.
    pass
