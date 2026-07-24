"""Add company social post description

Revision ID: 0008_social_post_description
Revises: 0007_social_connections
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


revision = '0008_social_post_description'
down_revision = '0007_social_connections'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('company_settings'):
        return

    columns = {column['name'] for column in inspector.get_columns('company_settings')}
    if 'social_post_description' not in columns:
        op.add_column(
            'company_settings',
            sa.Column('social_post_description', sa.Text(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('company_settings'):
        return

    columns = {column['name'] for column in inspector.get_columns('company_settings')}
    if 'social_post_description' in columns:
        op.drop_column('company_settings', 'social_post_description')
