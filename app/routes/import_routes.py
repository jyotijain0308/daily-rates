"""
CSV Import API routes
"""
import logging
import os
from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename
from csv_importer import ProductCSVImporter, get_csv_template, get_sample_csv, SAMPLE_CSV_FILENAME
from image_importer import ProductImageOCRImporter, ImageImportError, OCRUnavailableError
from pdf_importer import ProductPDFTableImporter, PDFImportError
from models import Product, ProductRateHistory

logger = logging.getLogger(__name__)
import_bp = Blueprint('imports', __name__, url_prefix='/api/import')

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
ALLOWED_IMAGE_EXTENSIONS = ProductImageOCRImporter.IMAGE_EXTENSIONS
ALLOWED_PDF_EXTENSIONS = {'pdf'}


def actionable_preview_rows(import_plan):
    """Return preview rows that will actually create or update products."""
    return [
        row for row in import_plan['rows']
        if row.get('action') != 'skipped'
    ]


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_image_file(filename):
    """Check if image file extension is allowed for OCR import."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def allowed_pdf_file(filename):
    """Check if file extension is allowed for PDF import."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PDF_EXTENSIONS


@import_bp.route('/sample', methods=['GET'])
def download_sample_csv():
    """Download sample CSV file with daily product rates"""
    try:
        content = get_sample_csv()
        return Response(
            content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={SAMPLE_CSV_FILENAME}',
            },
        )
    except Exception as e:
        logger.error(f"Error downloading sample CSV: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error downloading sample CSV: {str(e)}"
        }), 500


@import_bp.route('/preview-pdf', methods=['POST'])
def preview_pdf_import():
    """Extract product table rows from an uploaded PDF and preview generated CSV."""
    try:
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No PDF file provided'
            }), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No PDF selected'
            }), 400

        if not allowed_pdf_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': 'Only PDF files are allowed'
            }), 400

        rows, extraction_warnings = ProductPDFTableImporter.extract_rows_from_upload(file)
        content = ProductPDFTableImporter.rows_to_csv_content(rows)
        valid_rows, validation_errors = ProductCSVImporter.parse_csv_content(content)
        import_plan = ProductCSVImporter.build_import_plan(valid_rows)
        errors = extraction_warnings + validation_errors

        return jsonify({
            'status': 'success',
            'preview': {
                'valid_count': len(valid_rows),
                'error_count': len(errors),
                'sample_data': actionable_preview_rows(import_plan),
                'errors': errors,
                'source': 'pdf',
                'created_count': import_plan['created_count'],
                'updated_count': import_plan['updated_count'],
                'skipped_count': import_plan['skipped_count'],
                'large_change_count': import_plan['large_change_count'],
            },
            'content': content,
            'extracted_count': len(rows),
        }), 200

    except PDFImportError as e:
        logger.error(f"Error processing PDF import: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error previewing PDF import: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error previewing PDF import: {str(e)}"
        }), 500


@import_bp.route('/preview-image', methods=['POST'])
def preview_image_import():
    """Extract product table rows from an uploaded image and preview them."""
    try:
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

        if not allowed_image_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': 'Only PNG, JPG, JPEG, WEBP, BMP, and TIFF images are allowed'
            }), 400

        rows, extraction_errors, ocr_text = ProductImageOCRImporter.extract_rows_from_upload(file)
        content = ProductImageOCRImporter.rows_to_csv_content(rows)
        valid_rows, validation_errors = ProductCSVImporter.parse_csv_content(content)
        import_plan = ProductCSVImporter.build_import_plan(valid_rows)
        errors = extraction_errors + validation_errors

        return jsonify({
            'status': 'success',
            'preview': {
                'valid_count': len(valid_rows),
                'error_count': len(errors),
                'sample_data': actionable_preview_rows(import_plan),
                'errors': errors,
                'source': 'image',
                'created_count': import_plan['created_count'],
                'updated_count': import_plan['updated_count'],
                'skipped_count': import_plan['skipped_count'],
                'large_change_count': import_plan['large_change_count'],
            },
            'content': content,
            'ocr_text': ocr_text
        }), 200

    except OCRUnavailableError as e:
        logger.error(f"OCR unavailable: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 503
    except ImageImportError as e:
        logger.error(f"Error processing image import: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error previewing image import: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error previewing image import: {str(e)}"
        }), 500


