"""
PPT Generation wrapper for web application
Adapts existing ppt_generator.py to work with database products
"""
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path

# PPT generation is intentionally disabled for now. Keep the import commented
# so it can be restored when PPT output is needed again.
# from app.services.generation.ppt_generator import PPTGenerator
from app.services.generation.video_generator import MP4Generator
from app.services.generation.exchange_rates import ExchangeRateService
from app.services.generation.product_data import ProductData
from app.services.generation.product_image_service import ProductImageService
from app.services.generation import config
from app.services.company_service import company_settings_for, current_company_id
from app.services.country_service import country_currency_map, country_logo_map
from app.services.storage_service import generated_output_path
from app.models import Product, GenerationHistory
from wsgi import db

logger = logging.getLogger(__name__)


class GenerationCancelled(Exception):
    """Raised when an MP4 generation job is cancelled."""


class PPTGenerationService:
    """Service to generate MP4 videos from database products."""
    
    @staticmethod
    def generate_ppt(products_list=None, custom_filename=None, country_filter=None,
                     shipment_filter=None, output_format='mp4', background_audio_path=None,
                     is_cancelled=None, company_id=None, generation_date=None,
                     content_fingerprint=None):
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
                company_id = company_id or current_company_id()
                query = Product.query.filter_by(company_id=company_id)
                if country_filter:
                    query = query.filter_by(country_of_origin=country_filter)
                if shipment_filter:
                    query = query.filter_by(shipment_by=shipment_filter)
                products_list = query.all()
            elif products_list:
                company_id = products_list[0].company_id
            else:
                company_id = company_id or current_company_id()
            
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

            company_settings = company_settings_for(company_id)
            currency_codes = country_currency_map(company_id=company_id)
            country_logos = country_logo_map(company_id=company_id)

            target_currencies = sorted({
                currency_codes[country]
                for country in products_by_country
                if country in currency_codes
            })
            if company_settings.currency == 'AED':
                exchange_rates = PPTGenerationService._get_aed_exchange_rates(target_currencies)
            else:
                exchange_rates = PPTGenerationService._get_exchange_rates(
                    company_settings.currency,
                    target_currencies,
                )

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
                generator = MP4Generator(
                    country_logo_images=country_logos,
                    company_settings=company_settings,
                )
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

                currency_code = currency_codes.get(country)
                generator.add_thank_you_slide(
                    country_name=country,
                    exchange_rate=exchange_rates.get(currency_code) if currency_code else None,
                    currency_code=currency_code,
                )

                if custom_filename and len(products_by_country) == 1:
                    output_path = str(generated_output_path(custom_filename))
                else:
                    slug_parts = [PPTGenerationService._slugify(country)]
                    if shipment_label:
                        slug_parts.append(PPTGenerationService._slugify(shipment_label))
                    slug = "_".join(slug_parts)
                    extension = 'mp4'
                    output_path = str(generated_output_path(f'{slug}_products_price_list_{timestamp}.{extension}'))

                os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
                logger.info("Writing MP4 file: %s", output_path)
                generator.save(
                    output_path,
                    is_cancelled=is_cancelled,
                    audio_path=background_audio_path,
                )
                logger.info("Finished MP4 file: %s", output_path)
                PPTGenerationService._record_generation(
                    output_path,
                    len(country_products),
                    'success',
                    company_id=company_id,
                    generation_date=generation_date,
                    content_fingerprint=content_fingerprint,
                )

                generated_files.append({
                    'country': country,
                    'filepath': output_path,
                    'filename': os.path.basename(output_path),
                    'product_count': len(country_products),
                    'shipment_by': shipment_label,
                    'currency_code': currency_code,
                    'exchange_rate': exchange_rates.get(currency_code) if currency_code else None,
                    'format': output_format,
                    'has_audio': bool(background_audio_path),
                })

            first_file = generated_files[0]
            result = {
                'files': generated_files,
                'filepath': first_file['filepath'],
                'filename': first_file['filename'],
                'product_count': len(products_data),
                'shipment_by': first_file.get('shipment_by'),
                'country_count': len(generated_files),
                'has_audio': first_file.get('has_audio', False),
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
            PPTGenerationService._record_generation('', 0, 'failed', str(e), company_id=company_id or current_company_id())
            return False, {}, error_msg
        except Exception as e:
            error_msg = f"PPT generation failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            
            # Record failure in database
            PPTGenerationService._record_generation('', 0, 'failed', str(e), company_id=company_id or current_company_id())
            
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
    def _get_exchange_rates(base_currency, target_currencies):
        if not target_currencies:
            return {}

        try:
            service = ExchangeRateService()
            rates = service.get_exchange_rates(base_currency=base_currency, target_currencies=target_currencies)
            logger.info(f"✓ Fetched {base_currency} exchange rates: {rates}")
            return rates
        except Exception as e:
            logger.warning(f"Could not fetch {base_currency} exchange rates (non-critical): {str(e)}")
            return {}

    @staticmethod
    def _get_aed_exchange_rates(target_currencies):
        """Backward-compatible wrapper for existing tests/callers."""
        return PPTGenerationService._get_exchange_rates('AED', target_currencies)
    
    @staticmethod
    def _record_generation(
        file_path,
        product_count,
        status,
        error_msg=None,
        company_id=None,
        generation_date=None,
        content_fingerprint=None,
    ):
        """Record PPT generation in database"""
        try:
            company_id = company_id or current_company_id()
            filename = os.path.basename(file_path) if file_path else f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            
            generation = GenerationHistory(
                company_id=company_id,
                filename=filename,
                product_count=product_count,
                generation_date=PPTGenerationService._parse_generation_date(generation_date),
                content_fingerprint=content_fingerprint,
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
    def _parse_generation_date(value):
        if not value:
            return date.today()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return date.today()
    
    @staticmethod
    def get_latest_ppt():
        """Get the latest generated PPT file info"""
        try:
            generation = GenerationHistory.query.filter_by(
                company_id=current_company_id(),
                status='success',
            ).order_by(
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
            generations = GenerationHistory.query.filter_by(
                company_id=current_company_id(),
            ).order_by(
                GenerationHistory.generated_at.desc()
            ).limit(limit).all()
            
            return [gen.to_dict() for gen in generations]
        except Exception as e:
            logger.error(f"Error getting generation history: {str(e)}")
            return []
