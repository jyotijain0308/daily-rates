"""Company management API routes."""
import logging
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file, url_for
from PIL import Image, UnidentifiedImageError

from app.services.company_service import create_company, current_company, current_company_id, ensure_default_company
from app.models import Company, CompanySettings
from app.services.generation import config
from wsgi import db

logger = logging.getLogger(__name__)
company_bp = Blueprint('companies', __name__, url_prefix='/api/companies')
COMPANY_LOGO_SIZE = (1200, 400)
DESTINATION_LOGO_SIZE = (800, 500)
ASSET_FIELDS = {
    'company_logo_image': {
        'filename': 'company_logo',
        'size': COMPANY_LOGO_SIZE,
    },
    'destination_logo_image': {
        'filename': 'destination_logo',
        'size': DESTINATION_LOGO_SIZE,
    },
}


def _company_assets_dir():
    return Path(current_app.config.get('ASSET_UPLOADS_DIR', 'uploads/assets')) / 'company'


def _project_root():
    return Path(current_app.root_path)


def _resolve_company_asset(asset_path):
    if not asset_path:
        return None

    path = Path(asset_path)
    if path.is_absolute() and path.exists():
        return path

    candidates = [
        _project_root() / asset_path,
        _company_assets_dir() / path.name,
        _project_root() / 'uploads' / 'assets' / path.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _asset_url(asset_path):
    if not asset_path:
        return None

    asset_file = _resolve_company_asset(asset_path)
    if not asset_file:
        return None

    return url_for(
        'companies.get_company_asset',
        filename=asset_path,
        v=int(asset_file.stat().st_mtime),
    )


def company_to_dict(company):
    data = company.to_dict()
    settings = data.get('settings') or {}
    settings['company_logo_url'] = _asset_url(settings.get('company_logo_image'))
    settings['destination_logo_url'] = _asset_url(settings.get('destination_logo_image'))
    data['settings'] = settings
    return data


@company_bp.route('/', methods=['GET'])
def list_companies():
    """List active companies."""
    ensure_default_company()
    companies = Company.query.order_by(Company.name.asc()).all()
    return jsonify({
        'status': 'success',
        'data': [company_to_dict(company) for company in companies],
    }), 200


@company_bp.route('/current', methods=['GET'])
def get_current_company():
    """Return the currently selected company."""
    return jsonify({
        'status': 'success',
        'data': company_to_dict(current_company()),
    }), 200


@company_bp.route('/assets/<path:filename>', methods=['GET'])
def get_company_asset(filename):
    """Serve company branding assets from uploads with bundled fallback."""
    asset_file = _resolve_company_asset(filename)
    if not asset_file:
        return jsonify({'status': 'error', 'message': 'Company asset not found'}), 404
    return send_file(asset_file)


@company_bp.route('/', methods=['POST'])
def create_company_route():
    """Create a new company with company-level settings."""
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({
                'status': 'error',
                'message': 'Company name is required',
            }), 400

        existing = Company.query.filter(db.func.lower(Company.name) == name.lower()).first()
        if existing:
            return jsonify({
                'status': 'error',
                'message': 'Company already exists',
            }), 409

        company = create_company(name, settings_data=data.get('settings') or {})
        return jsonify({
            'status': 'success',
            'message': 'Company created successfully',
            'data': company_to_dict(company),
        }), 201

    except Exception as exc:
        db.session.rollback()
        logger.error("Error creating company: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error creating company: {exc}',
        }), 500