@import_bp.route('/template', methods=['GET'])
def get_template():
    """Get CSV template"""
    try:
        template = get_csv_template()
        return jsonify({
            'status': 'success',
            'template': template
        }), 200
    except Exception as e:
        logger.error(f"Error getting template: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error getting template: {str(e)}"
        }), 500


@import_bp.route('/preview', methods=['POST'])
def preview_import():
    """Preview CSV before importing"""
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': 'Only CSV files are allowed'
            }), 400
        
        # Read file content
        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            return jsonify({
                'status': 'error',
                'message': 'File must be UTF-8 encoded'
            }), 400
        
        valid_rows, errors = ProductCSVImporter.parse_csv_content(content)
        import_plan = ProductCSVImporter.build_import_plan(valid_rows)
        
        return jsonify({
            'status': 'success',
            'preview': {
                'valid_count': len(valid_rows),
                'error_count': len(errors),
                'sample_data': actionable_preview_rows(import_plan),
                'errors': errors,
                'created_count': import_plan['created_count'],
                'updated_count': import_plan['updated_count'],
                'skipped_count': import_plan['skipped_count'],
                'large_change_count': import_plan['large_change_count'],
            },
            'content': content,
        }), 200
    
    except Exception as e:
        logger.error(f"Error previewing import: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error previewing import: {str(e)}"
        }), 500


@import_bp.route('/save', methods=['POST'])
def save_import():
    """Save previously previewed CSV content into the database"""
    try:
        data = request.get_json(silent=True) or {}
        content = data.get('content')

        if not content:
            return jsonify({
                'status': 'error',
                'message': 'No CSV content provided'
            }), 400

        valid_rows, errors = ProductCSVImporter.parse_csv_content(content)

        if not valid_rows:
            return jsonify({
                'status': 'error',
                'message': 'No valid products to import',
                'data': {'errors': errors}
            }), 400

        import_plan = ProductCSVImporter.build_import_plan(valid_rows)
        import_summary, import_errors = ProductCSVImporter.import_products(valid_rows)
        all_errors = errors + import_errors
        imported_count = import_summary['imported_count']

        return jsonify({
            'status': 'success' if imported_count > 0 else 'partial',
            'message': (
                f"Created {import_summary['created_count']}, "
                f"updated {import_summary['updated_count']}, "
                f"skipped {import_summary['skipped_count']} products"
            ),
            'data': {
                **import_summary,
                'imported_count': imported_count,
                'errors': all_errors,
                'preview': actionable_preview_rows(import_plan)
            }
        }), 200

    except Exception as e:
        logger.error(f"Error saving import: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error saving import: {str(e)}"
        }), 500


@import_bp.route('/upload', methods=['POST'])
def upload_and_import():
    """Upload and import CSV file"""
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': 'Only CSV files are allowed'
            }), 400
        
        # Ensure upload folder exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        try:
            # Import from file
            imported_count, errors, preview_data = ProductCSVImporter.import_from_file(file_path)
            
            return jsonify({
                'status': 'success' if imported_count > 0 else 'partial',
                'message': f'Imported {imported_count} products',
                'data': {
                    'imported_count': imported_count,
                    'errors': errors,
                    'preview': preview_data
                }
            }), 200
        
        finally:
            # Clean up temp file
            if os.path.exists(file_path):
                os.remove(file_path)
    
    except Exception as e:
        logger.error(f"Error during import: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error during import: {str(e)}"
        }), 500


@import_bp.route('/clear', methods=['POST'])
def clear_products():
    """Clear all products from database (for testing)"""
    try:
        count = Product.query.count()
        ProductRateHistory.query.delete()
        Product.query.delete()
        from wsgi import db
        db.session.commit()
        
        logger.warning(f"Cleared {count} products from database")
        return jsonify({
            'status': 'success',
            'message': f'Cleared {count} products',
            'data': {'cleared_count': count}
        }), 200
    
    except Exception as e:
        from wsgi import db
        db.session.rollback()
        logger.error(f"Error clearing products: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error clearing products: {str(e)}"
        }), 500
