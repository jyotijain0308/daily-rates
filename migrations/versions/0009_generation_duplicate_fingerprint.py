"""Add generation duplicate fingerprint

Revision ID: 0009_generation_fingerprint
Revises: 0008_social_post_description
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


revision = '0009_generation_fingerprint'
down_revision = '0008_social_post_description'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('generation_history'):
        return

    columns = {column['name'] for column in inspector.get_columns('generation_history')}
    if 'generation_date' not in columns:
        op.add_column('generation_history', sa.Column('generation_date', sa.Date(), nullable=True))
        op.create_index('ix_generation_history_generation_date', 'generation_history', ['generation_date'])

    if 'content_fingerprint' not in columns:
        op.add_column('generation_history', sa.Column('content_fingerprint', sa.String(length=64), nullable=True))
        op.create_index('ix_generation_history_content_fingerprint', 'generation_history', ['content_fingerprint'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('generation_history'):
        return

    columns = {column['name'] for column in inspector.get_columns('generation_history')}
    if 'content_fingerprint' in columns:
        op.drop_index('ix_generation_history_content_fingerprint', table_name='generation_history')
        op.drop_column('generation_history', 'content_fingerprint')

    if 'generation_date' in columns:
        op.drop_index('ix_generation_history_generation_date', table_name='generation_history')
        op.drop_column('generation_history', 'generation_date')
