"""
PPT Generation and Download API routes
"""
import hashlib
import json
import logging
import os
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_file
from app.services.company_service import company_settings_for, current_company, current_company_id
from app.services.storage_service import resolve_generated_file
from app.services.generation.job_service import create_job, list_generation_jobs, read_job, request_cancel, start_generation_job
from app.models import BackgroundAudio, Product, GenerationHistory, ProductRateHistory, SocialConnection, SocialPublishHistory
from app.services.ppt_service import PPTGenerationService
from app.services.generation.product_image_service import ProductImageService
from wsgi import db

logger = logging.getLogger(__name__)
generation_bp = Blueprint('generation', __name__, url_prefix='/api/generation')
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac', 'ogg'}
product_image_service = ProductImageService()


def _allowed_audio_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


def _parse_optional_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def background_audio_to_dict(audio):
    data = audio.to_dict()
    data['audio_url'] = f"/api/generation/audio/{audio.id}/preview"
    return data


def _slugify_share_part(value):
    return ''.join(char if char.isalnum() else '_' for char in str(value or '').lower()).strip('_')


def _share_metadata_for_filename(filename, company_id):
    base_name = Path(filename).stem
    if base_name.endswith('_products_price_list'):
        file_slug = base_name[:-len('_products_price_list')]
    else:
        file_slug = base_name.rsplit('_products_price_list_', 1)[0]

    rows = Product.query.filter_by(company_id=company_id).all()
    matches = []
    for product in rows:
        country_slug = _slugify_share_part(product.country_of_origin)
        shipment_slug = _slugify_share_part(product.shipment_by)
        expected_with_shipment = '_'.join(part for part in [country_slug, shipment_slug] if part)
        if file_slug == expected_with_shipment or file_slug.startswith(f'{expected_with_shipment}_'):
            matches.append(product)
            continue
        if file_slug == country_slug:
            matches.append(product)

    if not matches:
        return {
            'filename': filename,
            'country': '',
            'shipment_by': '',
            'product_names': [],
            'product_count': 0,
        }

    country = matches[0].country_of_origin
    shipment_by = matches[0].shipment_by
    if len({product.shipment_by for product in matches}) > 1:
        shipment_by = ''
    product_names = sorted({product.product_name for product in matches if product.product_name})
    return {
        'filename': filename,
        'country': country,
        'shipment_by': shipment_by,
        'product_names': product_names,
        'product_count': len(product_names),
    }


def _product_image_signature(product):
    image_path = product_image_service.get_product_image_path(
        product.product_name,
        product.country_of_origin,
        fetch_if_missing=False,
    )
    if not image_path:
        return {'path': None, 'mtime_ns': None, 'size': None, 'sha256': None}

    image_file = product_image_service._resolve_asset(image_path)
    if not image_file or not image_file.exists():
        return {'path': image_path, 'mtime_ns': None, 'size': None, 'sha256': None}

    stat = image_file.stat()
    return {
        'path': image_path,
        'mtime_ns': stat.st_mtime_ns,
        'size': stat.st_size,
        'sha256': hashlib.sha256(image_file.read_bytes()).hexdigest(),
    }


