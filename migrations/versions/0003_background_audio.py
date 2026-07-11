"""Add reusable background audio

Revision ID: 0003_background_audio
Revises: 0002_dynamic_countries
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa


revision = '0003_background_audio'
down_revision = '0002_dynamic_countries'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('background_audio'):
        op.create_table(
            'background_audio',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=False),
            sa.Column('stored_filename', sa.String(length=255), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('rights_confirmed', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('uploaded_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('stored_filename'),
        )


def downgrade():
    op.drop_table('background_audio')
