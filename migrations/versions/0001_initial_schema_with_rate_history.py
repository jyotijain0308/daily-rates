"""Initial schema with product rate history

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa


revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('products'):
        op.create_table(
            'products',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('serial_no', sa.Integer(), nullable=True),
            sa.Column('country_of_origin', sa.String(length=100), nullable=False),
            sa.Column('shipment_by', sa.String(length=100), nullable=False),
            sa.Column('product_name', sa.String(length=255), nullable=False),
            sa.Column('weight_kg', sa.Float(), nullable=False),
            sa.Column('packing', sa.String(length=100), nullable=False),
            sa.Column('price_aed', sa.Float(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('product_name', 'country_of_origin', name='uq_product_origin'),
        )
        op.create_index(op.f('ix_products_country_of_origin'), 'products', ['country_of_origin'], unique=False)
        op.create_index(op.f('ix_products_product_name'), 'products', ['product_name'], unique=False)

    inspector = sa.inspect(bind)
    if not inspector.has_table('generation_history'):
        op.create_table(
            'generation_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('product_count', sa.Integer(), nullable=False),
            sa.Column('generated_at', sa.DateTime(), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('filename'),
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table('product_rate_history'):
        op.create_table(
            'product_rate_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('old_price_aed', sa.Float(), nullable=True),
            sa.Column('new_price_aed', sa.Float(), nullable=False),
            sa.Column('changed_by', sa.String(length=100), nullable=False),
            sa.Column('changed_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_product_rate_history_changed_at'), 'product_rate_history', ['changed_at'], unique=False)
        op.create_index(op.f('ix_product_rate_history_product_id'), 'product_rate_history', ['product_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_product_rate_history_product_id'), table_name='product_rate_history')
    op.drop_index(op.f('ix_product_rate_history_changed_at'), table_name='product_rate_history')
    op.drop_table('product_rate_history')
    op.drop_table('generation_history')
    op.drop_index(op.f('ix_products_product_name'), table_name='products')
    op.drop_index(op.f('ix_products_country_of_origin'), table_name='products')
    op.drop_table('products')