def _generation_fingerprint(company_id, country, shipment_by, products, generation_date=None):
    generation_date = generation_date or date.today()
    product_rows = []
    for product in products:
        product_rows.append({
            'name': product.product_name,
            'weight_kg': product.weight_kg,
            'packing': product.packing,
            'price_aed': round(float(product.price_aed), 4),
            'image': _product_image_signature(product),
        })

    payload = {
        'company_id': company_id,
        'country': country,
        'shipment_by': shipment_by,
        'generation_date': generation_date.isoformat(),
        'products': sorted(product_rows, key=lambda item: (
            item['name'] or '',
            item['weight_kg'] or '',
            item['packing'] or '',
        )),
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return fingerprint, payload


def _find_duplicate_generation(company_id, fingerprint, generation_date):
    return GenerationHistory.query.filter_by(
        company_id=company_id,
        status='success',
        content_fingerprint=fingerprint,
        generation_date=generation_date,
    ).order_by(GenerationHistory.generated_at.desc()).first()


@generation_bp.route('/generate', methods=['POST'])
def generate_ppt():
    """Generate MP4 for a selected country."""
    try:
        data = request.get_json(silent=True) or {}
        country = (data.get('country') or '').strip()
        shipment_by = (data.get('shipment_by') or '').strip()
        audio_path = (data.get('audio_path') or '').strip()
        audio_id = _parse_optional_int(data.get('audio_id'))
        force_generation = bool(data.get('force'))
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
        company_id = current_company_id()
        products = Product.query.filter_by(
            company_id=company_id,
            country_of_origin=country,
            shipment_by=shipment_by,
        ).order_by(Product.product_name.asc(), Product.id.asc()).all()
        product_count = len(products)
        if product_count == 0:
            return jsonify({
                'status': 'error',
                'message': 'No products found for the selected country and shipment method.'
            }), 400

        generation_date = date.today()
        content_fingerprint, _fingerprint_payload = _generation_fingerprint(
            company_id,
            country,
            shipment_by,
            products,
            generation_date=generation_date,
        )
        duplicate = _find_duplicate_generation(company_id, content_fingerprint, generation_date)
        if duplicate and not force_generation:
            return jsonify({
                'status': 'duplicate',
                'message': 'An MP4 with the same country, shipment, date, product names, images, and rates already exists.',
                'data': {
                    'duplicate': True,
                    'existing_generation': duplicate.to_dict(),
                    'content_fingerprint': content_fingerprint,
                    'fingerprint_criteria': {
                        'country': country,
                        'shipment_by': shipment_by,
                        'generation_date': generation_date.isoformat(),
                        'product_count': product_count,
                    },
                },
            }), 409

        if data.get('audio_id') and audio_id is None:
            return jsonify({
                'status': 'error',
                'message': 'Selected background audio id is invalid.'
            }), 400

        if audio_id:
            audio = BackgroundAudio.query.filter_by(id=audio_id, company_id=company_id).first()
            if not audio or not Path(audio.file_path).exists():
                return jsonify({
                    'status': 'error',
                    'message': 'Selected background audio file was not found.'
                }), 400
            audio_path = audio.file_path

        if audio_path:
            audio_file = Path(audio_path)
            audio_root = Path(current_app.config.get('GENERATION_AUDIO_DIR', 'uploads/audio')).resolve()
            try:
                is_allowed_path = audio_file.resolve().is_relative_to(audio_root)
            except AttributeError:
                is_allowed_path = str(audio_file.resolve()).startswith(str(audio_root))
            if not is_allowed_path or not audio_file.exists():
                return jsonify({
                    'status': 'error',
                    'message': 'Selected background audio file was not found.'
                }), 400
        
        job = create_job(country, shipment_by, product_count, company_id=company_id)
        start_generation_job(
            current_app._get_current_object(),
            job['job_id'],
            country,
            shipment_by,
            audio_path=audio_path or None,
            company_id=company_id,
            generation_date=generation_date.isoformat(),
            content_fingerprint=content_fingerprint,
        )

        return jsonify({
            'status': 'accepted',
            'message': f"Started {output_format.upper()} generation for {country} / {shipment_by}",
            'data': job,
        }), 202
    
    except Exception as e:
        logger.error(f"Error generating file: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating file: {str(e)}'
        }), 500


@generation_bp.route('/audio', methods=['GET'])
def list_generation_audio():
    """List reusable background audio files."""
    audios = BackgroundAudio.query.filter_by(company_id=current_company_id()).order_by(BackgroundAudio.uploaded_at.desc()).all()
    return jsonify({
        'status': 'success',
        'data': [background_audio_to_dict(audio) for audio in audios],
    }), 200


