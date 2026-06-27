#!/bin/bash
# Quick Start Guide for PPT Daily Rates System

echo "================================================"
echo "PPT Daily Rates System - Quick Start"
echo "================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Navigate to project
cd "$(dirname "$0")" || exit 1

echo "Setting up virtual environment..."
python3 -m venv venv_ppt

echo "Activating virtual environment..."
source venv_ppt/bin/activate

echo "Installing dependencies..."
pip install -q python-pptx requests python-dateutil pandas

echo "✓ Setup complete!"
echo ""

echo "================================================"
echo "Running PPT Generation"
echo "================================================"
echo ""

cd src || exit 1

echo "Generating PPT with sample data..."
python main.py

echo ""
echo "================================================"
echo "✓ Done! Check output/daily_rates.pptx"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit data/products.csv with your product data"
echo "2. Customize config.py with your company details"
echo "3. Run: python main.py"
echo ""
