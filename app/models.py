"""Database models for PPT Daily Rates System"""
from datetime import datetime
from wsgi import db


class Product(db.Model):
    """Product model matching the CSV import contract"""
    __tablename__ = 'products'
    __table_args__ = (
        db.UniqueConstraint('company_id', 'product_name', 'country_of_origin', name='uq_company_product_origin'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, default=1, index=True)
    serial_no = db.Column(db.Integer, nullable=True)
    country_of_origin = db.Column(db.String(100), nullable=False, index=True)
    shipment_by = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(255), nullable=False, index=True)
    weight_kg = db.Column(db.String(100), nullable=False)
    packing = db.Column(db.String(100), nullable=False)
    price_aed = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    rate_history = db.relationship(
        'ProductRateHistory',
        back_populates='product',
        cascade='all, delete-orphan',
        order_by='desc(ProductRateHistory.changed_at)',
    )
    
    def to_dict(self):
        """Convert product to dictionary"""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'serial_no': self.serial_no,
            'country_of_origin': self.country_of_origin,
            'shipment_by': self.shipment_by,
            'product_name': self.product_name,
            'weight_kg': self.weight_kg,
            'packing': self.packing,
            'price_aed': self.price_aed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Product {self.product_name} ({self.country_of_origin})>'


class ProductRateHistory(db.Model):
    """Track product price changes from imports and manual edits."""
    __tablename__ = 'product_rate_history'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey('products.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    old_price_aed = db.Column(db.Float, nullable=True)
    new_price_aed = db.Column(db.Float, nullable=False)
    changed_by = db.Column(db.String(100), nullable=False, default='system')
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    product = db.relationship('Product', back_populates='rate_history')

    def to_dict(self):
        """Convert rate history to dictionary."""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'old_price_aed': self.old_price_aed,
            'new_price_aed': self.new_price_aed,
            'changed_by': self.changed_by,
            'changed_at': self.changed_at.isoformat(),
        }

    def __repr__(self):
        return f'<ProductRateHistory product={self.product_id} {self.old_price_aed}->{self.new_price_aed}>'


class Country(db.Model):
    """Manage countries and their presentation metadata."""
    __tablename__ = 'countries'
    __table_args__ = (
        db.UniqueConstraint('company_id', 'name', name='uq_company_country_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, default=1, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    currency_code = db.Column(db.String(10), nullable=True)
    logo_image = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert country to dictionary."""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'name': self.name,
            'currency_code': self.currency_code,
            'logo_image': self.logo_image,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f'<Country {self.name}>'


class Company(db.Model):
    """Tenant company that owns products, countries, assets, and generation history."""
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    settings = db.relationship(
        'CompanySettings',
        back_populates='company',
        uselist=False,
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        """Convert company to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'settings': self.settings.to_dict() if self.settings else None,
        }

    def __repr__(self):
        return f'<Company {self.name}>'


class User(db.Model):
    """User account scoped to an existing company."""
    __tablename__ = 'users'
    __table_args__ = (
        db.UniqueConstraint('email', name='uq_users_email'),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='member')
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = db.relationship('Company')

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'company_name': self.company.name if self.company else None,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f'<User {self.email}>'


class CompanySettings(db.Model):
    """Company-level presentation and pricing configuration."""
    __tablename__ = 'company_settings'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, default=1, unique=True, index=True)
    subtitle = db.Column(db.String(255), nullable=False)
    default_country = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    website = db.Column(db.String(500), nullable=True)
    company_logo_image = db.Column(db.String(500), nullable=True)
    destination_logo_image = db.Column(db.String(500), nullable=True)
    currency = db.Column(db.String(10), nullable=False)
    rate_display_format = db.Column(db.String(50), nullable=False)
    import_price_deduction_percent = db.Column(db.Float, nullable=False, default=15.0)
    social_post_description = db.Column(db.Text, nullable=True)
    exchange_rate_api_url = db.Column(db.String(500), nullable=True)
    exchange_rate_cache_hours = db.Column(db.Integer, nullable=False, default=24)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company = db.relationship('Company', back_populates='settings')

    def to_dict(self):
        """Convert company settings to dictionary."""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'subtitle': self.subtitle,
            'default_country': self.default_country,
            'address': self.address,
            'website': self.website,
            'company_logo_image': self.company_logo_image,
            'destination_logo_image': self.destination_logo_image,
            'currency': self.currency,
            'rate_display_format': self.rate_display_format,
            'import_price_deduction_percent': self.import_price_deduction_percent,
            'social_post_description': self.social_post_description,
            'exchange_rate_api_url': self.exchange_rate_api_url,
            'exchange_rate_cache_hours': self.exchange_rate_cache_hours,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    def __repr__(self):
        return f'<CompanySettings company_id={self.company_id}>'


class GenerationHistory(db.Model):
    """Track PPT generation history"""
    __tablename__ = 'generation_history'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, default=1, index=True)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    product_count = db.Column(db.Integer, nullable=False)
    generation_date = db.Column(db.Date, nullable=True, index=True)
    content_fingerprint = db.Column(db.String(64), nullable=True, index=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='success')  # success, failed
    error_message = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'filename': self.filename,
            'product_count': self.product_count,
            'generation_date': self.generation_date.isoformat() if self.generation_date else None,
            'content_fingerprint': self.content_fingerprint,
            'generated_at': self.generated_at.isoformat(),
            'file_path': self.file_path,
            'status': self.status
        }
    
    def __repr__(self):
        return f'<GenerationHistory {self.filename}>'


class BackgroundAudio(db.Model):
    """Reusable background audio uploaded for MP4 generation."""
    __tablename__ = 'background_audio'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, default=1, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    file_path = db.Column(db.String(500), nullable=False)
    rights_confirmed = db.Column(db.Boolean, nullable=False, default=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        """Convert background audio to dictionary."""
        return {
            'id': self.id,
            'company_id': self.company_id,
            'original_filename': self.original_filename,
            'stored_filename': self.stored_filename,
            'file_path': self.file_path,
            'rights_confirmed': self.rights_confirmed,
            'uploaded_at': self.uploaded_at.isoformat(),
        }

    def __repr__(self):
        return f'<BackgroundAudio {self.original_filename}>'


class SocialConnection(db.Model):
    """Company-level connected social media account."""
    __tablename__ = 'social_connections'
    __table_args__ = (
        db.UniqueConstraint('company_id', 'provider', name='uq_company_social_provider'),
    )

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False, index=True)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    external_account_id = db.Column(db.String(255), nullable=True)
    external_account_name = db.Column(db.String(255), nullable=True)
    oauth_state = db.Column(db.String(255), nullable=True)
    connected_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def is_connected(self):
        return bool(self.refresh_token or self.access_token)

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'provider': self.provider,
            'connected': self.is_connected(),
            'external_account_id': self.external_account_id,
            'external_account_name': self.external_account_name,
            'connected_at': self.connected_at.isoformat() if self.connected_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class SocialPublishHistory(db.Model):
    """Track generated MP4 publishing attempts to social platforms."""
    __tablename__ = 'social_publish_history'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False, index=True)
    generation_id = db.Column(db.Integer, db.ForeignKey('generation_history.id'), nullable=True, index=True)
    filename = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='queued')
    external_post_id = db.Column(db.String(255), nullable=True)
    external_post_url = db.Column(db.String(500), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'provider': self.provider,
            'generation_id': self.generation_id,
            'filename': self.filename,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'external_post_id': self.external_post_id,
            'external_post_url': self.external_post_url,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