@company_bp.route('/<int:company_id>/settings', methods=['PUT'])
def update_company_settings(company_id):
    """Update company-level settings."""
    try:
        company = Company.query.get_or_404(company_id)
        data = request.get_json(silent=True) or {}
        settings = company.settings
        if not settings:
            settings = CompanySettings(
                company_id=company.id,
                subtitle=config.COMPANY_SUBTITLE,
                default_country=config.COMPANY_DEFAULT_COUNTRY,
                address=config.COMPANY_ADDRESS,
                website=config.COMPANY_WEBSITE,
                company_logo_image=config.COMPANY_LOGO_IMAGE,
                destination_logo_image=config.UAE_LOGO_IMAGE,
                currency=config.CURRENCY,
                rate_display_format=config.RATE_DISPLAY_FORMAT,
                import_price_deduction_percent=15.0,
                social_post_description=None,
                exchange_rate_api_url=config.EXCHANGE_RATE_API_URL,
                exchange_rate_cache_hours=config.CACHE_DURATION_HOURS,
            )
            db.session.add(settings)

        allowed_fields = {
            'subtitle',
            'default_country',
            'address',
            'website',
            'company_logo_image',
            'destination_logo_image',
            'currency',
            'rate_display_format',
            'import_price_deduction_percent',
            'social_post_description',
            'exchange_rate_api_url',
            'exchange_rate_cache_hours',
        }
        for field in allowed_fields:
            if field not in data:
                continue
            value = data[field]
            if field == 'currency' and value:
                value = str(value).strip().upper()
            elif field == 'import_price_deduction_percent':
                value = float(value)
                if value < 0 or value > 100:
                    return jsonify({
                        'status': 'error',
                        'message': 'Import price deduction percent must be between 0 and 100',
                    }), 400
            elif field == 'exchange_rate_cache_hours':
                value = int(value)
            elif isinstance(value, str):
                value = value.strip()
            setattr(settings, field, value)

        if 'name' in data:
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify({
                    'status': 'error',
                    'message': 'Company name is required',
                }), 400
            existing = Company.query.filter(
                db.func.lower(Company.name) == name.lower(),
                Company.id != company.id,
            ).first()
            if existing:
                return jsonify({
                    'status': 'error',
                    'message': 'Company already exists',
                }), 409
            company.name = name

        if 'is_active' in data:
            company.is_active = bool(data.get('is_active'))

        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Company settings updated successfully',
            'data': company_to_dict(company),
        }), 200

    except Exception as exc:
        db.session.rollback()
        logger.error("Error updating company settings %s: %s", company_id, exc)
        return jsonify({
            'status': 'error',
            'message': f'Error updating company settings: {exc}',
        }), 500


@company_bp.route('/<int:company_id>/assets/<field>', methods=['POST'])
def upload_company_asset(company_id, field):
    """Upload a company branding image and update the matching settings field."""
    try:
        if company_id != current_company_id():
            return jsonify({
                'status': 'error',
                'message': 'Company not found',
            }), 404

        if field not in ASSET_FIELDS:
            return jsonify({
                'status': 'error',
                'message': 'Unsupported company asset field',
            }), 400

        company = Company.query.get_or_404(company_id)
        settings = company.settings
        if not settings:
            settings = CompanySettings(
                company_id=company.id,
                subtitle=config.COMPANY_SUBTITLE,
                default_country=config.COMPANY_DEFAULT_COUNTRY,
                address=config.COMPANY_ADDRESS,
                website=config.COMPANY_WEBSITE,
                company_logo_image=config.COMPANY_LOGO_IMAGE,
                destination_logo_image=config.UAE_LOGO_IMAGE,
                currency=config.CURRENCY,
                rate_display_format=config.RATE_DISPLAY_FORMAT,
                import_price_deduction_percent=15.0,
                social_post_description=None,
                exchange_rate_api_url=config.EXCHANGE_RATE_API_URL,
                exchange_rate_cache_hours=config.CACHE_DURATION_HOURS,
            )
            db.session.add(settings)

        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No image file provided',
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No image selected',
            }), 400

        if not file.mimetype.startswith('image/'):
            return jsonify({
                'status': 'error',
                'message': 'Only image files are allowed',
            }), 400

        output_dir = _company_assets_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{ASSET_FIELDS[field]['filename']}_{company.id}.png"
        output_path = output_dir / filename

        with Image.open(file.stream) as uploaded_image:
            image = uploaded_image.convert('RGBA')
            image.thumbnail(ASSET_FIELDS[field]['size'], Image.Resampling.LANCZOS)
            image.save(output_path, format='PNG', optimize=True)

        setattr(settings, field, f"uploads/assets/company/{filename}")
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Company image uploaded successfully',
            'data': company_to_dict(company),
        }), 200

    except UnidentifiedImageError:
        return jsonify({
            'status': 'error',
            'message': 'The uploaded file is not a readable image',
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error uploading company asset %s for %s: %s", field, company_id, exc)
        return jsonify({
            'status': 'error',
            'message': f'Error uploading company image: {exc}',
        }), 500
