"""
Flask application factory and initialization
"""
import os
import logging
import sys
import click
from datetime import timedelta
from flask import Flask, jsonify, redirect, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import inspect, text
from urllib.parse import urlparse

try:
    from flask_migrate import Migrate
except ImportError:
    Migrate = None

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate() if Migrate else None

logger = logging.getLogger(__name__)


class PrefixMiddleware:
    """Support hosting the Flask app under a URL prefix such as /taaza-rates."""

    def __init__(self, app, prefix):
        self.app = app
        self.prefix = (prefix or '').rstrip('/')

    def __call__(self, environ, start_response):
        if self.prefix:
            path_info = environ.get('PATH_INFO', '')
            environ['SCRIPT_NAME'] = self.prefix
            if path_info == self.prefix:
                environ['PATH_INFO'] = '/'
            elif path_info.startswith(f'{self.prefix}/'):
                environ['PATH_INFO'] = path_info[len(self.prefix):] or '/'
        return self.app(environ, start_response)


def running_in_docker() -> bool:
    """Return True when the app is running inside a Docker container."""
    return os.path.exists('/.dockerenv')


def load_local_env() -> None:
    """Load project .env values for direct local Python commands."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

    if not running_in_docker() and os.getenv('HOST_DATABASE_URL'):
        os.environ['DATABASE_URL'] = os.getenv('HOST_DATABASE_URL')


def get_database_uri() -> str:
    """Return the configured SQLAlchemy database URI."""
    load_local_env()
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Start a reachable PostgreSQL or MySQL "
            "server and set DATABASE_URL before running the app or Python "
            "commands."
        )

    # Some platforms still expose SQLAlchemy's old postgres:// scheme.
    if database_url.startswith('postgres://'):
        return database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    if database_url.startswith('postgresql://'):
        return database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    if database_url.startswith('mysql://'):
        return database_url.replace('mysql://', 'mysql+pymysql://', 1)

    return database_url


def get_app_base_path() -> str:
    """Return the optional URL path where the app is mounted."""
    explicit_path = (os.getenv('APP_BASE_PATH') or '').strip()
    if explicit_path:
        return '/' + explicit_path.strip('/')

    app_url = (os.getenv('APP_URL') or '').strip()
    if app_url:
        return urlparse(app_url).path.rstrip('/')

    return ''


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


def ensure_company_tenancy_columns():
    """Backfill company_id columns for local databases not upgraded by Alembic."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    for table_name in ['products', 'countries', 'generation_history', 'background_audio']:
        if table_name not in table_names:
            continue

        columns = {column['name'] for column in inspector.get_columns(table_name)}
        if 'company_id' not in columns:
            db.session.execute(text(
                f"ALTER TABLE {table_name} "
                "ADD COLUMN company_id INTEGER NOT NULL DEFAULT 1"
            ))
            db.session.commit()
            logger.info("Added company_id column to %s", table_name)


def is_flask_migration_command() -> bool:
    """Return True when Flask-Migrate/Alembic should manage schema changes."""
    return 'db' in sys.argv


def create_app(config=None):
    """Application factory function"""
    app = Flask(__name__, 
                template_folder='app/templates',
                static_folder='app/static')
    
    # Default configuration
    configured_database_uri = (
        config.get('SQLALCHEMY_DATABASE_URI')
        if config and 'SQLALCHEMY_DATABASE_URI' in config
        else get_database_uri()
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = configured_database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file upload
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['ASSET_UPLOADS_DIR'] = 'uploads/assets'
    app.config['COUNTRY_ASSETS_DIR'] = 'uploads/assets/countries'
    app.config['GENERATION_AUDIO_DIR'] = 'uploads/audio'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.getenv('FLASK_SECRET_KEY') or 'dev-change-me'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=14)
    app.config['APP_BASE_PATH'] = get_app_base_path()
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, app.config['APP_BASE_PATH'])
    
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
    os.makedirs(app.config.get('ASSET_UPLOADS_DIR', 'uploads/assets'), exist_ok=True)
    os.makedirs(app.config.get('COUNTRY_ASSETS_DIR', 'uploads/assets/countries'), exist_ok=True)
    os.makedirs(app.config.get('GENERATION_AUDIO_DIR', 'uploads/audio'), exist_ok=True)
    from app.services.storage_service import ensure_storage_dirs
    ensure_storage_dirs()

    from app.services.generation.cleanup_service import cleanup_previous_day_outputs
    cleanup_previous_day_outputs()
    
    # Register blueprints
    with app.app_context():
        # Import models
        from app.models import (
            BackgroundAudio,
            Company,
            CompanySettings,
            Country,
            GenerationHistory,
            Product,
            ProductRateHistory,
            SocialConnection,
            SocialPublishHistory,
            SystemConfiguration,
            User,
        )

        # Local/test startup keeps backward compatibility. Migration commands
        # skip this so Alembic can create/upgrade tables itself.
        if not is_flask_migration_command():
            db.create_all()
            ensure_database_schema()
            from app.services.company_service import ensure_default_company
            ensure_default_company()
            ensure_company_tenancy_columns()
            from app.services.country_service import seed_default_countries
            seed_default_countries()
        logger.info("Database initialized")
        
        # Register route blueprints
        from app.routes.import_routes import import_bp
        from app.routes.company_routes import company_bp
        from app.routes.product_routes import product_bp
        from app.routes.country_routes import country_bp
        from app.routes.generation_routes import generation_bp
        from app.routes.social_routes import social_bp
        from app.routes.system_routes import system_bp
        from app.routes.auth_routes import auth_bp
        from app.routes.page_routes import page_bp
        app.register_blueprint(auth_bp)
        app.register_blueprint(system_bp)
        app.register_blueprint(company_bp)
        app.register_blueprint(import_bp)
        app.register_blueprint(product_bp)
        app.register_blueprint(country_bp)
        app.register_blueprint(generation_bp)
        app.register_blueprint(social_bp)
        app.register_blueprint(page_bp)

    @app.context_processor
    def inject_auth_context():
        from app.services.auth_service import current_user
        return {'current_user': current_user()}

    @app.before_request
    def require_authenticated_user():
        if app.config.get('TESTING') and not app.config.get('AUTH_REQUIRED_IN_TESTS', False):
            return None

        if _is_public_request():
            return None

        from app.services.auth_service import current_user
        if current_user():
            return None

        if request.path.startswith('/api/'):
            return jsonify({'status': 'error', 'message': 'Authentication required'}), 401

        return redirect(url_for('auth.signin', next=request.full_path if request.query_string else request.path))

    @app.cli.command('cleanup-generations')
    @click.option('--days', default=7, show_default=True, type=int, help='Delete generation artifacts older than this many days.')
    def cleanup_generations_command(days):
        """Delete old generated files, job files, and generation history rows."""
        from app.services.generation.cleanup_service import cleanup_old_generation_artifacts

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


def _is_public_request():
    endpoint = request.endpoint or ''
    if endpoint == 'static' or endpoint == 'health':
        return True
    if endpoint.startswith('auth.'):
        return True
    if endpoint in {
        'social.youtube_callback',
        'social.facebook_callback',
        'social.linkedin_callback',
        'social.tiktok_callback',
        'social.x_callback',
    }:
        return True
    if endpoint == 'generation.preview_mp4':
        return True
    return False
