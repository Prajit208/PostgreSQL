"""add content column to post table

Revision ID: d5f44c6444c3
Revises: 532751149b47
Create Date: 2026-06-30 23:36:47.364116

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5f44c6444c3'
down_revision: Union[str, Sequence[str], None] = '532751149b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('posts',sa.Column('content',sa.String(),nullable=False))
    pass


def downgrade() -> None:
    op.drop_column('posts','content')
    pass
