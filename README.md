# Taaza Rates

Daily market rates, ready to share.

A Python-based system that imports product rates, manages company-specific product data, and generates branded MP4 rate videos with preview, download, and social publishing workflows.

## Features

**Professional MP4 Generation**
- Title slide with company name, heading, and current date
- Individual product frames with rate information
- Thank you slide with currency exchange rates
- Customizable colors, fonts, and branding

**Product Management**
- Web UI for importing, editing, and managing product rates
- Export all products as a CSV sheet for bulk rate updates
- PostgreSQL database backend with REST API in production
- Product rate history for import and manual price changes
- Products missing images dashboard workflow with direct link to filtered products
- Load product data from CSV or JSON files (CLI mode)
- Display current rates and previous rates
- Show rate changes in percentage
- Support for multiple product categories

**Web Interface**
- Dashboard with stats, missing-image tracking, updated-product tracking, active generation jobs, social connections, and today's generation summary
- CSV import with diff preview, large-change highlighting, confirmation, and validation
- Image table import with OCR preview and validation
- Inline product editing
- One-click MP4 generation, preview, and download
- In-browser MP4 preview before download
- Background MP4 generation with cancellation support
- Responsive design for desktop and mobile

**Authentication and Company Scope**
- Sign in and sign up functionality
- Users belong to an existing registered company
- Products, countries, generation history, audio, and social connections are scoped by company

**Social Publishing**
- Connected social platform status on the dashboard
- Publishing integrations for YouTube, Facebook Page, Instagram Reels, LinkedIn, and X
- Social app keys are managed system-wide in the database from **Company → Social App Keys**
- Manual social options were removed; publishing flows use configured integrations

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

```text
DailyRates/
├── app/
│   ├── models.py              # SQLAlchemy database models
│   ├── routes/                # Flask API and page routes
│   ├── services/              # Business logic and external integrations
│   │   ├── importing/         # CSV, image OCR, and PDF product import logic
│   │   ├── generation/        # PPT/MP4 generation, jobs, cleanup, rates, config
│   │   └── social/            # Social platform integrations
│   ├── templates/             # Web UI HTML pages
│   └── static/                # CSS and JavaScript
├── data/                      # Sample data at project root
├── uploads/
│   ├── assets/                # Uploaded product, company, and country images
│   ├── generated/             # Generated MP4/PPT files
│   └── jobs/                  # Generation job state
├── db.py                      # Database init and seed utilities
├── wsgi.py                    # Flask application factory
├── run.py                     # Optional direct Python web server entry point
├── Procfile                   # Production deployment config
├── tests/                     # Integration tests
├── requirements.txt           # Python dependencies
└── docker-compose.yml         # Web app and PostgreSQL services
```

Root-level files are now limited to app entry points, deployment/configuration files, database utilities, and documentation. Business logic lives under `app/services/`; database models live under `app/models.py`.

## Prerequisites

- Python 3.8+
- pip (Python package manager)
- Tesseract OCR binary for image table import

Install Tesseract before using image import:

```bash
brew install tesseract        # macOS
# sudo apt-get install tesseract-ocr  # Ubuntu/Debian
```

The Docker image installs `tesseract-ocr` automatically for deployed image imports.

---

## Web UI (Recommended)

The web frontend is served by Flask — there is **no separate npm/React build step**. Start the server from the **project root** and open your browser.

### Step 1: Create Environment File

```bash
cp .env.example .env
# edit .env and replace POSTGRES_PASSWORD with a strong secret
```

### Step 2: Start Native PostgreSQL

PostgreSQL runs outside Docker. Start your local PostgreSQL service before starting the app, then create the configured user/database if they do not already exist.

```bash
brew services start postgresql@17
createuser daily_rates_user
createdb -O daily_rates_user ef_daily_rates
```

If you use a different native PostgreSQL version or a managed PostgreSQL server, update `DATABASE_URL` and `HOST_DATABASE_URL` in `.env`.

### Step 3: Start Docker Compose

```bash
docker compose up -d --build
```