@generation_bp.route('/audio', methods=['POST'])
def upload_generation_audio():
    """Upload optional background audio for MP4 generation."""
    try:
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No audio file provided'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No audio file selected'
            }), 400

        if not _allowed_audio_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': 'Only MP3, WAV, M4A, AAC, and OGG audio files are allowed'
            }), 400

        rights_confirmed = (request.form.get('rights_confirmed') or '').lower() == 'true'
        if not rights_confirmed:
            return jsonify({
                'status': 'error',
                'message': 'Confirm that you own or have licensed rights to use this audio.'
            }), 400

        extension = file.filename.rsplit('.', 1)[1].lower()
        audio_dir = Path(current_app.config.get('GENERATION_AUDIO_DIR', 'uploads/audio'))
        audio_dir.mkdir(parents=True, exist_ok=True)
        stored_filename = f"background_audio_{uuid.uuid4().hex}.{extension}"
        audio_path = audio_dir / stored_filename
        file.save(audio_path)

        audio = BackgroundAudio(
            company_id=current_company_id(),
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_path=str(audio_path),
            rights_confirmed=True,
        )
        db.session.add(audio)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Background audio uploaded',
            'data': background_audio_to_dict(audio),
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading generation audio: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error uploading audio: {str(e)}'
        }), 500


@generation_bp.route('/audio/<int:audio_id>/preview', methods=['GET'])
def preview_generation_audio(audio_id):
    """Stream a reusable background audio file."""
    audio = BackgroundAudio.query.filter_by(id=audio_id, company_id=current_company_id()).first_or_404()
    path = Path(audio.file_path)
    if not path.exists():
        return jsonify({
            'status': 'error',
            'message': 'Audio file not found'
        }), 404

    return send_file(path, as_attachment=False, conditional=True)


@generation_bp.route('/jobs/<job_id>', methods=['GET'])
def get_generation_job(job_id):
    """Get status for a background MP4 generation job."""
    job = read_job(job_id)
    if not job:
        return jsonify({
            'status': 'error',
            'message': 'Generation job not found'
        }), 404
    if job.get('company_id') and job.get('company_id') != current_company_id():
        return jsonify({
            'status': 'error',
            'message': 'Generation job not found'
        }), 404

    return jsonify({
        'status': 'success',
        'data': job,
    }), 200


@generation_bp.route('/jobs/<job_id>/cancel', methods=['POST'])
def cancel_generation_job(job_id):
    """Request cancellation for a running MP4 generation job."""
    job = read_job(job_id)
    if not job or (job.get('company_id') and job.get('company_id') != current_company_id()):
        return jsonify({
            'status': 'error',
            'message': 'Generation job not found'
        }), 404

    if not request_cancel(job_id):
        return jsonify({
            'status': 'error',
            'message': 'Generation job not found'
        }), 404

    return jsonify({
        'status': 'success',
        'message': 'Cancellation requested',
    }), 200


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
        
        generation = GenerationHistory.query.filter_by(filename=filename).first()
        if generation and generation.company_id != current_company_id():
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
        filepath = resolve_generated_file(generation.file_path if generation else filename)
        
        # Check if file exists
        if not filepath:
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

        generation = GenerationHistory.query.filter_by(filename=filename).first()
        if generation and generation.company_id != current_company_id():
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
        filepath = resolve_generated_file(generation.file_path if generation else filename)
        if not filepath:
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


@generation_bp.route('/share-metadata/<filename>', methods=['GET'])
def get_share_metadata(filename):
    """Return country, shipment, and product names for a generated MP4."""
    try:
        if '/' in filename or '\\' in filename or filename.startswith('.'):
            return jsonify({
                'status': 'error',
                'message': 'Invalid filename'
            }), 400

        if not filename.lower().endswith('.mp4'):
            return jsonify({
                'status': 'error',
                'message': 'Share metadata is only available for MP4 files'
            }), 400

        company_id = current_company_id()
        generation = GenerationHistory.query.filter_by(filename=filename).first()
        if generation and generation.company_id != company_id:
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404

        return jsonify({
            'status': 'success',
            'data': _share_metadata_for_filename(filename, company_id),
        }), 200

    except Exception as e:
        logger.error(f"Error getting share metadata: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting share metadata: {str(e)}'
        }), 500


