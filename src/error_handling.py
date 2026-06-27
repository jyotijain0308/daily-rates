"""
Error Handling and Validation Module
"""
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class PPTGenerationError(Exception):
    """Base exception for PPT generation errors"""
    pass


class DataValidationError(PPTGenerationError):
    """Raised when product data validation fails"""
    pass


class ExchangeRateError(PPTGenerationError):
    """Raised when exchange rate fetching fails"""
    pass


class FileIOError(PPTGenerationError):
    """Raised when file operations fail"""
    pass


def validate_product_data(products: list) -> bool:
    """
    Validate product data structure and values
    
    Args:
        products: List of ProductData objects
        
    Returns:
        True if valid, raises exception otherwise
    """
    if not products:
        raise DataValidationError("No products provided")
    
    for idx, product in enumerate(products):
        if not product.product_name or not product.product_name.strip():
            raise DataValidationError(f"Product {idx}: product_name is required")
        
        if not product.country_of_origin or not product.country_of_origin.strip():
            raise DataValidationError(f"Product {idx}: country_of_origin is required")

        if not product.shipment_by or not product.shipment_by.strip():
            raise DataValidationError(f"Product {idx}: shipment_by is required")
        
        if product.weight_kg is None or product.weight_kg <= 0:
            raise DataValidationError(
                f"Product '{product.product_name}': weight_kg must be a positive number"
            )
        
        if product.price_aed is None or product.price_aed <= 0:
            raise DataValidationError(
                f"Product '{product.product_name}': price_aed must be a positive number"
            )
    
    logger.info(f"✓ Validated {len(products)} products")
    return True


def validate_file_path(file_path: str, should_exist: bool = False) -> Path:
    """
    Validate file path
    
    Args:
        file_path: Path to file
        should_exist: If True, file must exist; if False, parent directory must exist
        
    Returns:
        Path object if valid
    """
    path = Path(file_path)
    
    if should_exist:
        if not path.exists():
            raise FileIOError(f"File not found: {file_path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    
    return path


def validate_exchange_rates(rates: dict) -> bool:
    """Validate exchange rates data"""
    if not rates:
        logger.warning("No exchange rates available")
        return False
    
    for currency, rate in rates.items():
        if not isinstance(currency, str) or not isinstance(rate, (int, float)):
            raise ExchangeRateError(
                f"Invalid exchange rate format: {currency}={rate}"
            )
        if rate <= 0:
            raise ExchangeRateError(
                f"Exchange rate must be positive: {currency}={rate}"
            )
    
    logger.info(f"✓ Validated {len(rates)} exchange rates")
    return True


def handle_missing_file(file_path: str, create_default: callable = None,
                        error_message: str = None) -> Optional[str]:
    """
    Handle missing file gracefully
    
    Args:
        file_path: Path to file
        create_default: Callable to create default/sample data
        error_message: Custom error message
        
    Returns:
        file_path if resolved, None if cannot proceed
    """
    if Path(file_path).exists():
        return file_path
    
    if create_default:
        try:
            logger.warning(f"File not found: {file_path}. Creating sample data...")
            create_default(file_path)
            return file_path
        except Exception as e:
            logger.error(f"Failed to create sample data: {str(e)}")
            return None
    
    msg = error_message or f"Required file not found: {file_path}"
    raise FileIOError(msg)


class ErrorHandler:
    """Centralized error handling"""
    
    @staticmethod
    def handle_workflow_error(error: Exception, context: str = "") -> bool:
        """
        Handle workflow-level errors
        
        Returns:
            False to indicate failure
        """
        if isinstance(error, DataValidationError):
            logger.error(f"Data validation failed: {str(error)}")
        elif isinstance(error, ExchangeRateError):
            logger.warning(f"Exchange rate error (non-critical): {str(error)}")
            return True  # Continue without rates
        elif isinstance(error, FileIOError):
            logger.error(f"File I/O error: {str(error)}")
        else:
            logger.error(f"Unexpected error {context}: {str(error)}")
        
        return False
    
    @staticmethod
    def safe_operation(operation: callable, *args, fallback_value=None, **kwargs):
        """
        Execute operation with error handling
        
        Args:
            operation: Callable to execute
            *args, **kwargs: Arguments to pass
            fallback_value: Value to return if operation fails
            
        Returns:
            Operation result or fallback_value
        """
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Operation failed: {str(e)}. Using fallback value.")
            return fallback_value
