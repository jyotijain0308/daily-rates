"""
Database initialization and management utilities
"""
import logging
from wsgi import create_app, db
from models import Product, GenerationHistory

logger = logging.getLogger(__name__)


def init_db():
    """Initialize database and create tables"""
    app = create_app()
    with app.app_context():
        db.create_all()
        logger.info("✓ Database tables created/verified")
        
        # Log table information
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        logger.info(f"✓ Tables in database: {tables}")
        
        for table_name in tables:
            columns = inspector.get_columns(table_name)
            logger.info(f"  Table '{table_name}' columns:")
            for col in columns:
                logger.info(f"    - {col['name']}: {col['type']}")


def drop_all():
    """Drop all tables (use with caution!)"""
    app = create_app()
    with app.app_context():
        db.drop_all()
        logger.warning("✓ All database tables dropped")


def seed_sample_data():
    """Seed database with sample products"""
    app = create_app()
    with app.app_context():
        # Check if products already exist
        existing_products = Product.query.count()
        if existing_products > 0:
            logger.info(f"Database already has {existing_products} products, skipping seed")
            return
        
        sample_products = [
            Product(serial_no=1, country_of_origin="India", shipment_by="Air", product_name="Wheat Flour", weight_kg=25, packing="Bag", price_aed=72.50),
            Product(serial_no=2, country_of_origin="Thailand", shipment_by="Sea", product_name="Jasmine Rice", weight_kg=50, packing="Sack", price_aed=158.00),
            Product(serial_no=3, country_of_origin="Brazil", shipment_by="Sea", product_name="Soybean Meal", weight_kg=40, packing="Bag", price_aed=121.25),
            Product(serial_no=4, country_of_origin="United States", shipment_by="Air", product_name="Almonds", weight_kg=10, packing="Carton", price_aed=96.00),
            Product(serial_no=5, country_of_origin="Australia", shipment_by="Sea", product_name="Chickpeas", weight_kg=25, packing="Bag", price_aed=88.75),
            Product(serial_no=6, country_of_origin="Vietnam", shipment_by="Sea", product_name="Black Pepper", weight_kg=5, packing="Carton", price_aed=64.50),
        ]
        
        db.session.add_all(sample_products)
        db.session.commit()
        logger.info(f"✓ Seeded {len(sample_products)} sample products")


if __name__ == '__main__':
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'init':
            init_db()
        elif command == 'drop':
            drop_all()
        elif command == 'seed':
            init_db()
            seed_sample_data()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python db.py [init|drop|seed]")
    else:
        init_db()
