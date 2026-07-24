"""Session authentication helpers."""
from datetime import datetime

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from app.services.company_service import slugify_company_name
from app.models import Company, User
from wsgi import db


def normalize_email(email):
    return (email or '').strip().lower()


def find_company_for_signup(identifier):
    value = (identifier or '').strip()
    if not value:
        return None

    if value.isdigit():
        company = Company.query.filter_by(id=int(value), is_active=True).first()
        if company:
            return company

    company = Company.query.filter_by(slug=value.lower(), is_active=True).first()
    if company:
        return company

    slug = slugify_company_name(value)
    company = Company.query.filter_by(slug=slug, is_active=True).first()
    if company:
        return company

    return Company.query.filter_by(name=value, is_active=True).first()


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.filter_by(id=user_id, is_active=True).first()


def current_user_company_id():
    user = current_user()
    return user.company_id if user else None


def signup_user(full_name, email, password, company_identifier):
    clean_name = (full_name or '').strip()
    clean_email = normalize_email(email)
    if not clean_name:
        raise ValueError('Full name is required.')
    if not clean_email:
        raise ValueError('Email is required.')
    if not password or len(password) < 8:
        raise ValueError('Password must be at least 8 characters.')

    company = find_company_for_signup(company_identifier)
    if not company:
        raise ValueError('Company was not found. Use the company ID, slug, or exact registered company name.')

    if User.query.filter_by(email=clean_email).first():
        raise ValueError('An account already exists for this email.')

    existing_company_users = User.query.filter_by(company_id=company.id).count()
    user = User(
        company_id=company.id,
        email=clean_email,
        full_name=clean_name,
        password_hash=generate_password_hash(password),
        role='admin' if existing_company_users == 0 else 'member',
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(email, password):
    clean_email = normalize_email(email)
    user = User.query.filter_by(email=clean_email, is_active=True).first()
    if not user or not check_password_hash(user.password_hash, password or ''):
        return None
    if not user.company or not user.company.is_active:
        return None

    user.last_login_at = datetime.utcnow()
    db.session.commit()
    return user


def sign_in_user(user):
    session.clear()
    session['user_id'] = user.id
    session['company_id'] = user.company_id
    session.permanent = True


def sign_out_user():
    session.clear()
