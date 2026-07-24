"""Country metadata helpers."""
import re
from pathlib import Path

from app.services.company_service import current_company_id, slugify_company_name
from app.models import Company, Country
from app.services.storage_service import resolve_asset_file
from wsgi import db


COMMON_COUNTRY_CURRENCY_CODES = {
    "Afghanistan": "AFN",
    "Australia": "AUD",
    "Bangladesh": "BDT",
    "Brazil": "BRL",
    "Canada": "CAD",
    "China": "CNY",
    "Ecuador": "USD",
    "Egypt": "EGP",
    "India": "INR",
    "Indonesia": "IDR",
    "Iran": "IRR",
    "Malaysia": "MYR",
    "New Zealand": "NZD",
    "Pakistan": "PKR",
    "Sri Lanka": "LKR",
    "Srilanka": "LKR",
    "Thailand": "THB",
    "Turkey": "TRY",
    "Ukraine": "UAH",
    "United Arab Emirates": "AED",
    "United States": "USD",
    "Vietnam": "VND",
}

COUNTRY_IMAGE_EXTENSIONS = ("jpg", "jpeg", "png")


def _asset_slug(value):
    """Return the underscore slug used for generated asset filenames."""
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


def _country_assets_dir(assets_dir=None):
    if assets_dir:
        return Path(assets_dir)
    return Path(__file__).resolve().parents[2] / "uploads" / "assets" / "countries"


def _default_country_assets_dir():
    return _country_assets_dir() / "default"


def _company_folder_names(company):
    if not company:
        return []

    names = [
        getattr(company, "slug", None),
        slugify_company_name(getattr(company, "name", "")),
        _asset_slug(getattr(company, "name", "")),
    ]
    folders = []
    for name in names:
        if name and name not in folders:
            folders.append(name)
    return folders


def _resolve_relative_country_asset(relative_path, assets_dir=None):
    """Resolve an assets/countries relative path to a filesystem path."""
    if not relative_path:
        return None

    path = Path(relative_path)
    base_dir = _country_assets_dir(assets_dir)
    default_dir = _default_country_assets_dir()
    extra_dirs = [base_dir, default_dir]
    if len(path.parts) >= 3 and path.parts[0] == "assets" and path.parts[1] == "countries":
        extra_dirs.extend([
            base_dir.joinpath(*path.parts[2:-1]),
            default_dir.joinpath(*path.parts[2:-1]),
        ])
    if len(path.parts) >= 4 and path.parts[0] == "uploads" and path.parts[1] == "assets" and path.parts[2] == "countries":
        extra_dirs.append(base_dir.joinpath(*path.parts[3:-1]))

    return resolve_asset_file(relative_path, extra_dirs=extra_dirs)


def company_country_logo_path(company, country_name, assets_dir=None):
    """Find a company-specific country logo by country filename."""
    country_slug = _asset_slug(country_name)
    if not country_slug:
        return None

    base_dir = _country_assets_dir(assets_dir)
    for folder in _company_folder_names(company):
        for extension in COUNTRY_IMAGE_EXTENSIONS:
            relative_path = f"uploads/assets/countries/{folder}/{country_slug}.{extension}"
            if (base_dir / folder / f"{country_slug}.{extension}").exists():
                return relative_path
    return None


def default_country_logo_path(country_name, assets_dir=None):
    """Find a shared country logo by country filename."""
    country_slug = _asset_slug(country_name)
    if not country_slug:
        return None

    base_dir = _default_country_assets_dir()
    for extension in COUNTRY_IMAGE_EXTENSIONS:
        relative_path = f"uploads/assets/countries/default/{country_slug}.{extension}"
        if (base_dir / f"{country_slug}.{extension}").exists():
            return relative_path
    return None


def resolve_country_logo_image(country, assets_dir=None):
    """Resolve the best country logo path for the country and its company."""
    company = db.session.get(Company, country.company_id) if country and country.company_id else None
    company_logo = company_country_logo_path(company, country.name, assets_dir=assets_dir)
    if company_logo:
        return company_logo

    if country.logo_image and _resolve_relative_country_asset(country.logo_image, assets_dir=assets_dir):
        return country.logo_image

    return default_country_logo_path(country.name, assets_dir=assets_dir)


def resolve_country_logo_asset(country, assets_dir=None):
    """Return the resolved country logo relative path and filesystem path."""
    logo_image = resolve_country_logo_image(country, assets_dir=assets_dir)
    if not logo_image:
        return None, None
    return logo_image, _resolve_relative_country_asset(logo_image, assets_dir=assets_dir)


def infer_currency_code(country_name):
    """Infer a currency code for known product-origin countries."""
    clean_name = (country_name or "").strip()
    return COMMON_COUNTRY_CURRENCY_CODES.get(clean_name)


def seed_default_countries(company_id=None):
    """Backfill known metadata for countries that already exist in the database."""
    company_id = company_id or current_company_id()
    for country in Country.query.filter_by(company_id=company_id).all():
        if not country.currency_code:
            country.currency_code = infer_currency_code(country.name)
    db.session.commit()


def ensure_country(name, currency_code=None, logo_image=None, company_id=None):
    """Create a country if it does not already exist."""
    clean_name = (name or "").strip()
    if not clean_name:
        return None

    company_id = company_id or current_company_id()
    country = Country.query.filter(
        Country.company_id == company_id,
        db.func.lower(Country.name) == clean_name.lower(),
    ).first()
    if country:
        return country

    country = Country(
        company_id=company_id,
        name=clean_name,
        currency_code=(currency_code or infer_currency_code(clean_name) or "").strip().upper() or None,
        logo_image=(logo_image or "").strip() or None,
        is_active=True,
    )
    db.session.add(country)
    return country


def active_country_names(company_id=None):
    """Return active country names for dropdowns."""
    company_id = company_id or current_company_id()
    return [
        country.name
        for country in Country.query.filter_by(company_id=company_id, is_active=True).order_by(Country.name.asc()).all()
    ]


def country_currency_map(company_id=None):
    """Return country to currency-code mapping from managed countries."""
    company_id = company_id or current_company_id()
    return {
        country.name: country.currency_code
        for country in Country.query.filter_by(company_id=company_id).all()
        if country.currency_code
    }


def country_logo_map(company_id=None):
    """Return active country to logo-path mapping."""
    company_id = company_id or current_company_id()
    return {
        country.name: logo_image
        for country in Country.query.filter_by(company_id=company_id, is_active=True).all()
        for logo_image in [resolve_country_logo_image(country)]
        if logo_image
    }
