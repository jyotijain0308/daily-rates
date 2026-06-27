"""
Configuration module for PPT Daily Rates System
"""
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

# Company Settings
COMPANY_NAME = "Eastern Farms LLC"
COMPANY_SUBTITLE = "Daily Product Rates"
COMPANY_DEFAULT_COUNTRY = "United Arab Emirates"
COMPANY_ADDRESS = "Office #1835, One by Omniyat, Business Bay, Dubai, United Arab Emirates"
COMPANY_WEBSITE = "https://www.easternfarmsllc.com"
COMPANY_LOGO_IMAGE = "assets/company_logo.png"
UAE_LOGO_IMAGE = "assets/uae_logo.png"
PRODUCT_IMAGES_DIR = "assets/products"

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
    "India": "assets/countries/india-large.png",
    "United States": "assets/countries/united_states.png",
    "Brazil": "assets/countries/brazil.png",
    "Thailand": "assets/countries/thailand.png",
    "Vietnam": "assets/countries/vietnam.png",
    "Australia": "assets/countries/australia.png",
    "Canada": "assets/countries/canada.png",
    "China": "assets/countries/china.png",
}

# Slide Layout Settings
PRODUCTS_PER_SLIDE = 1  # Number of products per slide
SHOW_PREVIOUS_RATE = False  # Show previous rate for comparison
