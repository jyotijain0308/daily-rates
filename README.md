# PPT Daily Rates System

A Python-based system that automatically generates professional PowerPoint presentations with daily product rates, exchange rates, and company branding.

## Features

**Professional PPT Generation**
- Title slide with company name, heading, and current date
- Individual product slides with rate information
- Thank you slide with currency exchange rates
- Customizable colors, fonts, and branding

**Product Management**
- Web UI for importing, editing, and managing product rates
- SQLite database backend with REST API
- Load product data from CSV or JSON files (CLI mode)
- Display current rates and previous rates
- Show rate changes in percentage
- Support for multiple product categories

**Web Interface**
- Dashboard with stats and generation history
- CSV import with preview and validation
- Inline product editing
- One-click PPT generation and download
- Responsive design for desktop and mobile

**Exchange Rate Integration**
- Fetch live exchange rates to INR from free APIs
- Automatic caching to minimize API calls
- Graceful fallback if rates unavailable
- Support for multiple currencies (USD, EUR, GBP, JPY)

**Robust Error Handling**
- Comprehensive validation for all data
- Graceful error recovery
- Detailed logging for debugging
- Sample data generation for testing

## Project Structure

```
PyCharmMiscProject/
├── app/
│   ├── routes/                # Flask API and page routes
│   ├── templates/             # Web UI HTML pages
│   └── static/                # CSS and JavaScript
├── src/
│   ├── config.py              # Configuration & styling
│   ├── product_data.py        # Product data loading & validation
│   ├── exchange_rates.py      # Exchange rate fetching & caching
│   ├── ppt_generator.py       # PPT slide generation
│   ├── error_handling.py      # Error handling & validation
│   ├── main.py                # CLI orchestration workflow
│   └── data/                  # CLI input data (when run from src/)
├── data/                      # Sample data at project root
├── output/                    # Generated PPT/MP4 files (web mode)
├── models.py                  # SQLAlchemy database models
├── db.py                      # Database init and seed utilities
├── csv_importer.py            # CSV validation and bulk import
├── ppt_service.py             # PPT generation service (web)
├── wsgi.py                    # Flask application factory
├── run.py                     # Web server entry point
├── Procfile                   # Production deployment config
├── tests/                     # Integration tests
├── requirements.txt           # Python dependencies
└── ppt_products.db            # SQLite database (created on first run)
```

## Prerequisites

- Python 3.8+
- pip (Python package manager)

---

## Web UI (Recommended)

The web frontend is served by Flask — there is **no separate npm/React build step**. Start the server from the **project root** and open your browser.

### Step 1: Create Virtual Environment

```bash
cd PyCharmMiscProject
python3 -m venv venv_web
source venv_web/bin/activate        # macOS/Linux
# venv_web\Scripts\activate         # Windows
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Initialize Database (Optional)

Load sample products for testing:

```bash
python db.py seed
```

Other database commands:

```bash
python db.py init    # Create tables
python db.py drop    # Drop all tables (use with caution)
```

The SQLite database file `ppt_products.db` is created automatically in the project root on first run.

### Step 4: Start the Web Server

```bash
python run.py
```

Open in your browser: [http://localhost:5001](http://localhost:5001)

> **Note:** The default port is **5001** because macOS AirPlay Receiver often uses port 5000. To use a specific port: `PORT=8000 python run.py`

To stop the server, press `Ctrl+C` in the terminal.

### Web UI Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | [http://localhost:5001/](http://localhost:5001/) | Overview, stats, quick actions |
| Import | [http://localhost:5001/import](http://localhost:5001/import) | Upload CSV, preview, save |
| Products | [http://localhost:5001/products](http://localhost:5001/products) | View and edit product rates |
| Generate | [http://localhost:5001/generate](http://localhost:5001/generate) | Create and download PPT or MP4 |

### Web Workflow

1. **Import** — Upload a CSV file, review the preview, then save to the database
2. **Manage** — Edit rates inline (double-click a cell) or use the Add/Edit modal
3. **Generate** — Select a country and output format, then click Generate
4. **Download** — Download the generated country-specific PPT or MP4 file from the Generate page or Dashboard history

Generated files are saved to `output/`, for example `output/india_products_price_list_20260627_154030.pptx` or `output/india_products_price_list_20260627_154030.mp4`.

On app startup, generated `.pptx` and `.mp4` files from previous days are automatically deleted from `output/` and `src/output/`. Files generated today are kept.

### Run Tests

```bash
source venv_web/bin/activate
python -m unittest tests.test_api -v
```

### Production Deployment

Run from the project root:

```bash
gunicorn "wsgi:create_app()" --bind 0.0.0.0:8000 --workers 2
```

Or use the included `Procfile` with Heroku or similar platforms.

---

## CLI Mode (Alternative)

For command-line PPT generation from CSV/JSON files without the web UI. **All CLI commands below must be run from the `src/` directory** because paths in `src/config.py` are relative to that folder.

### Step 1: Create Virtual Environment

```bash
cd PyCharmMiscProject
python3 -m venv venv_ppt
source venv_ppt/bin/activate        # macOS/Linux
# venv_ppt\Scripts\activate           # Windows
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run the System