@generation_bp.route('/status', methods=['GET'])
def get_status():
    """Get generation status and statistics"""
    try:
        from wsgi import db
        
        company = current_company()
        company_id = company.id
        company_settings = company.settings or company_settings_for(company_id)
        today_start = datetime.combine(date.today(), time.min)
        tomorrow_start = datetime.combine(date.today() + timedelta(days=1), time.min)
        total_products = Product.query.filter_by(company_id=company_id).count()
        countries = [
            country for (country,) in db.session.query(Product.country_of_origin)
            .filter(Product.company_id == company_id)
            .distinct()
            .order_by(Product.country_of_origin)
            .all()
        ]
        shipment_rows = db.session.query(
            Product.country_of_origin,
            Product.shipment_by,
        ).filter(Product.company_id == company_id).distinct().order_by(Product.country_of_origin, Product.shipment_by).all()
        shipments_by_country = {}
        for country, shipment_by in shipment_rows:
            shipments_by_country.setdefault(country, []).append(shipment_by)
        total_generations = GenerationHistory.query.filter_by(company_id=company_id).count()
        success_generations = GenerationHistory.query.filter_by(
            company_id=company_id,
            status='success',
        ).count()
        today_generations = GenerationHistory.query.filter(
            GenerationHistory.company_id == company_id,
            GenerationHistory.generated_at >= today_start,
            GenerationHistory.generated_at < tomorrow_start,
        ).count()
        today_success_generations = GenerationHistory.query.filter(
            GenerationHistory.company_id == company_id,
            GenerationHistory.status == 'success',
            GenerationHistory.generated_at >= today_start,
            GenerationHistory.generated_at < tomorrow_start,
        ).count()
        today_failed_generations = GenerationHistory.query.filter(
            GenerationHistory.company_id == company_id,
            GenerationHistory.status == 'failed',
            GenerationHistory.generated_at >= today_start,
            GenerationHistory.generated_at < tomorrow_start,
        ).count()
        today_generation_rows = GenerationHistory.query.filter(
            GenerationHistory.company_id == company_id,
            GenerationHistory.generated_at >= today_start,
            GenerationHistory.generated_at < tomorrow_start,
        ).order_by(GenerationHistory.generated_at.desc()).limit(20).all()
        failed_generations = GenerationHistory.query.filter_by(
            company_id=company_id,
            status='failed',
        ).count()
        connected_social_platform_details = _connected_social_platform_details(company_id)
        connected_social_platforms = [
            platform['label']
            for platform in connected_social_platform_details
        ]
        last_import = db.session.query(db.func.max(ProductRateHistory.changed_at)).join(
            Product,
            Product.id == ProductRateHistory.product_id,
        ).filter(
            Product.company_id == company_id,
            ProductRateHistory.changed_by == 'import',
        ).scalar()
        active_generation_jobs = list_generation_jobs(
            company_id=company_id,
            statuses={'queued', 'running'},
            updated_since=today_start,
        )
        products_updated_today = Product.query.filter(
            Product.company_id == company_id,
            Product.updated_at >= today_start,
            Product.updated_at < tomorrow_start,
        ).count()
        updated_product_history_query = ProductRateHistory.query.join(
            Product,
            Product.id == ProductRateHistory.product_id,
        ).filter(
            Product.company_id == company_id,
            ProductRateHistory.changed_at >= today_start,
            ProductRateHistory.changed_at < tomorrow_start,
        )
        updated_product_history_rows = updated_product_history_query.order_by(
            ProductRateHistory.changed_at.desc()
        ).limit(50).all()
        updated_product_summary_rows = updated_product_history_query.order_by(
            ProductRateHistory.changed_at.desc()
        ).all()
        large_rate_change_query = ProductRateHistory.query.join(
            Product,
            Product.id == ProductRateHistory.product_id,
        ).filter(
            Product.company_id == company_id,
            ProductRateHistory.changed_by == 'import',
            ProductRateHistory.changed_at >= today_start,
            ProductRateHistory.changed_at < tomorrow_start,
            ProductRateHistory.old_price_aed.isnot(None),
            ProductRateHistory.old_price_aed != 0,
            db.func.abs(
                (ProductRateHistory.new_price_aed - ProductRateHistory.old_price_aed)
                / ProductRateHistory.old_price_aed
            ) >= 0.2,
        )
        large_rate_change_rows = large_rate_change_query.order_by(
            ProductRateHistory.changed_at.desc()
        ).limit(50).all()
        large_rate_change_summary_rows = large_rate_change_query.order_by(
            ProductRateHistory.changed_at.desc()
        ).all()
        large_rate_change_product_ids = {
            history.product_id for history in large_rate_change_summary_rows
        }
        updated_products_today = _updated_products_for_dashboard(
            updated_product_history_rows,
            limit=50,
            large_rate_change_product_ids=large_rate_change_product_ids,
        )
        updated_products_rate_summary = _updated_products_rate_summary(
            updated_product_summary_rows,
            large_rate_change_product_ids,
            total_products=products_updated_today,
        )
        large_rate_change_products_today = _updated_products_for_dashboard(
            large_rate_change_rows,
            limit=50,
            large_rate_change_product_ids=large_rate_change_product_ids,
        )
        large_rate_changes_today = len(large_rate_change_product_ids)
        latest_ppt = PPTGenerationService.get_latest_ppt()
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_products': total_products,
                'countries': countries,
                'shipments_by_country': shipments_by_country,
                'total_generations': total_generations,
                'success_generations': success_generations,
                'today_generations': today_generations,
                'today_success_generations': today_success_generations,
                'today_failed_generations': today_failed_generations,
                'today_generation_history': [
                    _generation_summary_for_dashboard(generation, company_id)
                    for generation in today_generation_rows
                ],
                'failed_generations': failed_generations,
                'connected_social_platform_count': len(connected_social_platforms),
                'connected_social_platforms': connected_social_platforms,
                'connected_social_platform_details': connected_social_platform_details,
                'last_import_at': last_import.isoformat() if last_import else None,
                'active_generation_jobs': len(active_generation_jobs),
                'active_generation_job_details': [
                    _generation_job_summary_for_dashboard(job, company_id)
                    for job in active_generation_jobs[:10]
                ],
                'products_updated_today': products_updated_today,
                'updated_products_today': updated_products_today,
                'updated_products_rate_summary': updated_products_rate_summary,
                'large_rate_change_products_today': large_rate_change_products_today,
                'large_rate_changes_today': large_rate_changes_today,
                'configured_company': {
                    'id': company.id,
                    'name': company.name,
                    'currency': company_settings.currency,
                },
                'latest_generation': latest_ppt
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting status: {str(e)}'
        }), 500

