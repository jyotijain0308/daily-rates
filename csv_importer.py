"""
CSV import utilities for products
"""
import csv
import logging
from io import StringIO, TextIOWrapper
from typing import List, Dict, Tuple
from models import Product
from wsgi import db

logger = logging.getLogger(__name__)


class CSVImportError(Exception):
    """Custom exception for CSV import errors"""
    pass


class ProductCSVImporter:
    """Handle CSV import for products"""
    
    CSV_COLUMNS = [
        'S.No.',
        'Country of origin',
        'Shipment by',
        'Product Name',
        'Weight in kg',
        'Packing',
        'Price in AED',
    ]
    REQUIRED_COLUMNS = CSV_COLUMNS

    @staticmethod
    def normalize_row(row: Dict) -> Dict:
        """Normalize CSV headers to stable internal field names."""
        cleaned = {(key or '').strip().lstrip('\ufeff'): value for key, value in row.items()}
        return {
            'serial_no': cleaned.get('S.No.', ''),
            'country_of_origin': cleaned.get('Country of origin', ''),
            'shipment_by': cleaned.get('Shipment by', ''),
            'product_name': cleaned.get('Product Name', ''),
            'weight_kg': cleaned.get('Weight in kg', ''),
            'packing': cleaned.get('Packing', ''),
            'price_aed': cleaned.get('Price in AED', ''),
        }
    
    @staticmethod
    def validate_row(row: Dict, row_number: int) -> Tuple[bool, str]:
        """
        Validate a single row from CSV
        Returns: (is_valid, error_message)
        """
        for field, label in [
            ('serial_no', 'S.No.'),
            ('country_of_origin', 'Country of origin'),
            ('shipment_by', 'Shipment by'),
            ('product_name', 'Product Name'),
            ('weight_kg', 'Weight in kg'),
            ('packing', 'Packing'),
            ('price_aed', 'Price in AED'),
        ]:
            if field not in row or row[field] in (None, ''):
                return False, f"Row {row_number}: Missing required column '{label}'"
        
        if not row['product_name'].strip():
            return False, f"Row {row_number}: 'Product Name' cannot be empty"
        
        if len(row['product_name']) > 255:
            return False, f"Row {row_number}: 'Product Name' exceeds 255 characters"
        
        if len(row['country_of_origin']) > 100:
            return False, f"Row {row_number}: 'Country of origin' exceeds 100 characters"

        if len(row['shipment_by']) > 100:
            return False, f"Row {row_number}: 'Shipment by' exceeds 100 characters"

        try:
            int(row['serial_no'])
        except (ValueError, TypeError):
            return False, f"Row {row_number}: 'S.No.' must be a whole number, got '{row['serial_no']}'"

        try:
            float(row['weight_kg'])
        except (ValueError, TypeError):
            return False, f"Row {row_number}: 'Weight in kg' must be a valid number, got '{row['weight_kg']}'"

        try:
            float(row['price_aed'])
        except (ValueError, TypeError):
            return False, f"Row {row_number}: 'Price in AED' must be a valid number, got '{row['price_aed']}'"
        
        return True, ""
    
    @staticmethod
    def parse_csv_content(file_content: str) -> Tuple[List[Dict], List[str]]:
        """
        Parse CSV content and return rows with validation errors
        Returns: (valid_rows, error_messages)
        """
        errors = []
        valid_rows = []
        
        try:
            # Parse CSV
            reader = csv.DictReader(StringIO(file_content))
            
            if not reader.fieldnames:
                errors.append("CSV file is empty or has no headers")
                return [], errors
            
            normalized_fieldnames = [
                (fieldname or '').strip().lstrip('\ufeff') for fieldname in reader.fieldnames
            ]
            missing_cols = [col for col in ProductCSVImporter.REQUIRED_COLUMNS 
                          if col not in normalized_fieldnames]
            if missing_cols:
                errors.append(f"Missing required columns: {', '.join(missing_cols)}")
                return [], errors
            
            # Process rows
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                normalized_row = ProductCSVImporter.normalize_row(row)
                is_valid, error_msg = ProductCSVImporter.validate_row(normalized_row, row_num)
                
                if is_valid:
                    valid_rows.append(normalized_row)
                else:
                    errors.append(error_msg)
        
        except Exception as e:
            errors.append(f"Error parsing CSV: {str(e)}")
        
        return valid_rows, errors
    
    @staticmethod
    def import_products(rows: List[Dict]) -> Tuple[int, List[str]]:
        """
        Insert new products and update existing products by Product Name + Country of origin.
        Returns: (count_imported, error_messages)
        """
        imported_count = 0
        errors = []
        
        if not rows:
            return 0, ["No valid products to import"]
        
        try:
            for row in rows:
                try:
                    product_name = row['product_name'].strip()
                    country_of_origin = row['country_of_origin'].strip()
                    product = Product.query.filter_by(
                        product_name=product_name,
                        country_of_origin=country_of_origin,
                    ).first()

                    if product:
                        product.serial_no = int(row['serial_no'])
                        product.shipment_by = row['shipment_by'].strip()
                        product.weight_kg = float(row['weight_kg'])
                        product.packing = row['packing'].strip()
                        product.price_aed = float(row['price_aed'])
                    else:
                        product = Product(
                            serial_no=int(row['serial_no']),
                            country_of_origin=country_of_origin,
                            shipment_by=row['shipment_by'].strip(),
                            product_name=product_name,
                            weight_kg=float(row['weight_kg']),
                            packing=row['packing'].strip(),
                            price_aed=float(row['price_aed']),
                        )
                        db.session.add(product)

                    imported_count += 1
                except Exception as e:
                    errors.append(
                        f"Error importing {row.get('product_name', 'unknown product')}: {str(e)}"
                    )

            if imported_count:
                db.session.commit()
                logger.info(f"✓ Imported {imported_count} products from CSV")
        
        except Exception as e:
            db.session.rollback()
            errors.append(f"Database error during import: {str(e)}")
            logger.error(f"✗ Import failed: {str(e)}")
        
        return imported_count, errors
    
    @staticmethod
    def import_from_file(file_path: str) -> Tuple[int, List[str], List[Dict]]:
        """
        Complete import workflow: parse → validate → insert
        Returns: (count_imported, error_messages, preview_data)
        """
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return 0, [f"Error reading file: {str(e)}"], []
        
        # Parse and validate
        valid_rows, parse_errors = ProductCSVImporter.parse_csv_content(content)
        errors.extend(parse_errors)
        
        # Import valid rows
        imported_count, import_errors = ProductCSVImporter.import_products(valid_rows)
        errors.extend(import_errors)
        
        # Generate preview data (first 5 valid rows)
        preview_data = valid_rows[:5]
        
        return imported_count, errors, preview_data


def get_csv_template() -> str:
    """Generate blank CSV template with header row only."""
    return ",".join(ProductCSVImporter.CSV_COLUMNS) + "\n"


def get_sample_csv() -> str:
    """Generate sample CSV with daily product rates ready for upload."""
    header = get_csv_template()
    rows = [
        "1,India,Air,Wheat Flour,25,Bag,72.50",
        "2,Thailand,Sea,Jasmine Rice,50,Sack,158.00",
        "3,Brazil,Sea,Soybean Meal,40,Bag,121.25",
        "4,United States,Air,Almonds,10,Carton,96.00",
        "5,Australia,Sea,Chickpeas,25,Bag,88.75",
        "6,Vietnam,Sea,Black Pepper,5,Carton,64.50",
    ]
    return header + "\n".join(rows) + "\n"


SAMPLE_CSV_FILENAME = "sample_daily_product_rates.csv"
