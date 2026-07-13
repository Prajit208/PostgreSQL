"""add foreign key to post table

Revision ID: 268965d7cffd
Revises: e33e2239c7b2
Create Date: 2026-07-13 10:35:58.264164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '268965d7cffd'
down_revision: Union[str, Sequence[str], None] = 'e33e2239c7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('posts',sa.Column('owner_id',sa.Integer(),nullable=False))
    op.create_foreign_key('posts_users_fk',source_table='posts',referent_table='users',
                          local_cols=['owner_id'],remote_cols=['id'],ondelete="CASCADE")
    pass


def downgrade() -> None:
    op.drop_constraint('posts_users_fk',table_name='posts')
    op.drop_column('posts','owner_id')
    pass