def _connected_social_platform_details(company_id):
    rows = SocialConnection.query.filter_by(company_id=company_id).all()
    platforms = {
        connection.provider
        for connection in rows
        if connection.is_connected()
    }

    facebook_connection = next(
        (
            connection for connection in rows
            if connection.provider == 'facebook' and connection.is_connected()
        ),
        None,
    )
    if facebook_connection:
        try:
            from app.services.social.facebook_service import get_connected_instagram_account
            if get_connected_instagram_account(facebook_connection):
                platforms.add('instagram')
        except Exception:
            pass

    labels = {
        'youtube': 'YouTube',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'linkedin_page': 'LinkedIn Page',
        'linkedin_personal': 'LinkedIn',
        'x': 'X',
    }
    return [
        {
            'provider': provider,
            'label': labels.get(provider, provider.title()),
        }
        for provider in sorted(platforms)
        if provider in labels
    ]


def _updated_products_for_dashboard(
    history_rows,
    limit=10,
    large_rate_change_product_ids=None,
):
    large_rate_change_product_ids = large_rate_change_product_ids or set()
    products = []
    seen_product_ids = set()
    for history in history_rows:
        if history.product_id in seen_product_ids:
            continue
        seen_product_ids.add(history.product_id)
        old_price = history.old_price_aed
        new_price = history.new_price_aed
        change_percent = None
        if old_price not in (None, 0):
            change_percent = ((new_price - old_price) / old_price) * 100

        products.append({
            'product_id': history.product_id,
            'product_name': history.product.product_name,
            'country_of_origin': history.product.country_of_origin,
            'shipment_by': history.product.shipment_by,
            'old_price_aed': old_price,
            'new_price_aed': new_price,
            'change_percent': round(change_percent, 1) if change_percent is not None else None,
            'is_large_rate_change': history.product_id in large_rate_change_product_ids,
            'changed_by': history.changed_by,
            'changed_at': history.changed_at.isoformat(),
        })
        if len(products) >= limit:
            break
    return products


