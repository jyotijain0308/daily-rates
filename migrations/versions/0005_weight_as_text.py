"""Store product weight as text

Revision ID: 0005_weight_as_text
Revises: 0004_company_tenancy
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = '0005_weight_as_text'
down_revision = '0004_company_tenancy'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('products'):
        return

    columns = {column['name']: column for column in inspector.get_columns('products')}
    if 'weight_kg' not in columns:
        return

    if bind.dialect.name == 'postgresql':
        op.alter_column(
            'products',
            'weight_kg',
            existing_type=sa.Float(),
            type_=sa.String(length=100),
            existing_nullable=False,
            postgresql_using='weight_kg::text',
        )
    else:
        with op.batch_alter_table('products') as batch_op:
            batch_op.alter_column(
                'weight_kg',
                existing_type=sa.Float(),
                type_=sa.String(length=100),
                existing_nullable=False,
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('products'):
        return

    if bind.dialect.name == 'postgresql':
        op.alter_column(
            'products',
            'weight_kg',
            existing_type=sa.String(length=100),
            type_=sa.Float(),
            existing_nullable=False,
            postgresql_using="NULLIF(regexp_replace(weight_kg, '[^0-9.\\-]', '', 'g'), '')::double precision",
        )
    else:
        with op.batch_alter_table('products') as batch_op:
            batch_op.alter_column(
                'weight_kg',
                existing_type=sa.String(length=100),
                type_=sa.Float(),
                existing_nullable=False,
            )
