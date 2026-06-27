"""
Flask application factory and initialization
"""
import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import inspect, text

# Initialize extensions
db = SQLAlchemy()

logger = logging.getLogger(__name__)


def ensure_database_schema():
    """Rebuild old local product schemas to the current CSV-backed shape."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    if 'product_rate_history' in table_names:
        db.session.execute(text("DROP TABLE product_rate_history"))
        db.session.commit()
        logger.info("Dropped obsolete product_rate_history table")

    if 'products' in table_names:
        product_columns = {column['name'] for column in inspector.get_columns('products')}
        if 'product_name' not in product_columns:
            db.session.execute(text("ALTER TABLE products RENAME TO products_legacy"))
            db.session.commit()
            db.create_all()

            legacy_columns = {
                column['name'] for column in inspect(db.engine).get_columns('products_legacy')
            }
            if {'name', 'current_rate'}.issubset(legacy_columns):
                country_expr = "COALESCE(country, 'India')" if 'country' in legacy_columns else "'India'"
                packing_expr = "COALESCE(unit, 'unit')" if 'unit' in legacy_columns else "'unit'"
                db.session.execute(text(f"""
                    INSERT OR REPLACE INTO products (
                        serial_no,
                        country_of_origin,
                        shipment_by,
                        product_name,
                        weight_kg,
                        packing,
                        price_aed,
                        created_at,
                        updated_at
                    )
                    SELECT
                        id,
                        {country_expr},
                        '-',
                        name,
                        0,
                        {packing_expr},
                        current_rate,
                        created_at,
                        updated_at
                    FROM products_legacy
                    WHERE name IS NOT NULL AND current_rate IS NOT NULL
                """))

            db.session.execute(text("DROP TABLE products_legacy"))
            db.session.commit()
            logger.info("Rebuilt products table for shipment product schema")


def create_app(config=None):
    """Application factory function"""
    app = Flask(__name__, 
                template_folder='app/templates',
                static_folder='app/static')
    
    # Default configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ppt_products.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file upload
    app.config['UPLOAD_FOLDER'] = 'uploads'
    
    # Override with custom config if provided
    if config:
        app.config.update(config)
    
    # Initialize extensions
    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Create necessary directories
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # Register blueprints
    with app.app_context():
        # Import models
        from models import Product, GenerationHistory

        # Create tables
        db.create_all()
        ensure_database_schema()
        logger.info("Database initialized")
        
        # Register route blueprints
        from app.routes.import_routes import import_bp
        from app.routes.product_routes import product_bp
        from app.routes.generation_routes import generation_bp
        from app.routes.page_routes import page_bp
        app.register_blueprint(import_bp)
        app.register_blueprint(product_bp)
        app.register_blueprint(generation_bp)
        app.register_blueprint(page_bp)
    
    @app.route('/health')
    def health():
        return {"status": "healthy", "version": "1.0"}, 200
    
    return app
