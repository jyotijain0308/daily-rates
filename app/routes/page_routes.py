"""
Web UI page routes
"""
from flask import Blueprint, render_template

page_bp = Blueprint('pages', __name__)


@page_bp.route('/')
def dashboard():
    return render_template('dashboard.html', active_page='dashboard')


@page_bp.route('/import')
def import_page():
    return render_template('import.html', active_page='import')


@page_bp.route('/products')
def products_page():
    return render_template('products.html', active_page='products')


@page_bp.route('/generate')
def generate_page():
    return render_template('generate.html', active_page='generate')
