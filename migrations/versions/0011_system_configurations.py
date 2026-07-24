"""Add system configuration table

Revision ID: 0011_system_configurations
Revises: 0010_users_auth
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa


revision = '0011_system_configurations'
down_revision = '0010_users_auth'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table('system_configurations'):
        return

    op.create_table(
        'system_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=120), nullable=False),
        sa.Column('value_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_system_configurations_key', 'system_configurations', ['key'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('system_configurations'):
        return

    op.drop_index('ix_system_configurations_key', table_name='system_configurations')
    op.drop_table('system_configurations')