```bash
cd src
python main.py
```

The generated PPT files will be saved to `src/output/`, one file per country of origin.

### Using Sample Data

The CLI automatically creates sample data if no products file exists:

```bash
cd src && python main.py
```

### Using Your Own Data

#### CSV Format

Create `src/data/products.csv`:

```csv
S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED
1,India,Air,Wheat Flour,25,Bag,72.50
2,Thailand,Sea,Jasmine Rice,50,Sack,158.00
3,Brazil,Sea,Soybean Meal,40,Bag,121.25
```

**Required columns:** `S.No.`, `Country of origin`, `Shipment by`, `Product Name`, `Weight in kg`, `Packing`, `Price in AED`

When importing, the app uses `Product Name` + `Country of origin` as the unique identifier. Matching rows update the existing product; non-matching rows are inserted.

#### JSON Format

Create `src/data/products.json`:

```json
[
  {
    "serial_no": 1,
    "country_of_origin": "India",
    "shipment_by": "Air",
    "product_name": "Wheat Flour",
    "weight_kg": 25,
    "packing": "Bag",
    "price_aed": 72.50
  }
]
```

Then run:

```bash
cd src && python main.py
```

---

## Configuration

Edit `src/config.py` to customize:

- **Company Details:** Company name, address, website, default country, logo paths
- **Styling:** Colors (primary, accent, background), fonts, font sizes
- **Exchange Rates:** API endpoint, cache duration, country-to-currency mappings
- **Output:** File paths, naming, and daily cleanup settings

### Example: Change Company Name

```python
# In src/config.py
COMPANY_NAME = "Your Company Ltd."
COMPANY_ADDRESS = "Dubai, United Arab Emirates"
COMPANY_WEBSITE = "https://www.example.com"
COMPANY_LOGO_IMAGE = "assets/company_logo.png"
UAE_LOGO_IMAGE = "assets/uae_logo.png"
```

Country logo paths are configured in `COUNTRY_LOGO_IMAGES`. If a configured image file is missing, the PPT uses a text placeholder instead of failing.

Product images are read from `PRODUCT_IMAGES_DIR`, which defaults to `assets/products`. Add product images under `src/assets/products/` using the product-name slug:

```text
src/assets/products/wheat_flour.png
src/assets/products/jasmine_rice.jpg
```

The slug is the lower-case product name with spaces/symbols replaced by underscores.

### Example: Customize Colors

```python
# In src/config.py
COLORS = {
    "primary": RGBColor(0, 102, 204),
    "accent": RGBColor(255, 153, 0),
    "background": RGBColor(255, 255, 255),
    "text": RGBColor(50, 50, 50),
    "light_text": RGBColor(255, 255, 255),
}
```

---

## Generated PPT/MP4 Structure

### Slide 1: Title Slide
- Company logo on top, displayed at native size
- Country logo/image below it, displayed at native size
- Title: `{Country Name} Products Price List`
- Current date

### Slides 2-N: Product Slides
Each product gets its own slide showing:
- Company logo on the top-left
- Country image on the top-right
- Title: `{Product Name} {Weight}kg {Packing}`
- Product image from `src/assets/products/`
- Dark price band: `Price: AED {price}`

### Last Slide: Thank You Slide
- Company logo centered at the top
- Product country logo and UAE logo
- Exchange rate: `1 AED = {rate} {currency code}`
- Company name, address, and website

---

## Features in Detail

### Data Validation
- Validates all product data before PPT generation
- Checks for required fields and valid values
- Prevents invalid files from causing errors

### Exchange Rate Caching
- Rates are cached locally for 24 hours
- Automatically fetches fresh rates when cache expires
- Falls back to cached rates if API is unavailable

### Error Handling
- Comprehensive error logging
- Graceful degradation (e.g., continues without rates if API fails)
- Sample data generation for quick testing

### Logging

| Mode | Log output |
|------|------------|
| Web UI | Terminal where `python run.py` is running |
| CLI | Console and `src/ppt_generator.log` |

Example CLI log output:

