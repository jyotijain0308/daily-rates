"""Passenger entry point for cPanel Python application hosting."""
from wsgi import create_app


application = create_app()