This starts the Flask app only. Open in your browser: [http://localhost:8000](http://localhost:8000)

Load sample products into the native PostgreSQL database if needed:

```bash
docker compose exec flask-app python db.py seed
```

To stop the stack:

```bash
docker compose down
```

### Optional: Run Python Commands Directly

The web app uses PostgreSQL. It does not fall back to SQLite when run outside Docker. For the Flask app container, use `host.docker.internal` so it can reach native PostgreSQL on your Mac:

```bash
DATABASE_URL=postgresql+psycopg://ppt_user:your-password@host.docker.internal:5432/ppt_daily_rates
```

For Python commands on your host machine, use `127.0.0.1`:

```bash
HOST_DATABASE_URL=postgresql+psycopg://ppt_user:your-password@127.0.0.1:5432/ppt_daily_rates
```

Use single quotes around manually typed URLs if your password contains shell-special characters.

Install dependencies for direct Python commands:

```bash
python3 -m venv venv_web
source venv_web/bin/activate
pip install -r requirements.txt
```

Initialize or seed the configured PostgreSQL database:

Load sample products for testing:

```bash
python db.py seed
```

Other database commands:

```bash
python db.py init    # Create tables
python db.py drop    # Drop all tables (use with caution)
```

Database migrations are managed with Flask-Migrate/Alembic:

```bash
export FLASK_APP=wsgi:create_app
flask db upgrade
```

For an existing database that was created before migrations were added, run the same upgrade command. The initial migration skips tables that already exist and creates missing tables such as `product_rate_history`. If you have already applied the schema manually, mark the database as current:

```bash
flask db stamp head
```

Start the direct Python development server only after `DATABASE_URL` is set:

```bash
python run.py
```

Open in your browser: [http://localhost:5001](http://localhost:5001)

> **Note:** The default port is **5001** because macOS AirPlay Receiver often uses port 5000. To use a specific port: `PORT=8000 python run.py`

To stop the server, press `Ctrl+C` in the terminal.

### Web UI Pages

The URLs below use the Docker Compose default `APP_PORT=8000`. If you run `python run.py` directly, use the port printed by the server, usually `5001` unless that port is busy.

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | [http://localhost:8000/](http://localhost:8000/) | Overview, stats, missing images, updated products, social connections, today's generations, and active jobs |
| Import | [http://localhost:8000/import](http://localhost:8000/import) | Upload CSV, preview, save |
| Products | [http://localhost:8000/products](http://localhost:8000/products) | View, edit, export product rates, and update product images |
| Generate | [http://localhost:8000/generate](http://localhost:8000/generate) | Create, preview, and download MP4 videos |
| Company | [http://localhost:8000/company](http://localhost:8000/company) | Manage company settings, branding assets, defaults, and social connections |

### Web Workflow

1. **Import** — Upload a CSV file or table image, review created/updated/skipped counts and old-vs-new rate differences, then confirm the save
2. **Manage** — Edit rates inline (double-click a cell), use the Add/Edit modal, or export the full rate sheet from Products
3. **Generate** — Select a country and shipment method, then click Generate MP4. You can cancel an in-progress generation from the same page.
4. **Preview/Download/Share** — Preview the generated MP4 in the browser, then download or publish it from the Generate page
5. **Track** — Use the Dashboard to monitor today's total/success/failed generations, active jobs, missing product images, updated products, large rate changes, and connected social platforms

To update rates in bulk, open **Products**, click **Export Rate Sheet**, update the `Price in AED` values in the downloaded CSV, then upload that CSV on the **Import** page. Existing products are updated by `Product Name` + `Country of origin`. The import preview highlights rate changes of 20% or more before you confirm.

Generated web files are saved to `uploads/generated/`, for example `uploads/generated/videos/india_products_price_list_20260627_154030.mp4`.

On app startup, generated `.pptx` and `.mp4` files from previous days are automatically deleted from `uploads/generated/`. Files generated today are kept.

### Social App Keys

Social publishing app credentials are now stored system-wide in PostgreSQL. Open **Company → Social App Keys** and add keys for the platforms you use:

- **YouTube:** Client ID, Client secret, Redirect URI
- **Facebook & Instagram:** App ID, App secret, Redirect URI, Graph version, Login config ID, Scopes, Public base URL
- **X:** Client ID, Client secret, Redirect URI, Scopes, Media category
- **LinkedIn:** Client ID, Client secret, Redirect URI, Personal scopes, Page scopes, Prompt

The matching `.env` values are still supported as fallback/bootstrap values. If both are present, the system configuration value from the database is used first.

### Dashboard Layout

- Top stats show products, origin countries, total generations, latest MP4, and last import.
- Quick Actions provide direct access to import, products, generate, and latest download.
- Products Missing Images and Products Updated Today appear in one row.
- Products Updated Today includes tabs for updated products and 20%+ large rate changes.
- Social Media Connections appears as a compact auto-width list of configured publishing platforms.
- Today Generations shows total, success, and failed counts in the card header and includes failure reasons when available.
- Pending/Running Jobs appears at the bottom and only shows active jobs updated today.

### Run Tests

```bash
source venv_web/bin/activate
python -m unittest tests.test_api -v
```

### Production Deployment

Set a PostgreSQL database URL before starting the app:

```bash
export DATABASE_URL="postgresql+psycopg://user:password@host:5432/ppt_daily_rates"
```

Then run from the project root:

```bash
gunicorn "wsgi:create_app()" --bind 0.0.0.0:8000 --workers 2
```

Or use the included `Procfile` with Heroku or similar platforms.

For Docker Compose deployments, the included `docker-compose.yml` starts the Flask app and passes `DATABASE_URL` to it. PostgreSQL must already be reachable, either as native PostgreSQL on the host or as an external managed database. Create a real `.env` file from the committed example and keep `.env` only on the server:

```bash
cp .env.example .env
# edit .env and replace the password with a strong secret
docker compose up -d --build
```

By default this exposes the app at [http://localhost:8000](http://localhost:8000). Set `APP_PORT=80` in `.env` for a server that should listen on port 80.

Do not commit `.env`; it is already ignored by git.

For GitHub Actions EC2 deployment, set these repository secrets:

- `EC2_HOST` or `AWS_HOST`
- `EC2_USER` or `AWS_USER`
- `EC2_SSH_KEY` or `AWS_SSH_KEY`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `OPENAI_API_KEY` only if using OpenAI for PDF table extraction

Alternatively, set `DATABASE_URL` if you use an external managed PostgreSQL database. If `DATABASE_URL` is not set, the EC2 workflow creates or reuses a local PostgreSQL Docker container with a persistent Docker volume.

Free local AI PDF import uses Ollama by default:

```bash
brew install ollama
ollama pull llama3.2-vision
ollama serve
```

Then set:

- `PDF_TABLE_EXTRACTION_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434` for local Python
- `OLLAMA_BASE_URL=http://host.docker.internal:11434` for Docker Compose
- `OLLAMA_PDF_EXTRACTION_MODEL=llama3.2-vision`

Optional OpenAI PDF import settings:

- `PDF_TABLE_EXTRACTION_PROVIDER=openai`
- `OPENAI_API_KEY=...`
- `OPENAI_PDF_EXTRACTION_MODEL=gpt-4o-mini`

If the selected AI provider fails or returns no rows, PDF import falls back to text-table extraction and OCR.

---

## CLI Mode (Alternative)

For command-line PPT generation from CSV/JSON files without the web UI. Run commands from the project root.

### Step 1: Create Virtual Environment

```bash
cd DailyRates
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
python -m app.services.generation.main
```

The generated PPT files will be saved to `uploads/generated/presentations/`, one file per country of origin.

### Using Sample Data

The CLI automatically creates sample data if no products file exists:

```bash
python -m app.services.generation.main
```

### Using Your Own Data

#### CSV Format

Create `data/products.csv`:

```csv
S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED
1,India,Air,Wheat Flour,25,Bag,72.50
2,Thailand,Sea,Jasmine Rice,50,Sack,158.00
3,Brazil,Sea,Soybean Meal,40,Bag,121.25
```

**Required columns:** `S.No.`, `Country of origin`, `Shipment by`, `Product Name`, `Weight in kg`, `Packing`, `Price in AED`

When importing, the app uses `Product Name` + `Country of origin` as the unique identifier. Matching rows update the existing product; non-matching rows are inserted.

#### JSON Format

Create `data/products.json`:

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
python -m app.services.generation.main
```

---

## Configuration

Edit `app/services/generation/config.py` to customize:

- **Company Details:** Company name, address, website, default country, logo paths
- **Styling:** Colors (primary, accent, background), fonts, font sizes
- **Exchange Rates:** API endpoint, cache duration, country-to-currency mappings
- **Output:** File paths, naming, and daily cleanup settings

### Example: Change Company Name

```python
# In app/services/generation/config.py
COMPANY_NAME = "Your Company Ltd."
COMPANY_ADDRESS = "Dubai, United Arab Emirates"
COMPANY_WEBSITE = "https://www.example.com"
COMPANY_LOGO_IMAGE = "uploads/assets/company/company_logo.png"
UAE_LOGO_IMAGE = "uploads/assets/company/uae_logo.jpg"
```

Country logo paths are configured in `COUNTRY_LOGO_IMAGES`. If a configured image file is missing, the generator uses a text placeholder instead of failing.

Uploaded and fetched product images are stored under `uploads/assets/products/`. Use the product-name slug:

```text
uploads/assets/products/wheat_flour.png
uploads/assets/products/jasmine_rice.jpg
```

The slug is the lower-case product name with spaces/symbols replaced by underscores.

Asset resolution supports both current and legacy path formats:

```text
uploads/assets/company/company_logo.png
uploads/assets/countries/default/india.jpg
uploads/assets/products/wheat_flour.jpg
assets/company/company_logo.png
assets/countries/default/india.jpg
assets/products/wheat_flour.jpg
company_logo.png
india.jpg
wheat_flour.jpg
```

All generated MP4/PPT rendering resolves assets through `uploads/assets/`, so moving to S3 later can be handled behind the storage/asset layer.

### Example: Customize Colors

```python
# In app/services/generation/config.py
COLORS = {
    "primary": RGBColor(0, 102, 204),
    "accent": RGBColor(255, 153, 0),
    "background": RGBColor(255, 255, 255),
    "text": RGBColor(50, 50, 50),
    "light_text": RGBColor(255, 255, 255),
}
```

---

## Generated MP4/PPT Structure

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
- Product image from `uploads/assets/products/`
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
| Web UI | `docker compose logs -f flask-app` |
| CLI | Console and `ppt_generator.log` |

Example CLI log output:

```
2026-06-26 22:22:40,059 - __main__ - INFO - Starting PPT generation workflow...
2026-06-26 22:22:40,059 - product_data - INFO - Loaded 6 products from data/products.csv
2026-06-26 22:22:41,353 - exchange_rates - INFO - Fetched exchange rates from API
2026-06-26 22:22:45,076 - ppt_generator - INFO - Presentation saved to uploads/generated/presentations/daily_rates.pptx
```

---

## Customization Examples

### Add Country Currency or Logo

```python
# In app/services/generation/config.py
COUNTRY_CURRENCY_CODES["India"] = "INR"
COUNTRY_LOGO_IMAGES["India"] = "uploads/assets/countries/default/india.jpg"
```

### Change Output File Location

```python
# In app/services/generation/config.py
OUTPUT_PPT_FILE = "uploads/generated/presentations/daily_rates.pptx"
```

Web mode output is controlled in `app/services/ppt_service.py` and saved under `uploads/generated/videos/`, one file per country.

### Modify Slide Styling

Edit `PPTGenerator` class methods in `app/services/generation/ppt_generator.py`:
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
**Solution:** Run `docker compose up -d --build` from the **project root**, then visit [http://localhost:8000](http://localhost:8000). Check logs with `docker compose logs -f flask-app`.

### Web UI: "Address already in use" / port conflict
**Solution:** Docker Compose exposes the app on `APP_PORT`, defaulting to **8000**. Set another value in `.env`, for example `APP_PORT=8080`, then run `docker compose up -d`.

### Web UI: Generate button disabled
**Solution:** Import or add at least one product, then select a country on the Generate page.

### Web UI: CSV import fails
**Solution:** Ensure the CSV has required columns (`S.No.`, `Country of origin`, `Shipment by`, `Product Name`, `Weight in kg`, `Packing`, `Price in AED`) and is UTF-8 encoded. Use "Download Template" on the Import page.

### CLI: "File not found" errors
**Solution:** Run CLI commands from the project root. Ensure `data/` and `uploads/` exist, or let the system create them automatically.

### Issue: Exchange rates not fetching
**Solution:** Check your internet connection. Rates will be retried on the next run.

### Issue: PPT file is corrupted
**Solution:** Delete the file in `uploads/generated/presentations/` and regenerate. For CLI mode, check `ppt_generator.log` for errors.

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

1. **Web UI:** Check `docker compose logs -f flask-app`
2. **CLI:** Check `ppt_generator.log`
3. Review error messages in the console or browser toast notifications
4. Verify data format matches the expected CSV/JSON structure
5. Test with sample data after setting `DATABASE_URL`: `python db.py seed` (web) or `python -m app.services.generation.main` (CLI)
6. Run tests: `python -m unittest tests.test_api -v`

---

**Last Updated:** June 27, 2026  
**Version:** 2.0
