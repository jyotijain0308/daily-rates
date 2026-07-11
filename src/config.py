"""
Configuration module for PPT Daily Rates System
"""
import os

from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

# Company Settings
COMPANY_NAME = "Eastern Farms LLC"
COMPANY_SUBTITLE = "Daily Product Rates"
COMPANY_DEFAULT_COUNTRY = "United Arab Emirates"
COMPANY_ADDRESS = "Office #1835, One by Omniyat, Business Bay, Dubai, United Arab Emirates"
COMPANY_WEBSITE = "https://www.easternfarmsllc.com"
COMPANY_LOGO_IMAGE = "assets/company_logo.png"
UAE_LOGO_IMAGE = "assets/uae_logo.jpg"
PRODUCT_IMAGES_DIR = "assets/products"

# Product image search API Configuration
PEXELS_API_KEY = os.getenv(
    "PEXELS_API_KEY",
    "URdYNWJH4VRSWwMsCZ7HTHzwhG9bJOQNPGZnDjSVEtxGl5c8OTqKdSOv",
)
PEXELS_API_URL = "https://api.pexels.com/v1/search"
PRODUCT_IMAGE_PROVIDER = "pexels"
PRODUCT_IMAGE_AUTO_FETCH = os.getenv("PRODUCT_IMAGE_AUTO_FETCH", "true").lower() == "true"
PRODUCT_IMAGE_FETCH_TIMEOUT_SECONDS = int(os.getenv("PRODUCT_IMAGE_FETCH_TIMEOUT_SECONDS", "5"))
PRODUCT_IMAGE_PREFETCH_ON_GENERATE = os.getenv("PRODUCT_IMAGE_PREFETCH_ON_GENERATE", "true").lower() == "true"
PRODUCT_IMAGE_PREFETCH_LIMIT = int(os.getenv("PRODUCT_IMAGE_PREFETCH_LIMIT", "20"))
PRODUCT_IMAGE_SEARCH_CATEGORY = "fruits, vegetables or spices"
PRODUCT_IMAGE_MAX_WIDTH = 1200
PRODUCT_IMAGE_MAX_HEIGHT = 800
PRODUCT_IMAGE_JPEG_QUALITY = 85

# Presentation Settings
SLIDE_WIDTH = Inches(10)
SLIDE_HEIGHT = Inches(7.5)
PRESENTATION_TITLE = "Daily Product Rates Report"

# Color Scheme
COLORS = {
    "primary": RGBColor(0, 51, 102),      # Dark Blue
    "accent": RGBColor(255, 102, 0),      # Orange
    "background": RGBColor(255, 255, 255), # White
    "text": RGBColor(50, 50, 50),         # Dark Gray
    "light_text": RGBColor(255, 255, 255), # White
}

# Typography
FONTS = {
    "title": "Arial",
    "subtitle": "Arial",
    "body": "Calibri",
}

FONT_SIZES = {
    "title": Pt(54),
    "subtitle": Pt(32),
    "heading": Pt(28),
    "body": Pt(18),
    "small": Pt(14),
}

# Slide Margins
MARGINS = {
    "left": Inches(0.5),
    "right": Inches(0.5),
    "top": Inches(0.5),
    "bottom": Inches(0.5),
}

# Exchange Rate API Configuration
EXCHANGE_RATE_API_URL = "https://api.exchangerate-api.com/v4/latest"
CACHE_DURATION_HOURS = 24  # Cache exchange rates for 24 hours

# Data file paths
PRODUCTS_DATA_FILE = "data/products.csv"
OUTPUT_PPT_FILE = "output/daily_rates.pptx"
OUTPUT_CLEANUP_ENABLED = True
OUTPUT_CLEANUP_DIRS = ["output", "src/output"]
OUTPUT_CLEANUP_EXTENSIONS = [".pptx", ".mp4"]

# Image table import settings
IMAGE_IMPORT_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "tiff"}
OCR_TESSERACT_CONFIG = "--psm 6"
PDF_TABLE_EXTRACTION_PROVIDER = os.getenv("PDF_TABLE_EXTRACTION_PROVIDER", "ollama").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_PDF_EXTRACTION_MODEL = os.getenv("OPENAI_PDF_EXTRACTION_MODEL", "gpt-4o-mini")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_PDF_EXTRACTION_MODEL = os.getenv("OLLAMA_PDF_EXTRACTION_MODEL", "llama3.2-vision")

# Product Rate Format
CURRENCY = "AED"
RATE_DISPLAY_FORMAT = "AED {:.2f}"

# Supported countries for country-specific product rates
COUNTRIES = [
    "India",
    "United States",
    "Brazil",
    "Thailand",
    "Vietnam",
    "Australia",
    "Canada",
    "China",
]

COUNTRY_CURRENCY_CODES = {
    "India": "INR",
    "United States": "USD",
    "Brazil": "BRL",
    "Thailand": "THB",
    "Vietnam": "VND",
    "Australia": "AUD",
    "Canada": "CAD",
    "China": "CNY",
}

COUNTRY_LOGO_IMAGES = {
    "India": "assets/countries/india.jpg",
    "United States": "assets/countries/united_states.jpg",
    "Brazil": "assets/countries/brazil.jpg",
    "Thailand": "assets/countries/thailand.jpg",
    "Vietnam": "assets/countries/vietnam.jpg",
    "Australia": "assets/countries/australia.jpg",
    "Canada": "assets/countries/canada.jpg",
    "China": "assets/countries/china.jpg",
}

# Slide Layout Settings
PRODUCTS_PER_SLIDE = 1  # Number of products per slide
SHOW_PREVIOUS_RATE = False  # Show previous rate for comparison
