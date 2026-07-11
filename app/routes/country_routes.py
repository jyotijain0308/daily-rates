"""Country management API routes."""
import logging
import re
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory, url_for
from PIL import Image, UnidentifiedImageError

from country_service import ensure_country
from models import Country, Product
from wsgi import db

logger = logging.getLogger(__name__)
country_bp = Blueprint('countries', __name__, url_prefix='/api/countries')
COUNTRY_FLAG_SIZE = (300, 200)
COUNTRY_FLAG_JPEG_QUALITY = 86


def _country_by_id(country_id):
    return Country.query.get_or_404(country_id)


def _country_assets_dir():
    return Path(current_app.config.get('COUNTRY_ASSETS_DIR', 'src/assets/countries'))


def _slugify(value):
    return re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')


def country_to_dict(country):
    """Serialize a country with a browser-loadable logo URL."""
    data = country.to_dict()
    if country.logo_image:
        image_file = _country_assets_dir() / Path(country.logo_image).name
        if image_file.exists():
            url_args = {
                'filename': Path(country.logo_image).name,
                'v': int(image_file.stat().st_mtime),
            }
            data['logo_url'] = url_for('countries.get_country_logo', **url_args)
        else:
            data['logo_url'] = None
    else:
        data['logo_url'] = None
    return data


@country_bp.route('/image/<path:filename>', methods=['GET'])
def get_country_logo(filename):
    """Serve country logo images from the country asset directory."""
    return send_from_directory(_country_assets_dir(), Path(filename).name)


@country_bp.route('/', methods=['GET'])
def list_countries():
    """List all managed countries."""
    countries = Country.query.order_by(Country.name.asc()).all()
    return jsonify({
        'status': 'success',
        'data': [country_to_dict(country) for country in countries],
    }), 200


@country_bp.route('/', methods=['POST'])
def create_country():
    """Create a managed country."""
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({
                'status': 'error',
                'message': 'Country name is required'
            }), 400

        existing = Country.query.filter(db.func.lower(Country.name) == name.lower()).first()
        if existing:
            return jsonify({
                'status': 'error',
                'message': 'Country already exists'
            }), 409

        country = ensure_country(
            name,
            currency_code=data.get('currency_code'),
            logo_image=data.get('logo_image'),
        )
        country.is_active = bool(data.get('is_active', True))
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Country created successfully',
            'data': country_to_dict(country),
        }), 201

    except Exception as exc:
        db.session.rollback()
        logger.error("Error creating country: %s", exc)
        return jsonify({
            'status': 'error',
            'message': f'Error creating country: {exc}'
        }), 500


@country_bp.route('/<int:country_id>', methods=['PUT'])
def update_country(country_id):
    """Update country metadata."""
    try:
        country = _country_by_id(country_id)
        data = request.get_json(silent=True) or {}

        if 'name' in data:
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify({
                    'status': 'error',
                    'message': 'Country name is required'
                }), 400

            existing = Country.query.filter(
                db.func.lower(Country.name) == name.lower(),
                Country.id != country.id,
            ).first()
            if existing:
                return jsonify({
                    'status': 'error',
                    'message': 'Country already exists'
                }), 409

            old_name = country.name
            country.name = name
            Product.query.filter_by(country_of_origin=old_name).update(
                {'country_of_origin': name},
                synchronize_session=False,
            )

        if 'currency_code' in data:
            country.currency_code = (data.get('currency_code') or '').strip().upper() or None
        if 'logo_image' in data:
            country.logo_image = (data.get('logo_image') or '').strip() or None
        if 'is_active' in data:
            country.is_active = bool(data.get('is_active'))

        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Country updated successfully',
            'data': country_to_dict(country),
        }), 200

    except Exception as exc:
        db.session.rollback()
        logger.error("Error updating country %s: %s", country_id, exc)
        return jsonify({
            'status': 'error',
            'message': f'Error updating country: {exc}'
        }), 500


@country_bp.route('/<int:country_id>/flag', methods=['POST'])
def upload_country_flag(country_id):
    """Upload and store a country flag image."""
    try:
        country = _country_by_id(country_id)

        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No flag image file provided'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No flag image selected'
            }), 400

        if not file.mimetype.startswith('image/'):
            return jsonify({
                'status': 'error',
                'message': 'Only image files are allowed'
            }), 400

        slug = _slugify(country.name)
        if not slug:
            return jsonify({
                'status': 'error',
                'message': 'Country name is required before uploading a flag'
            }), 400

        output_dir = _country_assets_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'{slug}.jpg'

        with Image.open(file.stream) as uploaded_image:
            source = uploaded_image.convert('RGB')
            source.thumbnail(COUNTRY_FLAG_SIZE, Image.Resampling.LANCZOS)

            image = Image.new('RGB', COUNTRY_FLAG_SIZE, 'white')
            x = int((COUNTRY_FLAG_SIZE[0] - source.width) / 2)
            y = int((COUNTRY_FLAG_SIZE[1] - source.height) / 2)
            image.paste(source, (x, y))
            image.save(
                output_path,
                format='JPEG',
                quality=COUNTRY_FLAG_JPEG_QUALITY,
                optimize=True,
            )

        country.logo_image = f'assets/countries/{slug}.jpg'
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Country flag uploaded successfully',
            'data': country_to_dict(country),
        }), 200

    except UnidentifiedImageError:
        return jsonify({
            'status': 'error',
            'message': 'The uploaded file is not a readable image'
        }), 400
    except Exception as exc:
        db.session.rollback()
        logger.error("Error uploading country flag %s: %s", country_id, exc)
        return jsonify({
            'status': 'error',
            'message': f'Error uploading country flag: {exc}'
        }), 500


@country_bp.route('/<int:country_id>', methods=['DELETE'])
def delete_country(country_id):
    """Delete an unused country."""
    try:
        country = _country_by_id(country_id)
        product_count = Product.query.filter_by(country_of_origin=country.name).count()
        if product_count:
            return jsonify({
                'status': 'error',
                'message': 'Country is used by products. Deactivate it instead of deleting.'
            }), 400

        db.session.delete(country)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Country deleted successfully',
        }), 200

    except Exception as exc:
        db.session.rollback()
        logger.error("Error deleting country %s: %s", country_id, exc)
        return jsonify({
            'status': 'error',
            'message': f'Error deleting country: {exc}'
        }), 500
