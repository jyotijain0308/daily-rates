"""
Flask application factory and initialization
"""
import os
import logging
import sys
import click
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import inspect, text

try:
    from flask_migrate import Migrate
except ImportError:
    Migrate = None

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate() if Migrate else None

logger = logging.getLogger(__name__)


def get_database_uri() -> str:
    """Return the configured database URI, defaulting to local SQLite."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return 'sqlite:///ppt_products.db'

    # Some platforms still expose SQLAlchemy's old postgres:// scheme.
    if database_url.startswith('postgres://'):
        return database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    if database_url.startswith('postgresql://'):
        return database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

    return database_url


def ensure_database_schema():
    """Rebuild old local product schemas to the current CSV-backed shape."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

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


def is_flask_migration_command() -> bool:
    """Return True when Flask-Migrate/Alembic should manage schema changes."""
    return 'db' in sys.argv


def create_app(config=None):
    """Application factory function"""
    app = Flask(__name__, 
                template_folder='app/templates',
                static_folder='app/static')
    
    # Default configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file upload
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['COUNTRY_ASSETS_DIR'] = 'src/assets/countries'
    app.config['GENERATION_AUDIO_DIR'] = 'uploads/audio'
    
    # Override with custom config if provided
    if config:
        app.config.update(config)
    
    # Initialize extensions
    db.init_app(app)
    if migrate:
        migrate.init_app(app, db)
    elif is_flask_migration_command():
        raise RuntimeError(
            "Flask-Migrate is required for migration commands. "
            "Install dependencies with: python3 -m pip install -r requirements.txt"
        )
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Create necessary directories
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
    os.makedirs(app.config.get('GENERATION_AUDIO_DIR', 'uploads/audio'), exist_ok=True)
    os.makedirs('output', exist_ok=True)
    os.makedirs('src/output', exist_ok=True)

    from output_cleanup import cleanup_previous_day_outputs
    cleanup_previous_day_outputs()
    
    # Register blueprints
    with app.app_context():
        # Import models
        from models import BackgroundAudio, Country, Product, ProductRateHistory, GenerationHistory

        # Local/test startup keeps backward compatibility. Migration commands
        # skip this so Alembic can create/upgrade tables itself.
        if not is_flask_migration_command():
            db.create_all()
            ensure_database_schema()
            from country_service import seed_default_countries
            seed_default_countries()
        logger.info("Database initialized")
        
        # Register route blueprints
        from app.routes.import_routes import import_bp
        from app.routes.product_routes import product_bp
        from app.routes.country_routes import country_bp
        from app.routes.generation_routes import generation_bp
        from app.routes.page_routes import page_bp
        app.register_blueprint(import_bp)
        app.register_blueprint(product_bp)
        app.register_blueprint(country_bp)
        app.register_blueprint(generation_bp)
        app.register_blueprint(page_bp)

    @app.cli.command('cleanup-generations')
    @click.option('--days', default=7, show_default=True, type=int, help='Delete generation artifacts older than this many days.')
    def cleanup_generations_command(days):
        """Delete old generated files, job files, and generation history rows."""
        from output_cleanup import cleanup_old_generation_artifacts

        summary = cleanup_old_generation_artifacts(days=days)
        click.echo(
            "Deleted "
            f"{summary['deleted_files']} output file(s), "
            f"{summary['deleted_history_rows']} generation history row(s), "
            f"{summary['deleted_job_files']} job file(s)."
        )
    
    @app.route('/health')
    def health():
        return {"status": "healthy", "version": "1.0"}, 200
    
    return app
