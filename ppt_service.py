"""
PPT Generation wrapper for web application
Adapts existing ppt_generator.py to work with database products
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path

# Import existing generation modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# PPT generation is intentionally disabled for now. Keep the import commented
# so it can be restored when PPT output is needed again.
# from src.ppt_generator import PPTGenerator
from src.video_generator import MP4Generator
from src.exchange_rates import ExchangeRateService
from src.product_data import ProductData
from src.product_image_service import ProductImageService
from src import config
from src.config import COUNTRY_CURRENCY_CODES
from models import Product, GenerationHistory
from wsgi import db

logger = logging.getLogger(__name__)


class GenerationCancelled(Exception):
    """Raised when an MP4 generation job is cancelled."""


class PPTGenerationService:
    """Service to generate MP4 videos from database products."""
    
    @staticmethod
    def generate_ppt(products_list=None, custom_filename=None, country_filter=None,
                     shipment_filter=None, output_format='mp4', is_cancelled=None):
        """
        Generate MP4 from products.
        
        Args:
            products_list: List of Product objects (if None, fetch all from DB)
            custom_filename: Custom output filename (default: timestamped)
        
        Returns:
            (success: bool, result: dict, error_msg: str)
        """
        try:
            is_cancelled = is_cancelled or (lambda: False)
            # Fetch products if not provided
            output_format = 'mp4'

            if products_list is None:
                query = Product.query
                if country_filter:
                    query = query.filter_by(country_of_origin=country_filter)
                if shipment_filter:
                    query = query.filter_by(shipment_by=shipment_filter)
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
            
            logger.info(
                "Starting country %s generation with %s products%s",
                output_format.upper(),
                len(products_data),
                f" for shipment {shipment_filter}" if shipment_filter else "",
            )

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
                PPTGenerationService._raise_if_cancelled(is_cancelled)
                logger.info(
                    "Generating MP4 for %s / %s with %s products",
                    country,
                    shipment_filter or country_products[0].get('shipment_by') or '-',
                    len(country_products),
                )
                PPTGenerationService._prefetch_missing_product_images(country_products, is_cancelled=is_cancelled)
                PPTGenerationService._raise_if_cancelled(is_cancelled)
                generator = MP4Generator()
                # PPT generation is disabled for now.
                # generator = PPTGenerator()
                shipment_label = shipment_filter or country_products[0].get('shipment_by')
                generator.add_country_title_slide(
                    country,
                    current_date=datetime.now(),
                    shipment_by=shipment_label,
                )

                for idx, product_data in enumerate(country_products, 1):
                    PPTGenerationService._raise_if_cancelled(is_cancelled)
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
                    slug_parts = [PPTGenerationService._slugify(country)]
                    if shipment_label:
                        slug_parts.append(PPTGenerationService._slugify(shipment_label))
                    slug = "_".join(slug_parts)
                    extension = 'mp4'
                    output_path = os.path.join('output', f'{slug}_products_price_list_{timestamp}.{extension}')

                os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
                logger.info("Writing MP4 file: %s", output_path)
                generator.save(output_path, is_cancelled=is_cancelled)
                logger.info("Finished MP4 file: %s", output_path)
                PPTGenerationService._record_generation(output_path, len(country_products), 'success')

                generated_files.append({
                    'country': country,
                    'filepath': output_path,
                    'filename': os.path.basename(output_path),
                    'product_count': len(country_products),
                    'shipment_by': shipment_label,
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
                'shipment_by': first_file.get('shipment_by'),
                'country_count': len(generated_files),
            }

            logger.info(f"✓ Generated {len(generated_files)} country {output_format.upper()} files")
            return True, result, ""
        
        except GenerationCancelled:
            raise
        except RuntimeError as e:
            if "cancelled" in str(e).lower():
                raise GenerationCancelled("MP4 generation cancelled")
            error_msg = f"PPT generation failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            PPTGenerationService._record_generation('', 0, 'failed', str(e))
            return False, {}, error_msg
        except Exception as e:
            error_msg = f"PPT generation failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            
            # Record failure in database
            PPTGenerationService._record_generation('', 0, 'failed', str(e))
            
            return False, {}, error_msg

    @staticmethod
    def _prefetch_missing_product_images(country_products, is_cancelled=None):
        """Fetch missing product images once before video rendering."""
        is_cancelled = is_cancelled or (lambda: False)
        if not getattr(config, "PRODUCT_IMAGE_PREFETCH_ON_GENERATE", True):
            logger.info("Product image prefetch is disabled")
            return

        image_service = ProductImageService()
        prefetch_limit = getattr(config, "PRODUCT_IMAGE_PREFETCH_LIMIT", 20)
        fetched_attempts = 0

        for product_data in country_products:
            PPTGenerationService._raise_if_cancelled(is_cancelled)
            product_name = product_data.get('product_name')
            country = product_data.get('country_of_origin')
            if not product_name:
                continue

            if image_service.get_product_image_path(product_name, country, fetch_if_missing=False):
                continue

            if prefetch_limit and fetched_attempts >= prefetch_limit:
                logger.info("Product image prefetch limit reached: %s", prefetch_limit)
                return

            fetched_attempts += 1
            logger.info("Prefetching missing product image: %s", product_name)
            image_service.get_product_image_path(product_name, country, fetch_if_missing=True)

    @staticmethod
    def _raise_if_cancelled(is_cancelled):
        if is_cancelled and is_cancelled():
            raise GenerationCancelled("MP4 generation cancelled")

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
            filename = os.path.basename(file_path) if file_path else f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            
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
