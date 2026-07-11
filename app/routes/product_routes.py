"""
Product management API routes
"""
import logging
from pathlib import Path

from flask import Blueprint, request, jsonify, send_from_directory, url_for, Response
from PIL import UnidentifiedImageError
from csv_importer import products_to_csv
from src.config import COMPANY_DEFAULT_COUNTRY, COUNTRIES, CURRENCY
from src.product_image_service import ProductImageService
from models import Product, ProductRateHistory
from wsgi import db

logger = logging.getLogger(__name__)
product_bp = Blueprint('products', __name__, url_prefix='/api/products')
product_image_service = ProductImageService()


def product_to_dict(product):
    """Serialize a product with the listing image URL."""
    data = product.to_dict()
    image_path = product_image_service.get_product_image_path(
        product.product_name,
        product.country_of_origin,
        fetch_if_missing=False,
    )
    if image_path:
        image_file = product_image_service.assets_root / image_path
        version = int(image_file.stat().st_mtime) if image_file.exists() else None
        data['image_url'] = url_for(
            'products.get_product_image',
            filename=Path(image_path).name,
            v=version,
        )
    else:
        data['image_url'] = None
    return data


@product_bp.route('/image/<path:filename>', methods=['GET'])
def get_product_image(filename):
    """Serve cached product images used by PPT/MP4 generation."""
    image_dir = product_image_service.assets_root / 'assets' / 'products'
    return send_from_directory(image_dir, Path(filename).name)


@product_bp.route('/<int:product_id>/image', methods=['POST'])
def update_product_image(product_id):
    """Upload a manual image override for a product."""
    try:
        product = Product.query.get_or_404(product_id)

        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No image file provided'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No image selected'
            }), 400

        if not file.mimetype.startswith('image/'):
            return jsonify({
                'status': 'error',
                'message': 'Only image files are allowed'
            }), 400

        product_image_service.save_product_image(product.product_name, file.stream)

        return jsonify({
            'status': 'success',
            'message': 'Product image updated successfully',
            'data': product_to_dict(product)
        }), 200

    except UnidentifiedImageError:
        return jsonify({
            'status': 'error',
            'message': 'The uploaded file is not a readable image'
        }), 400
    except Exception as e:
        logger.error(f"Error updating product image {product_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error updating product image: {str(e)}"
        }), 500


@product_bp.route('/<int:product_id>/image/pexels', methods=['POST'])
def fetch_product_image_from_pexels(product_id):
    """Fetch or refresh a product image from Pexels."""
    try:
        product = Product.query.get_or_404(product_id)
        image_path = product_image_service.fetch_product_image(
            product.product_name,
            product.country_of_origin,
        )

        if not image_path:
            return jsonify({
                'status': 'error',
                'message': 'Could not fetch an image from Pexels. Check PEXELS_API_KEY or try another product name.'
            }), 404

        return jsonify({
            'status': 'success',
            'message': 'Product image fetched from Pexels',
            'data': product_to_dict(product)
        }), 200

    except Exception as e:
        logger.error(f"Error fetching Pexels image for product {product_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error fetching Pexels image: {str(e)}"
        }), 500


@product_bp.route('/<int:product_id>/image/pexels/search', methods=['POST'])
def search_product_images_from_pexels(product_id):
    """Search Pexels for selectable product image candidates."""
    try:
        product = Product.query.get_or_404(product_id)
        payload = request.get_json(silent=True) or {}
        description = (payload.get('description') or '').strip()
        page = payload.get('page') or 1

        images = product_image_service.search_product_images(
            product.product_name,
            product.country_of_origin,
            description=description,
            page=page,
            per_page=5,
        )

        if not images:
            return jsonify({
                'status': 'error',
                'message': 'No matching Pexels images found. Try a different description.'
            }), 404

        return jsonify({
            'status': 'success',
            'message': 'Pexels image options loaded',
            'data': images
        }), 200

    except Exception as e:
        logger.error(f"Error searching Pexels images for product {product_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error searching Pexels images: {str(e)}"
        }), 500


@product_bp.route('/<int:product_id>/image/pexels/select', methods=['POST'])
def select_product_image_from_pexels(product_id):
    """Save a selected Pexels image for a product."""
    try:
        product = Product.query.get_or_404(product_id)
        payload = request.get_json(silent=True) or {}
        image_url = (payload.get('image_url') or '').strip()

        if not image_url:
            return jsonify({
                'status': 'error',
                'message': 'No Pexels image URL selected'
            }), 400

        image_path = product_image_service.save_product_image_from_url(
            product.product_name,
            image_url,
        )

        if not image_path:
            return jsonify({
                'status': 'error',
                'message': 'Could not save the selected Pexels image.'
            }), 400

        return jsonify({
            'status': 'success',
            'message': 'Product image updated from Pexels',
            'data': product_to_dict(product)
        }), 200

    except Exception as e:
        logger.error(f"Error saving selected Pexels image for product {product_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error saving selected Pexels image: {str(e)}"
        }), 500


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
            'data': [product_to_dict(product) for product in paginated.items],
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


@product_bp.route('/export', methods=['GET'])
def export_products():
    """Export all products as a CSV sheet that can be imported after rate updates."""
    try:
        products = Product.query.order_by(
            Product.serial_no.is_(None),
            Product.serial_no,
            Product.product_name,
        ).all()
        content = products_to_csv(products)

        return Response(
            content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=all_products_rate_update.csv',
            },
        )
    except Exception as e:
        logger.error(f"Error exporting products: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error exporting products: {str(e)}"
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
            'data': product_to_dict(product)
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
        db.session.add(ProductRateHistory(
            product=product,
            old_price_aed=None,
            new_price_aed=price_aed,
            changed_by='manual',
        ))
        db.session.commit()
        
        logger.info(f"✓ Created product: {product.product_name}")
        return jsonify({
            'status': 'success',
            'message': 'Product created successfully',
            'data': product_to_dict(product)
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
        old_price_aed = float(product.price_aed)
        
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
        
        if 'price_aed' in data and float(product.price_aed) != old_price_aed:
            db.session.add(ProductRateHistory(
                product=product,
                old_price_aed=old_price_aed,
                new_price_aed=float(product.price_aed),
                changed_by='manual',
            ))

        db.session.commit()
        logger.info(f"✓ Updated product: {product.product_name}")
        
        return jsonify({
            'status': 'success',
            'message': 'Product updated successfully',
            'data': product_to_dict(product)
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
