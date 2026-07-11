"""Database models for PPT Daily Rates System"""
from datetime import datetime
from wsgi import db


class Product(db.Model):
    """Product model matching the CSV import contract"""
    __tablename__ = 'products'
    __table_args__ = (
        db.UniqueConstraint('product_name', 'country_of_origin', name='uq_product_origin'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    serial_no = db.Column(db.Integer, nullable=True)
    country_of_origin = db.Column(db.String(100), nullable=False, index=True)
    shipment_by = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(255), nullable=False, index=True)
    weight_kg = db.Column(db.Float, nullable=False)
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


class GenerationHistory(db.Model):
    """Track PPT generation history"""
    __tablename__ = 'generation_history'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    product_count = db.Column(db.Integer, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='success')  # success, failed
    error_message = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'filename': self.filename,
            'product_count': self.product_count,
            'generated_at': self.generated_at.isoformat(),
            'file_path': self.file_path,
            'status': self.status
        }
    
    def __repr__(self):
        return f'<GenerationHistory {self.filename}>'
