"""
Main Application - Orchestrate PPT generation workflow
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import PRODUCTS_DATA_FILE, OUTPUT_PPT_FILE, COUNTRY_CURRENCY_CODES
from product_data import ProductDataLoader, ProductData
from exchange_rates import ExchangeRateService
from ppt_generator import PPTGenerator
from error_handling import (
    validate_product_data, validate_exchange_rates, validate_file_path,
    ErrorHandler, DataValidationError, ExchangeRateError, FileIOError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ppt_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PPTGenerationWorkflow:
    """Orchestrate the complete PPT generation workflow"""
    
    def __init__(self, products_file: str = PRODUCTS_DATA_FILE,
                 output_file: str = OUTPUT_PPT_FILE):
        self.products_file = products_file
        self.output_file = output_file
        self.products: list[ProductData] = []
        self.exchange_rates: dict = {}
    
    def run(self):
        """Execute the complete workflow"""
        try:
            logger.info("Starting PPT generation workflow...")
            
            # Step 1: Load product data
            self.load_products()
            
            # Step 2: Fetch exchange rates
            self.fetch_exchange_rates()
            
            # Step 3: Generate PPT
            self.generate_ppt()
            
            logger.info("✓ Workflow completed successfully!")
            return True
        except Exception as e:
            logger.error(f"✗ Workflow failed: {str(e)}", exc_info=True)
            return False
    
    def load_products(self):
        """Load product data from file"""
        try:
            logger.info(f"Loading products from {self.products_file}...")
            
            if not Path(self.products_file).exists():
                logger.warning(f"Products file not found, creating sample data...")
                ProductDataLoader.create_sample_data(self.products_file)
            
            self.products = ProductDataLoader.load_products(self.products_file)
            validate_product_data(self.products)
            logger.info(f"✓ Loaded {len(self.products)} products")
        except Exception as e:
            if not ErrorHandler.handle_workflow_error(e, "during product loading"):
                raise
    
    def fetch_exchange_rates(self):
        """Fetch current exchange rates"""
        try:
            logger.info("Fetching exchange rates...")
            service = ExchangeRateService()
            target_currencies = sorted({
                COUNTRY_CURRENCY_CODES[product.country_of_origin]
                for product in self.products
                if product.country_of_origin in COUNTRY_CURRENCY_CODES
            })
            self.exchange_rates = service.get_exchange_rates(
                base_currency="AED",
                target_currencies=target_currencies,
            ) if target_currencies else {}
            if self.exchange_rates:
                validate_exchange_rates(self.exchange_rates)
                logger.info(f"✓ Fetched exchange rates: {self.exchange_rates}")
            else:
                logger.warning("No exchange rates available")
        except ExchangeRateError as e:
            logger.warning(f"Exchange rate error (non-critical): {str(e)}")
            self.exchange_rates = {}
        except Exception as e:
            logger.warning(f"Could not fetch exchange rates: {str(e)}")
            self.exchange_rates = {}
    
    def generate_ppt(self):
        """Generate PowerPoint presentation"""
        try:
            if not self.products:
                raise DataValidationError("No products available to generate PPT")
            
            logger.info("Generating country PowerPoint presentations...")

            products_by_country = {}
            for product in self.products:
                products_by_country.setdefault(product.country_of_origin, []).append(product)

            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for country, products in sorted(products_by_country.items()):
                generator = PPTGenerator()
                generator.add_country_title_slide(country, current_date=datetime.now())

                for idx, product in enumerate(products, 1):
                    generator.add_product_slide(product, slide_number=idx)

                currency_code = COUNTRY_CURRENCY_CODES.get(country)
                generator.add_thank_you_slide(
                    country_name=country,
                    exchange_rate=self.exchange_rates.get(currency_code) if currency_code else None,
                    currency_code=currency_code,
                )

                slug = country.lower().replace(" ", "_")
                country_output = output_path.parent / f"{slug}_products_price_list_{timestamp}.pptx"
                validate_file_path(str(country_output), should_exist=False)
                generator.save(str(country_output))
                logger.info(f"✓ PPT generated for {country} with {len(products)} product slides")
        except Exception as e:
            if not ErrorHandler.handle_workflow_error(e, "during PPT generation"):
                raise


def main():
    """Entry point"""
    workflow = PPTGenerationWorkflow()
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
