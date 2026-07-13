"""Add more columns to posts table

Revision ID: 6562423bb189
Revises: 268965d7cffd
Create Date: 2026-07-13 10:50:58.137844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6562423bb189'
down_revision: Union[str, Sequence[str], None] = '268965d7cffd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('posts',sa.Column('published',sa.Boolean(),nullable=False,server_default='True'))
    op.add_column('posts',sa.Column('created_at',sa.TIMESTAMP(timezone=True),nullable=False,server_default=sa.text('NOW()')))
    pass


def downgrade() -> None:
    op.drop_column('posts','published')
    op.drop_column('posts','created_at')
    pass
