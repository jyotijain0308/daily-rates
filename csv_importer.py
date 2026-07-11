"""
CSV import utilities for products
"""
import csv
import logging
from io import StringIO, TextIOWrapper
from typing import List, Dict, Tuple
from country_service import ensure_country
from models import Product, ProductRateHistory
from wsgi import db

logger = logging.getLogger(__name__)


class CSVImportError(Exception):
    """Custom exception for CSV import errors"""
    pass


class ProductCSVImporter:
    """Handle CSV import for products"""
    LARGE_RATE_CHANGE_PERCENT = 20.0
    
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
    def _row_key(row: Dict) -> Tuple[str, str]:
        return (
            row['product_name'].strip().lower(),
            row['country_of_origin'].strip().lower(),
        )

    @staticmethod
    def _rate_diff(old_price, new_price) -> Dict:
        if old_price is None:
            return {
                'change_amount': None,
                'change_percent': None,
                'large_change': False,
            }

        change_amount = new_price - old_price
        if old_price == 0:
            change_percent = None
            large_change = new_price != 0
        else:
            change_percent = (change_amount / old_price) * 100
            large_change = abs(change_percent) >= ProductCSVImporter.LARGE_RATE_CHANGE_PERCENT

        return {
            'change_amount': change_amount,
            'change_percent': change_percent,
            'large_change': large_change,
        }

    @staticmethod
    def build_import_plan(rows: List[Dict]) -> Dict:
        """Build create/update/skip decisions for valid CSV rows."""
        products = Product.query.all()
        existing_by_key = {
            (product.product_name.strip().lower(), product.country_of_origin.strip().lower()): product
            for product in products
        }

        plan_rows = []
        summary = {
            'created_count': 0,
            'updated_count': 0,
            'skipped_count': 0,
            'large_change_count': 0,
        }

        seen_keys = set()
        duplicate_count = 0

        for row in rows:
            key = ProductCSVImporter._row_key(row)
            if key in seen_keys:
                duplicate_count += 1
                plan_rows.append({
                    **row,
                    'action': 'skipped',
                    'reason': 'Duplicate row in uploaded file',
                    'old_price_aed': None,
                    'new_price_aed': float(row['price_aed']),
                    'change_amount': None,
                    'change_percent': None,
                    'large_change': False,
                })
                summary['skipped_count'] += 1
                continue
            seen_keys.add(key)

            product = existing_by_key.get(key)
            new_price = float(row['price_aed'])

            if not product:
                diff = ProductCSVImporter._rate_diff(None, new_price)
                plan_rows.append({
                    **row,
                    'action': 'created',
                    'reason': 'New product',
                    'old_price_aed': None,
                    'new_price_aed': new_price,
                    **diff,
                })
                summary['created_count'] += 1
                continue

            old_price = float(product.price_aed)
            next_values = {
                'serial_no': int(row['serial_no']),
                'shipment_by': row['shipment_by'].strip(),
                'weight_kg': float(row['weight_kg']),
                'packing': row['packing'].strip(),
                'price_aed': new_price,
            }
            current_values = {
                'serial_no': product.serial_no,
                'shipment_by': product.shipment_by,
                'weight_kg': float(product.weight_kg),
                'packing': product.packing,
                'price_aed': old_price,
            }
            has_changes = any(current_values[field] != next_values[field] for field in next_values)
            diff = ProductCSVImporter._rate_diff(old_price, new_price)

            if has_changes:
                action = 'updated'
                reason = 'Existing product will be updated'
                summary['updated_count'] += 1
                if diff['large_change']:
                    summary['large_change_count'] += 1
            else:
                action = 'skipped'
                reason = 'No changes'
                summary['skipped_count'] += 1

            plan_rows.append({
                **row,
                'action': action,
                'reason': reason,
                'old_price_aed': old_price,
                'new_price_aed': new_price,
                **diff,
            })

        if duplicate_count:
            logger.info(f"Skipped {duplicate_count} duplicate row(s) in import plan")

        return {
            **summary,
            'rows': plan_rows,
        }
    
    @staticmethod
    def import_products(rows: List[Dict], changed_by: str = 'import') -> Tuple[Dict, List[str]]:
        """
        Insert new products and update existing products by Product Name + Country of origin.
        Returns: (summary, error_messages)
        """
        summary = {
            'created_count': 0,
            'updated_count': 0,
            'skipped_count': 0,
            'rate_history_count': 0,
            'large_change_count': 0,
            'imported_count': 0,
        }
        errors = []
        
        if not rows:
            return summary, ["No valid products to import"]
        
        try:
            plan = ProductCSVImporter.build_import_plan(rows)
            summary['large_change_count'] = plan['large_change_count']

            for plan_row in plan['rows']:
                if plan_row['action'] == 'skipped':
                    summary['skipped_count'] += 1
                    continue

                try:
                    product_name = plan_row['product_name'].strip()
                    country_of_origin = plan_row['country_of_origin'].strip()
                    ensure_country(country_of_origin)
                    new_price = float(plan_row['price_aed'])
                    product = Product.query.filter_by(
                        product_name=product_name,
                        country_of_origin=country_of_origin,
                    ).first()

                    if product:
                        old_price = float(product.price_aed)
                        product.serial_no = int(plan_row['serial_no'])
                        product.shipment_by = plan_row['shipment_by'].strip()
                        product.weight_kg = float(plan_row['weight_kg'])
                        product.packing = plan_row['packing'].strip()
                        product.price_aed = new_price
                        summary['updated_count'] += 1
                    else:
                        old_price = None
                        product = Product(
                            serial_no=int(plan_row['serial_no']),
                            country_of_origin=country_of_origin,
                            shipment_by=plan_row['shipment_by'].strip(),
                            product_name=product_name,
                            weight_kg=float(plan_row['weight_kg']),
                            packing=plan_row['packing'].strip(),
                            price_aed=new_price,
                        )
                        db.session.add(product)
                        summary['created_count'] += 1

                    if old_price != new_price:
                        db.session.add(ProductRateHistory(
                            product=product,
                            old_price_aed=old_price,
                            new_price_aed=new_price,
                            changed_by=changed_by,
                        ))
                        summary['rate_history_count'] += 1

                    summary['imported_count'] += 1
                except Exception as e:
                    errors.append(
                        f"Error importing {plan_row.get('product_name', 'unknown product')}: {str(e)}"
                    )

            if summary['imported_count']:
                db.session.commit()
                logger.info(f"✓ Imported {summary['imported_count']} products from CSV")
        
        except Exception as e:
            db.session.rollback()
            errors.append(f"Database error during import: {str(e)}")
            logger.error(f"✗ Import failed: {str(e)}")
        
        return summary, errors
    
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
        import_summary, import_errors = ProductCSVImporter.import_products(valid_rows)
        errors.extend(import_errors)
        
        # Generate preview data (first 5 valid rows)
        preview_data = valid_rows[:5]
        
        return import_summary['imported_count'], errors, preview_data


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


def products_to_csv(products: List[Product]) -> str:
    """Serialize products to the same CSV contract accepted by import."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(ProductCSVImporter.CSV_COLUMNS)

    for index, product in enumerate(products, start=1):
        writer.writerow([
            product.serial_no if product.serial_no is not None else index,
            product.country_of_origin,
            product.shipment_by,
            product.product_name,
            product.weight_kg,
            product.packing,
            product.price_aed,
        ])

    return output.getvalue()


SAMPLE_CSV_FILENAME = "sample_daily_product_rates.csv"
