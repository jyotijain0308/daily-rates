"""Passenger entry point for cPanel Python application hosting."""
import os
import sys

from wsgi import create_app


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

application = create_app()
