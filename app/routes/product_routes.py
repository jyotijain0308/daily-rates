"""
Product management API routes
"""
import logging
from flask import Blueprint, request, jsonify
from src.config import COMPANY_DEFAULT_COUNTRY, COUNTRIES, CURRENCY
from models import Product
from wsgi import db

logger = logging.getLogger(__name__)
product_bp = Blueprint('products', __name__, url_prefix='/api/products')


@product_bp.route('/', methods=['GET'])
def get_all_products():
    """Get all products"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Pagination
        paginated = Product.query.paginate(page=page, per_page=per_page)
        
        return jsonify({
            'status': 'success',
            'data': [product.to_dict() for product in paginated.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated.total,
                'pages': paginated.pages
            }
        }), 200
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error fetching products: {str(e)}"
        }), 500


@product_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get product statistics"""
    try:
        total_products = Product.query.count()
        countries = db.session.query(
            Product.country_of_origin, db.func.count(Product.id)
        ).group_by(Product.country_of_origin).all()
        shipments = db.session.query(
            Product.shipment_by, db.func.count(Product.id)
        ).group_by(Product.shipment_by).all()

        return jsonify({
            'status': 'success',
            'data': {
                'total_products': total_products,
                'countries': {country: count for country, count in countries},
                'shipments': {shipment: count for shipment, count in shipments},
                'company_default_country': COMPANY_DEFAULT_COUNTRY,
                'currency': CURRENCY
            }
        }), 200
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error getting stats: {str(e)}"
        }), 500


@product_bp.route('/countries', methods=['GET'])
def get_countries():
    """Get configured countries for product rates"""
    return jsonify({
        'status': 'success',
        'data': COUNTRIES,
        'default_country': COMPANY_DEFAULT_COUNTRY
    }), 200


@product_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get a specific product by ID"""
    try:
        product = Product.query.get_or_404(product_id)
        return jsonify({
            'status': 'success',
            'data': product.to_dict()
        }), 200
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Product not found or error occurred: {str(e)}"
        }), 404


@product_bp.route('/', methods=['POST'])
def create_product():
    """Create a new product"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = [
            'country_of_origin',
            'shipment_by',
            'product_name',
            'weight_kg',
            'packing',
            'price_aed',
        ]
        if not data or any(field not in data for field in required_fields):
            return jsonify({
                'status': 'error',
                'message': "Missing required fields: country_of_origin, shipment_by, product_name, weight_kg, packing, price_aed"
            }), 400
        
        # Validate data types
        try:
            serial_no = int(data['serial_no']) if data.get('serial_no') not in (None, '') else None
            weight_kg = float(data['weight_kg'])
            price_aed = float(data['price_aed'])
        except (ValueError, TypeError):
            return jsonify({
                'status': 'error',
                'message': "serial_no must be a whole number, weight_kg and price_aed must be valid numbers"
            }), 400
        
        # Create product
        product = Product(
            serial_no=serial_no,
            country_of_origin=data['country_of_origin'].strip(),
            shipment_by=data['shipment_by'].strip(),
            product_name=data['product_name'].strip(),
            weight_kg=weight_kg,
            packing=data['packing'].strip(),
            price_aed=price_aed,
        )
        
        db.session.add(product)
        db.session.commit()
        
        logger.info(f"✓ Created product: {product.product_name}")
        return jsonify({
            'status': 'success',
            'message': 'Product created successfully',
            'data': product.to_dict()
        }), 201
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating product: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error creating product: {str(e)}"
        }), 500


@product_bp.route('/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update a product (e.g., update rates)"""
    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json()
        
        # Update allowed fields
        allowed_fields = [
            'serial_no',
            'country_of_origin',
            'shipment_by',
            'product_name',
            'weight_kg',
            'packing',
            'price_aed',
        ]
        
        for field in allowed_fields:
            if field in data:
                if field == 'serial_no':
                    try:
                        setattr(product, field, int(data[field]) if data[field] not in (None, '') else None)
                    except (ValueError, TypeError):
                        return jsonify({
                            'status': 'error',
                            'message': f"{field} must be a whole number"
                        }), 400
                elif field in ['weight_kg', 'price_aed']:
                    try:
                        setattr(product, field, float(data[field]))
                    except (ValueError, TypeError):
                        return jsonify({
                            'status': 'error',
                            'message': f"{field} must be a valid number"
                        }), 400
                else:
                    setattr(product, field, data[field].strip() if isinstance(data[field], str) else data[field])
        
        db.session.commit()
        logger.info(f"✓ Updated product: {product.product_name}")
        
        return jsonify({
            'status': 'success',
            'message': 'Product updated successfully',
            'data': product.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating product {product_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error updating product: {str(e)}"
        }), 500


@product_bp.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product"""
    try:
        product = Product.query.get_or_404(product_id)
        product_name = product.product_name
        
        db.session.delete(product)
        db.session.commit()
        
        logger.info(f"✓ Deleted product: {product_name}")
        return jsonify({
            'status': 'success',
            'message': f'Product "{product_name}" deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting product {product_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error deleting product: {str(e)}"
        }), 500
