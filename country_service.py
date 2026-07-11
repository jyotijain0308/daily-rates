"""Country metadata helpers."""
from models import Country
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


def infer_currency_code(country_name):
    """Infer a currency code for known product-origin countries."""
    clean_name = (country_name or "").strip()
    return COMMON_COUNTRY_CURRENCY_CODES.get(clean_name)


def seed_default_countries():
    """Backfill known metadata for countries that already exist in the database."""
    for country in Country.query.all():
        if not country.currency_code:
            country.currency_code = infer_currency_code(country.name)
    db.session.commit()


def ensure_country(name, currency_code=None, logo_image=None):
    """Create a country if it does not already exist."""
    clean_name = (name or "").strip()
    if not clean_name:
        return None

    country = Country.query.filter(db.func.lower(Country.name) == clean_name.lower()).first()
    if country:
        return country

    country = Country(
        name=clean_name,
        currency_code=(currency_code or infer_currency_code(clean_name) or "").strip().upper() or None,
        logo_image=(logo_image or "").strip() or None,
        is_active=True,
    )
    db.session.add(country)
    return country


def active_country_names():
    """Return active country names for dropdowns."""
    return [
        country.name
        for country in Country.query.filter_by(is_active=True).order_by(Country.name.asc()).all()
    ]


def country_currency_map():
    """Return country to currency-code mapping from managed countries."""
    return {
        country.name: country.currency_code
        for country in Country.query.all()
        if country.currency_code
    }


def country_logo_map():
    """Return active country to logo-path mapping."""
    return {
        country.name: country.logo_image
        for country in Country.query.filter_by(is_active=True).all()
        if country.logo_image
    }