def _updated_products_rate_summary(history_rows, large_rate_change_product_ids=None, total_products=None):
    large_rate_change_product_ids = large_rate_change_product_ids or set()
    summary = {
        'increased': 0,
        'decreased': 0,
        'no_change': 0,
        'new_or_no_previous': 0,
        'large_changes': len(large_rate_change_product_ids),
    }
    seen_product_ids = set()
    for history in history_rows:
        if history.product_id in seen_product_ids:
            continue
        seen_product_ids.add(history.product_id)
        if history.old_price_aed in (None, 0):
            summary['new_or_no_previous'] += 1
        elif history.new_price_aed > history.old_price_aed:
            summary['increased'] += 1
        elif history.new_price_aed < history.old_price_aed:
            summary['decreased'] += 1
    summary['total'] = total_products if total_products is not None else len(seen_product_ids)
    summary['no_change'] = max(
        summary['total'] - summary['increased'] - summary['decreased'],
        0,
    )
    return summary


def _generation_job_summary_for_dashboard(job, company_id):
    country = job.get('country') or ''
    shipment_by = job.get('shipment_by') or ''
    product_count = job.get('product_count') or 0
    if country and shipment_by:
        product_count = Product.query.filter_by(
            company_id=company_id,
            country_of_origin=country,
            shipment_by=shipment_by,
        ).count()

    return {
        'job_id': job.get('job_id'),
        'status': job.get('status') or '',
        'country': country,
        'shipment_by': shipment_by,
        'product_count': product_count,
        'message': job.get('message') or '',
        'created_at': job.get('created_at'),
        'updated_at': job.get('updated_at'),
    }


def _generation_summary_for_dashboard(generation, company_id):
    data = generation.to_dict()
    metadata = _share_metadata_for_filename(generation.filename, company_id)
    data['country'] = metadata.get('country') or ''
    data['shipment_by'] = metadata.get('shipment_by') or ''
    data['error_message'] = generation.error_message or ''
    data['share_statuses'] = _share_statuses_for_generation(generation, company_id)
    return data


def _share_statuses_for_generation(generation, company_id):
    rows = SocialPublishHistory.query.filter(
        SocialPublishHistory.company_id == company_id,
        db.or_(
            SocialPublishHistory.generation_id == generation.id,
            SocialPublishHistory.filename == generation.filename,
        ),
    ).order_by(SocialPublishHistory.updated_at.desc()).all()

    latest_by_provider = {}
    for row in rows:
        if row.provider not in latest_by_provider:
            latest_by_provider[row.provider] = row

    labels = {
        'youtube': 'YouTube',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'linkedin_page': 'LinkedIn Page',
        'linkedin_personal': 'LinkedIn',
        'x': 'X',
    }
    return [
        {
            'provider': publish.provider,
            'label': labels.get(publish.provider, publish.provider.title()),
            'status': publish.status,
            'external_post_url': publish.external_post_url,
            'updated_at': publish.updated_at.isoformat(),
            'error_message': publish.error_message or '',
        }
        for publish in latest_by_provider.values()
        if publish.provider in labels
    ]
