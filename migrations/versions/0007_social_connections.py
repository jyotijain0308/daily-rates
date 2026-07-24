"""Add social media connections

Revision ID: 0007_social_connections
Revises: 0006_import_price_deduction
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa


revision = '0007_social_connections'
down_revision = '0006_import_price_deduction'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('social_connections'):
        op.create_table(
            'social_connections',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('access_token', sa.Text(), nullable=True),
            sa.Column('refresh_token', sa.Text(), nullable=True),
            sa.Column('token_expires_at', sa.DateTime(), nullable=True),
            sa.Column('external_account_id', sa.String(length=255), nullable=True),
            sa.Column('external_account_name', sa.String(length=255), nullable=True),
            sa.Column('oauth_state', sa.String(length=255), nullable=True),
            sa.Column('connected_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('company_id', 'provider', name='uq_company_social_provider'),
        )
        op.create_index('ix_social_connections_company_id', 'social_connections', ['company_id'])
        op.create_index('ix_social_connections_provider', 'social_connections', ['provider'])

    if not inspector.has_table('social_publish_history'):
        op.create_table(
            'social_publish_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('generation_id', sa.Integer(), nullable=True),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('external_post_id', sa.String(length=255), nullable=True),
            sa.Column('external_post_url', sa.String(length=500), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.ForeignKeyConstraint(['generation_id'], ['generation_history.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_social_publish_history_company_id', 'social_publish_history', ['company_id'])
        op.create_index('ix_social_publish_history_generation_id', 'social_publish_history', ['generation_id'])
        op.create_index('ix_social_publish_history_provider', 'social_publish_history', ['provider'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('social_publish_history'):
        op.drop_index('ix_social_publish_history_provider', table_name='social_publish_history')
        op.drop_index('ix_social_publish_history_generation_id', table_name='social_publish_history')
        op.drop_index('ix_social_publish_history_company_id', table_name='social_publish_history')
        op.drop_table('social_publish_history')

    if inspector.has_table('social_connections'):
        op.drop_index('ix_social_connections_provider', table_name='social_connections')
        op.drop_index('ix_social_connections_company_id', table_name='social_connections')
        op.drop_table('social_connections')
