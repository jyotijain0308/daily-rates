"""
PPT Generation and Download API routes
"""
import logging
import os
from flask import Blueprint, jsonify, request, send_file
from models import Product, GenerationHistory
from ppt_service import PPTGenerationService
from wsgi import db

logger = logging.getLogger(__name__)
generation_bp = Blueprint('generation', __name__, url_prefix='/api/generation')


@generation_bp.route('/generate', methods=['POST'])
def generate_ppt():
    """Generate MP4 for a selected country."""
    try:
        data = request.get_json(silent=True) or {}
        country = (data.get('country') or '').strip()
        shipment_by = (data.get('shipment_by') or '').strip()
        output_format = 'mp4'

        if not country:
            return jsonify({
                'status': 'error',
                'message': 'Please select a country before generating.'
            }), 400

        if not shipment_by:
            return jsonify({
                'status': 'error',
                'message': 'Please select a shipment method before generating.'
            }), 400

        # Check if products exist
        product_count = Product.query.filter_by(
            country_of_origin=country,
            shipment_by=shipment_by,
        ).count()
        if product_count == 0:
            return jsonify({
                'status': 'error',
                'message': 'No products found for the selected country and shipment method.'
            }), 400
        
        success, result, error_msg = PPTGenerationService.generate_ppt(
            country_filter=country,
            shipment_filter=shipment_by,
            output_format=output_format,
        )
        
        if success:
            logger.info(f"✓ File generated: {result['filename']}")
            return jsonify({
                'status': 'success',
                'message': f"Generated {output_format.upper()} for {country} / {shipment_by} with {product_count} products",
                'data': result
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 500
    
    except Exception as e:
        logger.error(f"Error generating file: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating file: {str(e)}'
        }), 500


@generation_bp.route('/latest', methods=['GET'])
def get_latest_ppt():
    """Get information about the latest generated PPT"""
    try:
        ppt_info = PPTGenerationService.get_latest_ppt()
        
        if ppt_info:
            return jsonify({
                'status': 'success',
                'data': ppt_info
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'No PPT has been generated yet'
            }), 404
    
    except Exception as e:
        logger.error(f"Error getting latest PPT: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting latest PPT: {str(e)}'
        }), 500


@generation_bp.route('/history', methods=['GET'])
def get_history():
    """Get generation history"""
    try:
        history = PPTGenerationService.get_generation_history(limit=20)
        
        return jsonify({
            'status': 'success',
            'data': history
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting history: {str(e)}'
        }), 500


@generation_bp.route('/download/<filename>', methods=['GET'])
def download_ppt(filename):
    """Download a generated MP4 file."""
    try:
        # Security: validate filename
        if '/' in filename or '\\' in filename or filename.startswith('.'):
            return jsonify({
                'status': 'error',
                'message': 'Invalid filename'
            }), 400
        
        filepath = os.path.join('output', filename)
        
        # Check if file exists
        if not os.path.exists(filepath):
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
        
        logger.info(f"✓ Downloading PPT: {filename}")
        
        mimetype = 'video/mp4' if filename.lower().endswith('.mp4') else 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        return send_file(filepath, mimetype=mimetype, as_attachment=True, download_name=filename)
    
    except Exception as e:
        logger.error(f"Error downloading PPT: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error downloading PPT: {str(e)}'
        }), 500


@generation_bp.route('/preview/<filename>', methods=['GET'])
def preview_mp4(filename):
    """Preview a generated MP4 file inline in the browser."""
    try:
        if '/' in filename or '\\' in filename or filename.startswith('.'):
            return jsonify({
                'status': 'error',
                'message': 'Invalid filename'
            }), 400

        if not filename.lower().endswith('.mp4'):
            return jsonify({
                'status': 'error',
                'message': 'Preview is only available for MP4 files'
            }), 400

        filepath = os.path.join('output', filename)
        if not os.path.exists(filepath):
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404

        logger.info(f"✓ Previewing MP4: {filename}")
        return send_file(filepath, mimetype='video/mp4', as_attachment=False, conditional=True)

    except Exception as e:
        logger.error(f"Error previewing MP4: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error previewing MP4: {str(e)}'
        }), 500


@generation_bp.route('/status', methods=['GET'])
def get_status():
    """Get generation status and statistics"""
    try:
        from wsgi import db
        from models import GenerationHistory
        
        total_products = Product.query.count()
        countries = [
            country for (country,) in db.session.query(Product.country_of_origin)
            .distinct()
            .order_by(Product.country_of_origin)
            .all()
        ]
        shipment_rows = db.session.query(
            Product.country_of_origin,
            Product.shipment_by,
        ).distinct().order_by(Product.country_of_origin, Product.shipment_by).all()
        shipments_by_country = {}
        for country, shipment_by in shipment_rows:
            shipments_by_country.setdefault(country, []).append(shipment_by)
        total_generations = GenerationHistory.query.count()
        latest_ppt = PPTGenerationService.get_latest_ppt()
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_products': total_products,
                'countries': countries,
                'shipments_by_country': shipments_by_country,
                'total_generations': total_generations,
                'latest_generation': latest_ppt
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting status: {str(e)}'
        }), 500
