"""Set default 0 for likes and dislikes in comments

Revision ID: 42ceb38ab75e
Revises: aa0c21503c26
Create Date: 2026-01-30 14:17:11.251487

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '42ceb38ab75e'
down_revision = 'aa0c21503c26'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('comment', 'likes',
               existing_type=sa.Integer(),
               nullable=False,
               server_default="0")
    op.alter_column('comment', 'dislikes',
               existing_type=sa.Integer(),
               nullable=False,
               server_default="0")

def downgrade():
    op.alter_column('comment', 'likes',
               existing_type=sa.Integer(),
               nullable=True,
               server_default=None)
    op.alter_column('comment', 'dislikes',
               existing_type=sa.Integer(),
               nullable=True,
               server_default=None)
