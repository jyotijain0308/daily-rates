"""Add company import price deduction setting

Revision ID: 0006_import_price_deduction
Revises: 0005_weight_as_text
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa


revision = '0006_import_price_deduction'
down_revision = '0005_weight_as_text'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('company_settings'):
        return

    columns = {column['name'] for column in inspector.get_columns('company_settings')}
    if 'import_price_deduction_percent' not in columns:
        op.add_column(
            'company_settings',
            sa.Column(
                'import_price_deduction_percent',
                sa.Float(),
                nullable=False,
                server_default='15',
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('company_settings'):
        return

    columns = {column['name'] for column in inspector.get_columns('company_settings')}
    if 'import_price_deduction_percent' in columns:
        op.drop_column('company_settings', 'import_price_deduction_percent')
