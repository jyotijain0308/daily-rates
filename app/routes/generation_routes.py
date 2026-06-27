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
    """Generate PPT or MP4 for a selected country"""
    try:
        data = request.get_json(silent=True) or {}
        country = (data.get('country') or '').strip()
        output_format = (data.get('format') or 'ppt').strip().lower()

        if not country:
            return jsonify({
                'status': 'error',
                'message': 'Please select a country before generating.'
            }), 400

        if output_format not in {'ppt', 'mp4'}:
            return jsonify({
                'status': 'error',
                'message': "Unsupported format. Use 'ppt' or 'mp4'."
            }), 400

        # Check if products exist
        product_count = Product.query.filter_by(country_of_origin=country).count()
        if product_count == 0:
            return jsonify({
                'status': 'error',
                'message': 'No products found for the selected country.'
            }), 400
        
        success, result, error_msg = PPTGenerationService.generate_ppt(
            country_filter=country,
            output_format=output_format,
        )
        
        if success:
            logger.info(f"✓ File generated: {result['filename']}")
            return jsonify({
                'status': 'success',
                'message': f"Generated {output_format.upper()} for {country} with {product_count} products",
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
    """Download a generated PPT or MP4 file"""
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
        total_generations = GenerationHistory.query.count()
        latest_ppt = PPTGenerationService.get_latest_ppt()
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_products': total_products,
                'countries': countries,
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
