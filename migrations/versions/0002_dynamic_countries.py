"""Add dynamic countries

Revision ID: 0002_dynamic_countries
Revises: 0001_initial_schema
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = '0002_dynamic_countries'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


DEFAULT_COUNTRIES = []


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('countries'):
        op.create_table(
            'countries',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('currency_code', sa.String(length=10), nullable=True),
            sa.Column('logo_image', sa.String(length=500), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
        )
        op.create_index(op.f('ix_countries_name'), 'countries', ['name'], unique=False)
        op.create_index(op.f('ix_countries_is_active'), 'countries', ['is_active'], unique=False)

    countries = sa.table(
        'countries',
        sa.column('name', sa.String),
        sa.column('currency_code', sa.String),
        sa.column('logo_image', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )
    existing = {
        row[0].lower()
        for row in bind.execute(sa.text("SELECT name FROM countries")).fetchall()
    }
    now = datetime.utcnow()
    rows = [
        {
            'name': name,
            'currency_code': currency_code,
            'logo_image': logo_image,
            'is_active': True,
            'created_at': now,
            'updated_at': now,
        }
        for name, currency_code, logo_image in DEFAULT_COUNTRIES
        if name.lower() not in existing
    ]
    if rows:
        op.bulk_insert(countries, rows)


def downgrade():
    op.drop_index(op.f('ix_countries_is_active'), table_name='countries')
    op.drop_index(op.f('ix_countries_name'), table_name='countries')
    op.drop_table('countries')
