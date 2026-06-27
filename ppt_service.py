"""
PPT Generation wrapper for web application
Adapts existing ppt_generator.py to work with database products
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path

# Import existing PPT generation modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ppt_generator import PPTGenerator
from src.video_generator import MP4Generator
from src.exchange_rates import ExchangeRateService
from src.product_data import ProductData
from src.config import COUNTRY_CURRENCY_CODES
from models import Product, GenerationHistory
from wsgi import db

logger = logging.getLogger(__name__)


class PPTGenerationService:
    """Service to generate PPT from database products"""
    
    @staticmethod
    def generate_ppt(products_list=None, custom_filename=None, country_filter=None, output_format='ppt'):
        """
        Generate PPT from products
        
        Args:
            products_list: List of Product objects (if None, fetch all from DB)
            custom_filename: Custom output filename (default: timestamped)
        
        Returns:
            (success: bool, result: dict, error_msg: str)
        """
        try:
            # Fetch products if not provided
            output_format = (output_format or 'ppt').lower()
            if output_format not in {'ppt', 'mp4'}:
                return False, {}, "Unsupported output format. Use 'ppt' or 'mp4'."

            if products_list is None:
                query = Product.query
                if country_filter:
                    query = query.filter_by(country_of_origin=country_filter)
                products_list = query.all()
            
            if not products_list:
                return False, {}, "No products available for the selected country"
            
            # Convert Product objects to compatible format
            products_data = []
            for product in products_list:
                products_data.append({
                    'serial_no': product.serial_no,
                    'country_of_origin': product.country_of_origin,
                    'shipment_by': product.shipment_by,
                    'product_name': product.product_name,
                    'weight_kg': product.weight_kg,
                    'packing': product.packing,
                    'price_aed': product.price_aed,
                })
            
            logger.info(f"Starting country {output_format.upper()} generation with {len(products_data)} products")

            products_by_country = {}
            for product_data in products_data:
                products_by_country.setdefault(product_data['country_of_origin'], []).append(product_data)

            target_currencies = sorted({
                COUNTRY_CURRENCY_CODES[country]
                for country in products_by_country
                if country in COUNTRY_CURRENCY_CODES
            })
            exchange_rates = PPTGenerationService._get_aed_exchange_rates(target_currencies)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            generated_files = []

            for country, country_products in sorted(products_by_country.items()):
                generator = MP4Generator() if output_format == 'mp4' else PPTGenerator()
                generator.add_country_title_slide(country, current_date=datetime.now())

                for idx, product_data in enumerate(country_products, 1):
                    product_obj = ProductData(
                        serial_no=product_data['serial_no'],
                        country_of_origin=product_data['country_of_origin'],
                        shipment_by=product_data['shipment_by'],
                        product_name=product_data['product_name'],
                        weight_kg=product_data['weight_kg'],
                        packing=product_data['packing'],
                        price_aed=product_data['price_aed'],
                    )
                    generator.add_product_slide(product_obj, slide_number=idx)

                currency_code = COUNTRY_CURRENCY_CODES.get(country)
                generator.add_thank_you_slide(
                    country_name=country,
                    exchange_rate=exchange_rates.get(currency_code) if currency_code else None,
                    currency_code=currency_code,
                )

                if custom_filename and len(products_by_country) == 1:
                    output_path = os.path.join('output', custom_filename)
                else:
                    slug = PPTGenerationService._slugify(country)
                    extension = 'mp4' if output_format == 'mp4' else 'pptx'
                    output_path = os.path.join('output', f'{slug}_products_price_list_{timestamp}.{extension}')

                os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
                generator.save(output_path)
                PPTGenerationService._record_generation(output_path, len(country_products), 'success')

                generated_files.append({
                    'country': country,
                    'filepath': output_path,
                    'filename': os.path.basename(output_path),
                    'product_count': len(country_products),
                    'currency_code': currency_code,
                    'exchange_rate': exchange_rates.get(currency_code) if currency_code else None,
                    'format': output_format,
                })

            first_file = generated_files[0]
            result = {
                'files': generated_files,
                'filepath': first_file['filepath'],
                'filename': first_file['filename'],
                'product_count': len(products_data),
                'country_count': len(generated_files),
            }

            logger.info(f"✓ Generated {len(generated_files)} country {output_format.upper()} files")
            return True, result, ""
        
        except Exception as e:
            error_msg = f"PPT generation failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            
            # Record failure in database
            PPTGenerationService._record_generation('', 0, 'failed', str(e))
            
            return False, {}, error_msg

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')
        return slug or 'country'

    @staticmethod
    def _get_aed_exchange_rates(target_currencies):
        if not target_currencies:
            return {}

        try:
            service = ExchangeRateService()
            rates = service.get_exchange_rates(base_currency='AED', target_currencies=target_currencies)
            logger.info(f"✓ Fetched AED exchange rates: {rates}")
            return rates
        except Exception as e:
            logger.warning(f"Could not fetch AED exchange rates (non-critical): {str(e)}")
            return {}
    
    @staticmethod
    def _record_generation(file_path, product_count, status, error_msg=None):
        """Record PPT generation in database"""
        try:
            filename = os.path.basename(file_path) if file_path else f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            
            generation = GenerationHistory(
                filename=filename,
                product_count=product_count,
                file_path=file_path,
                status=status,
                error_message=error_msg
            )
            
            db.session.add(generation)
            db.session.commit()
            logger.info(f"✓ Generation record saved: {filename}")
        except Exception as e:
            logger.warning(f"Could not save generation record: {str(e)}")
            db.session.rollback()
    
    @staticmethod
    def get_latest_ppt():
        """Get the latest generated PPT file info"""
        try:
            generation = GenerationHistory.query.filter_by(status='success').order_by(
                GenerationHistory.generated_at.desc()
            ).first()
            
            if generation:
                return {
                    'filename': generation.filename,
                    'filepath': generation.file_path,
                    'generated_at': generation.generated_at.isoformat(),
                    'product_count': generation.product_count
                }
            return None
        except Exception as e:
            logger.error(f"Error getting latest PPT: {str(e)}")
            return None
    
    @staticmethod
    def get_generation_history(limit=10):
        """Get generation history"""
        try:
            generations = GenerationHistory.query.order_by(
                GenerationHistory.generated_at.desc()
            ).limit(limit).all()
            
            return [gen.to_dict() for gen in generations]
        except Exception as e:
            logger.error(f"Error getting generation history: {str(e)}")
            return []
