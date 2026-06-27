"""
Product Data Loader - Load and validate product rates from CSV/JSON
"""
import csv
import json
import logging
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ProductData:
    """Data class for product information"""
    
    def __init__(self, serial_no: int, country_of_origin: str, shipment_by: str,
                 product_name: str, weight_kg: float, packing: str, price_aed: float):
        self.serial_no = serial_no
        self.country_of_origin = country_of_origin
        self.shipment_by = shipment_by
        self.product_name = product_name
        self.weight_kg = weight_kg
        self.packing = packing
        self.price_aed = price_aed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial_no": self.serial_no,
            "country_of_origin": self.country_of_origin,
            "shipment_by": self.shipment_by,
            "product_name": self.product_name,
            "weight_kg": self.weight_kg,
            "packing": self.packing,
            "price_aed": self.price_aed,
        }


class ProductDataLoader:
    """Load product data from CSV or JSON files"""
    
    @staticmethod
    def load_from_csv(file_path: str) -> List[ProductData]:
        """
        Load products from CSV file
        Expected columns: S.No., Country of origin, Shipment by, Product Name, Weight in kg, Packing, Price in AED
        """
        try:
            products = []
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    product = ProductData(
                        serial_no=int(row['S.No.']),
                        country_of_origin=row['Country of origin'].strip(),
                        shipment_by=row['Shipment by'].strip(),
                        product_name=row['Product Name'].strip(),
                        weight_kg=float(row['Weight in kg']),
                        packing=row['Packing'].strip(),
                        price_aed=float(row['Price in AED']),
                    )
                    products.append(product)
            
            logger.info(f"Loaded {len(products)} products from {file_path}")
            return products
        except FileNotFoundError:
            logger.error(f"Product file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading products from CSV: {str(e)}")
            raise
    
    @staticmethod
    def load_from_json(file_path: str) -> List[ProductData]:
        """
        Load products from JSON file
        Expected structure: [{"product_name": "...", "country_of_origin": "...", ...}]
        """
        try:
            products = []
            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                for item in data:
                    product = ProductData(
                        serial_no=int(item.get('serial_no', 0)),
                        country_of_origin=item['country_of_origin'],
                        shipment_by=item['shipment_by'],
                        product_name=item['product_name'],
                        weight_kg=float(item['weight_kg']),
                        packing=item['packing'],
                        price_aed=float(item['price_aed']),
                    )
                    products.append(product)
            
            logger.info(f"Loaded {len(products)} products from {file_path}")
            return products
        except FileNotFoundError:
            logger.error(f"Product file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading products from JSON: {str(e)}")
            raise
    
    @staticmethod
    def load_products(file_path: str) -> List[ProductData]:
        """
        Auto-detect file format and load products accordingly
        """
        path = Path(file_path)
        
        if path.suffix.lower() == '.csv':
            return ProductDataLoader.load_from_csv(file_path)
        elif path.suffix.lower() == '.json':
            return ProductDataLoader.load_from_json(file_path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
    
    @staticmethod
    def create_sample_data(output_file: str = "data/products.csv"):
        """Create sample product data for testing"""
        sample_data = [
            ['S.No.', 'Country of origin', 'Shipment by', 'Product Name', 'Weight in kg', 'Packing', 'Price in AED'],
            [1, 'India', 'Air', 'Wheat Flour', 25, 'Bag', 72.50],
            [2, 'Thailand', 'Sea', 'Jasmine Rice', 50, 'Sack', 158.00],
            [3, 'Brazil', 'Sea', 'Soybean Meal', 40, 'Bag', 121.25],
            [4, 'United States', 'Air', 'Almonds', 10, 'Carton', 96.00],
            [5, 'Australia', 'Sea', 'Chickpeas', 25, 'Bag', 88.75],
            [6, 'Vietnam', 'Sea', 'Black Pepper', 5, 'Carton', 64.50],
        ]
        
        try:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(sample_data)
            logger.info(f"Created sample product data at {output_file}")
        except Exception as e:
            logger.error(f"Error creating sample data: {str(e)}")
            raise
