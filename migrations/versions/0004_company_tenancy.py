"""Add company tenancy and company settings

Revision ID: 0004_company_tenancy
Revises: 0003_background_audio
Create Date: 2026-07-12
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = '0004_company_tenancy'
down_revision = '0003_background_audio'
branch_labels = None
depends_on = None


DEFAULT_COMPANY_ID = 1
DEFAULT_COMPANY_NAME = 'Eastern Farms LLC'
DEFAULT_COMPANY_SLUG = 'eastern-farms-llc'


def _add_company_id_column(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns(table_name)}
    if 'company_id' not in columns:
        op.add_column(
            table_name,
            sa.Column(
                'company_id',
                sa.Integer(),
                nullable=False,
                server_default=str(DEFAULT_COMPANY_ID),
            ),
        )
        op.create_index(op.f(f'ix_{table_name}_company_id'), table_name, ['company_id'], unique=False)


def _drop_unique_constraint_for_columns(table_name, columns):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    target = set(columns)

    for constraint in inspector.get_unique_constraints(table_name):
        if set(constraint.get('column_names') or []) == target:
            op.drop_constraint(constraint['name'], table_name, type_='unique')


def _has_unique_constraint(table_name, name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(
        constraint.get('name') == name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _has_foreign_key(table_name, constrained_columns):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    target = set(constrained_columns)
    return any(
        set(constraint.get('constrained_columns') or []) == target
        for constraint in inspector.get_foreign_keys(table_name)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    now = datetime.utcnow()

    if not inspector.has_table('companies'):
        op.create_table(
            'companies',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('slug', sa.String(length=120), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.UniqueConstraint('slug'),
        )
        op.create_index(op.f('ix_companies_is_active'), 'companies', ['is_active'], unique=False)
        op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=True)
        op.create_index(op.f('ix_companies_slug'), 'companies', ['slug'], unique=True)

    companies = sa.table(
        'companies',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )
    existing_company = bind.execute(
        sa.select(companies.c.id).where(companies.c.id == DEFAULT_COMPANY_ID)
    ).first()
    if not existing_company:
        op.bulk_insert(companies, [{
            'id': DEFAULT_COMPANY_ID,
            'name': DEFAULT_COMPANY_NAME,
            'slug': DEFAULT_COMPANY_SLUG,
            'is_active': True,
            'created_at': now,
            'updated_at': now,
        }])

    if not inspector.has_table('company_settings'):
        op.create_table(
            'company_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('subtitle', sa.String(length=255), nullable=False),
            sa.Column('default_country', sa.String(length=100), nullable=False),
            sa.Column('address', sa.Text(), nullable=False),
            sa.Column('website', sa.String(length=500), nullable=True),
            sa.Column('company_logo_image', sa.String(length=500), nullable=True),
            sa.Column('destination_logo_image', sa.String(length=500), nullable=True),
            sa.Column('currency', sa.String(length=10), nullable=False),
            sa.Column('rate_display_format', sa.String(length=50), nullable=False),
            sa.Column('exchange_rate_api_url', sa.String(length=500), nullable=True),
            sa.Column('exchange_rate_cache_hours', sa.Integer(), nullable=False, server_default='24'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('company_id'),
        )
        op.create_index(op.f('ix_company_settings_company_id'), 'company_settings', ['company_id'], unique=True)

    settings = sa.table(
        'company_settings',
        sa.column('company_id', sa.Integer),
        sa.column('subtitle', sa.String),
        sa.column('default_country', sa.String),
        sa.column('address', sa.Text),
        sa.column('website', sa.String),
        sa.column('company_logo_image', sa.String),
        sa.column('destination_logo_image', sa.String),
        sa.column('currency', sa.String),
        sa.column('rate_display_format', sa.String),
        sa.column('exchange_rate_api_url', sa.String),
        sa.column('exchange_rate_cache_hours', sa.Integer),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )
    existing_settings = bind.execute(
        sa.select(settings.c.company_id).where(settings.c.company_id == DEFAULT_COMPANY_ID)
    ).first()
    if not existing_settings:
        op.bulk_insert(settings, [{
            'company_id': DEFAULT_COMPANY_ID,
            'subtitle': 'Daily Product Rates',
            'default_country': 'United Arab Emirates',
            'address': 'Office #1835, One by Omniyat, Business Bay, Dubai, United Arab Emirates',
            'website': 'https://www.easternfarmsllc.com',
            'company_logo_image': 'assets/company_logo.png',
            'destination_logo_image': 'assets/uae_logo.jpg',
            'currency': 'AED',
            'rate_display_format': 'AED {:.2f}',
            'exchange_rate_api_url': 'https://api.exchangerate-api.com/v4/latest',
            'exchange_rate_cache_hours': 24,
            'created_at': now,
            'updated_at': now,
        }])

    for table_name in ['products', 'countries', 'generation_history', 'background_audio']:
        if inspector.has_table(table_name):
            _add_company_id_column(table_name)

    bind = op.get_bind()
    if bind.dialect.name != 'sqlite' and inspector.has_table('products'):
        _drop_unique_constraint_for_columns('products', ['product_name', 'country_of_origin'])
        if not _has_unique_constraint('products', 'uq_company_product_origin'):
            op.create_unique_constraint(
                'uq_company_product_origin',
                'products',
                ['company_id', 'product_name', 'country_of_origin'],
            )
        if not _has_foreign_key('products', ['company_id']):
            op.create_foreign_key(
                'fk_products_company_id_companies',
                'products',
                'companies',
                ['company_id'],
                ['id'],
            )

    if bind.dialect.name != 'sqlite' and inspector.has_table('countries'):
        _drop_unique_constraint_for_columns('countries', ['name'])
        if not _has_unique_constraint('countries', 'uq_company_country_name'):
            op.create_unique_constraint('uq_company_country_name', 'countries', ['company_id', 'name'])
        if not _has_foreign_key('countries', ['company_id']):
            op.create_foreign_key(
                'fk_countries_company_id_companies',
                'countries',
                'companies',
                ['company_id'],
                ['id'],
            )

    if bind.dialect.name != 'sqlite':
        for table_name in ['generation_history', 'background_audio']:
            if inspector.has_table(table_name) and not _has_foreign_key(table_name, ['company_id']):
                op.create_foreign_key(
                    f'fk_{table_name}_company_id_companies',
                    table_name,
                    'companies',
                    ['company_id'],
                    ['id'],
                )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name != 'sqlite':
        for table_name in ['background_audio', 'generation_history', 'countries', 'products']:
            if inspector.has_table(table_name):
                for constraint in inspector.get_foreign_keys(table_name):
                    if set(constraint.get('constrained_columns') or []) == {'company_id'}:
                        op.drop_constraint(constraint['name'], table_name, type_='foreignkey')

    for table_name in ['background_audio', 'generation_history', 'countries', 'products']:
        if inspector.has_table(table_name):
            columns = {column['name'] for column in inspector.get_columns(table_name)}
            if 'company_id' in columns:
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.drop_index(op.f(f'ix_{table_name}_company_id'))
                    batch_op.drop_column('company_id')

    if inspector.has_table('company_settings'):
        op.drop_index(op.f('ix_company_settings_company_id'), table_name='company_settings')
        op.drop_table('company_settings')
    if inspector.has_table('companies'):
        op.drop_index(op.f('ix_companies_slug'), table_name='companies')
        op.drop_index(op.f('ix_companies_name'), table_name='companies')
        op.drop_index(op.f('ix_companies_is_active'), table_name='companies')
        op.drop_table('companies')
