"""
Web UI page routes
"""
from flask import Blueprint, abort, render_template

page_bp = Blueprint('pages', __name__)


@page_bp.route('/')
def dashboard():
    return render_template('dashboard.html', active_page='dashboard')


@page_bp.route('/import')
def import_page():
    return render_template('import.html', active_page='import')


# PDF import is intentionally disabled.
# @page_bp.route('/import-pdf')
# def import_pdf_page():
#     return render_template('import_pdf.html', active_page='import_pdf')
@page_bp.route('/import-pdf')
def import_pdf_page_disabled():
    abort(404)



@page_bp.route('/products')
def products_page():
    return render_template('products.html', active_page='products')


@page_bp.route('/countries')
def countries_page():
    return render_template('countries.html', active_page='countries')


@page_bp.route('/company')
def company_page():
    return render_template('company.html', active_page='company')


@page_bp.route('/generate')
def generate_page():
    return render_template('generate.html', active_page='generate')
