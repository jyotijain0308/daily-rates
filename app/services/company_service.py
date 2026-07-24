"""Company tenant and settings helpers."""
import re

from flask import has_request_context, request, session

from app.models import Company, CompanySettings
from app.services.generation import config
from wsgi import db


def slugify_company_name(name):
    """Return a stable URL-safe slug for a company name."""
    slug = re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')
    return slug or 'company'


def ensure_default_company():
    """Create the default company/settings row from legacy config values."""
    company = Company.query.order_by(Company.id.asc()).first()
    if not company:
        company = Company(
            name=config.COMPANY_NAME,
            slug=slugify_company_name(config.COMPANY_NAME),
            is_active=True,
        )
        db.session.add(company)
        db.session.flush()

    if not company.settings:
        company.settings = CompanySettings(
            subtitle=config.COMPANY_SUBTITLE,
            default_country=config.COMPANY_DEFAULT_COUNTRY,
            address=config.COMPANY_ADDRESS,
            website=config.COMPANY_WEBSITE,
            company_logo_image=config.COMPANY_LOGO_IMAGE,
            destination_logo_image=config.UAE_LOGO_IMAGE,
            currency=config.CURRENCY,
            rate_display_format=config.RATE_DISPLAY_FORMAT,
            import_price_deduction_percent=15.0,
            social_post_description=None,
            exchange_rate_api_url=config.EXCHANGE_RATE_API_URL,
            exchange_rate_cache_hours=config.CACHE_DURATION_HOURS,
        )

    db.session.commit()
    return company


def create_company(name, settings_data=None):
    """Create a company with settings initialized from defaults."""
    clean_name = (name or '').strip()
    if not clean_name:
        raise ValueError('Company name is required')

    base_slug = slugify_company_name(clean_name)
    slug = base_slug
    suffix = 2
    while Company.query.filter_by(slug=slug).first():
        slug = f'{base_slug}-{suffix}'
        suffix += 1

    company = Company(name=clean_name, slug=slug, is_active=True)
    db.session.add(company)
    db.session.flush()

    settings_data = settings_data or {}
    company.settings = CompanySettings(
        subtitle=settings_data.get('subtitle') or config.COMPANY_SUBTITLE,
        default_country=settings_data.get('default_country') or config.COMPANY_DEFAULT_COUNTRY,
        address=settings_data.get('address') or config.COMPANY_ADDRESS,
        website=settings_data.get('website') or config.COMPANY_WEBSITE,
        company_logo_image=settings_data.get('company_logo_image') or config.COMPANY_LOGO_IMAGE,
        destination_logo_image=settings_data.get('destination_logo_image') or config.UAE_LOGO_IMAGE,
        currency=(settings_data.get('currency') or config.CURRENCY).strip().upper(),
        rate_display_format=settings_data.get('rate_display_format') or config.RATE_DISPLAY_FORMAT,
        import_price_deduction_percent=float(settings_data.get('import_price_deduction_percent') or 15.0),
        social_post_description=settings_data.get('social_post_description') or None,
        exchange_rate_api_url=settings_data.get('exchange_rate_api_url') or config.EXCHANGE_RATE_API_URL,
        exchange_rate_cache_hours=int(settings_data.get('exchange_rate_cache_hours') or config.CACHE_DURATION_HOURS),
    )
    db.session.commit()
    return company


def current_company():
    """Return the active company for this request.

    Requests can select a tenant with X-Company-ID or X-Company-Slug. Requests
    without a selection keep the legacy behavior and use the first active company.
    """
    if has_request_context():
        session_company_id = session.get('company_id')
        if session_company_id:
            company = Company.query.filter_by(id=session_company_id, is_active=True).first()
            if company:
                return company

        company_id = (request.headers.get('X-Company-ID') or request.args.get('company_id') or '').strip()
        if company_id.isdigit():
            company = Company.query.filter_by(id=int(company_id), is_active=True).first()
            if company:
                return company

        company_slug = (request.headers.get('X-Company-Slug') or request.args.get('company_slug') or '').strip()
        if company_slug:
            company = Company.query.filter_by(slug=company_slug, is_active=True).first()
            if company:
                return company

    company = Company.query.filter_by(is_active=True).order_by(Company.id.asc()).first()
    return company or ensure_default_company()


def current_company_id():
    """Return the active company id."""
    return current_company().id


def current_company_settings():
    """Return active company settings, creating defaults if needed."""
    company = current_company()
    if company.settings:
        return company.settings

    company.settings = CompanySettings(
        subtitle=config.COMPANY_SUBTITLE,
        default_country=config.COMPANY_DEFAULT_COUNTRY,
        address=config.COMPANY_ADDRESS,
        website=config.COMPANY_WEBSITE,
        company_logo_image=config.COMPANY_LOGO_IMAGE,
        destination_logo_image=config.UAE_LOGO_IMAGE,
        currency=config.CURRENCY,
        rate_display_format=config.RATE_DISPLAY_FORMAT,
        import_price_deduction_percent=15.0,
        social_post_description=None,
        exchange_rate_api_url=config.EXCHANGE_RATE_API_URL,
        exchange_rate_cache_hours=config.CACHE_DURATION_HOURS,
    )
    db.session.commit()
    return company.settings


def company_settings_for(company_id):
    """Return settings for a specific company id."""
    company = Company.query.filter_by(id=company_id, is_active=True).first()
    if not company:
        return current_company_settings()

    if company.settings:
        return company.settings

    company.settings = CompanySettings(
        subtitle=config.COMPANY_SUBTITLE,
        default_country=config.COMPANY_DEFAULT_COUNTRY,
        address=config.COMPANY_ADDRESS,
        website=config.COMPANY_WEBSITE,
        company_logo_image=config.COMPANY_LOGO_IMAGE,
        destination_logo_image=config.UAE_LOGO_IMAGE,
        currency=config.CURRENCY,
        rate_display_format=config.RATE_DISPLAY_FORMAT,
        import_price_deduction_percent=15.0,
        social_post_description=None,
        exchange_rate_api_url=config.EXCHANGE_RATE_API_URL,
        exchange_rate_cache_hours=config.CACHE_DURATION_HOURS,
    )
    db.session.commit()
    return company.settings