```
2026-06-26 22:22:40,059 - __main__ - INFO - Starting PPT generation workflow...
2026-06-26 22:22:40,059 - product_data - INFO - Loaded 6 products from data/products.csv
2026-06-26 22:22:41,353 - exchange_rates - INFO - Fetched exchange rates from API
2026-06-26 22:22:45,076 - ppt_generator - INFO - Presentation saved to output/daily_rates.pptx
```

---

## Customization Examples

### Add Country Currency or Logo

```python
# In src/config.py
COUNTRY_CURRENCY_CODES["India"] = "INR"
COUNTRY_LOGO_IMAGES["India"] = "assets/countries/india.png"
```

### Change Output File Location

```python
# In src/config.py
OUTPUT_PPT_FILE = "output/daily_rates.pptx"   # CLI (relative to src/)
```

Web mode output is controlled in `ppt_service.py` and saved to the project root `output/` folder, one file per country.

### Modify Slide Styling

Edit `PPTGenerator` class methods in `src/ppt_generator.py`:
- `add_title_slide()` — Customize title slide layout
- `add_product_slide()` — Customize product slide template
- `add_thank_you_slide()` — Customize thank you slide

---

## CI/CD

GitHub Actions workflows are provided under `.github/workflows/`.

### CI

`ci.yml` runs on push and pull requests to `main` or `master`:

- sets up Python 3.12
- installs `requirements.txt`
- compiles the main Python modules
- runs `python -m unittest tests/test_api.py`

### CD

`cd.yml` is a manual deployment workflow (`workflow_dispatch`) with staging/production environment selection. It installs dependencies and runs tests before the deploy hook.

Add the provider-specific deployment command in the `Deploy hook` step. Common options:

- Render deploy hook
- Heroku deploy
- Docker image build and push
- SSH rollout to a VPS
- AWS Elastic Beanstalk or ECS deployment

Deployment entry point:

```bash
gunicorn "wsgi:create_app()" --bind 0.0.0.0:$PORT --workers 2
```

This is also configured in `Procfile`.

---

## Troubleshooting

### Web UI: Page won't load
**Solution:** Run `python run.py` from the **project root** (not from `src/`), then visit [http://localhost:5001](http://localhost:5001). Check the terminal for the exact URL and any errors.

### Web UI: "Address already in use" / port conflict
**Solution:** On macOS, port 5000 is often taken by AirPlay Receiver. The app now defaults to port **5001**. Run `python run.py` again, or choose a port explicitly: `PORT=8000 python run.py`. To free port 5000, disable AirPlay Receiver in **System Settings → General → AirDrop & Handoff → AirPlay Receiver**.

### Web UI: Generate button disabled
**Solution:** Import or add at least one product, then select a country on the Generate page.

### Web UI: CSV import fails
**Solution:** Ensure the CSV has required columns (`S.No.`, `Country of origin`, `Shipment by`, `Product Name`, `Weight in kg`, `Packing`, `Price in AED`) and is UTF-8 encoded. Use "Download Template" on the Import page.

### CLI: "File not found" errors
**Solution:** Run commands from the `src/` directory. Ensure `src/data/` and `src/output/` exist, or let the system create them automatically.

### Issue: Exchange rates not fetching
**Solution:** Check your internet connection. Rates will be retried on the next run.

### Issue: PPT file is corrupted
**Solution:** Delete the file in `output/` and regenerate. For CLI mode, check `src/ppt_generator.log` for errors.

### Issue: Memory usage is high with many products
**Solution:** The system generates one slide per product. Current design is efficient for up to 100+ products.

---

## API Used

- **Exchange Rates:** [ExchangeRate-API](https://exchangerate-api.com/)
  - Free tier: 1,500 requests/month
  - No authentication required

## Performance

- **Generation Time:** ~0.5–1 second for 6 products + rates
- **PPT File Size:** ~6–7 KB per product slide
- **Memory Usage:** ~50–100 MB typical

## Future Enhancements

- [ ] Add charts/graphs for rate trends
- [ ] Support for multiple companies in one PPT
- [ ] Email integration to auto-send presentations
- [x] Database backend for product management
- [ ] CLI with command-line arguments
- [x] Web interface for easier configuration
- [ ] Support for multiple languages

## License

This project is provided as-is for your use.

## Support

For issues or questions:

1. **Web UI:** Check the terminal where `python run.py` is running
2. **CLI:** Check `src/ppt_generator.log`
3. Review error messages in the console or browser toast notifications
4. Verify data format matches the expected CSV/JSON structure
5. Test with sample data: `python db.py seed` (web) or `cd src && python main.py` (CLI)
6. Run tests: `python -m unittest tests.test_api -v`

---

**Last Updated:** June 27, 2026  
**Version:** 2.0
