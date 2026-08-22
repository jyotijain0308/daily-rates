"""End-to-end API tests for PPT Daily Rates System"""
import io
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from wsgi import create_app, db, get_database_uri
from app.services.country_service import country_logo_map, seed_default_countries
from app.models import (
    Country,
    GenerationHistory,
    Product,
    ProductRateHistory,
    SocialConnection,
    SocialPublishHistory,
)
from app.services.importing.image_importer import ProductImageOCRImporter
from app.services.importing.pdf_importer import ProductPDFTableImporter
from app.services.generation import config as generator_config


class TestDatabaseUrlConfiguration(unittest.TestCase):
    """Database URL normalization used by local and cPanel deployments."""

    def test_mysql_url_uses_pymysql_driver(self):
        env = {'DATABASE_URL': 'mysql://user:pass@localhost/db', 'HOST_DATABASE_URL': ''}
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(
                get_database_uri(),
                'mysql+pymysql://user:pass@localhost/db',
            )

    def test_postgresql_url_uses_psycopg_driver(self):
        env = {'DATABASE_URL': 'postgresql://user:pass@localhost/db', 'HOST_DATABASE_URL': ''}
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(
                get_database_uri(),
                'postgresql+psycopg://user:pass@localhost/db',
            )


class TestPPTDailyRatesAPI(unittest.TestCase):
    """Integration tests covering the full workflow"""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.db_path}',
        })
        self.client = self.app.test_client()
        self.previous_product_image_auto_fetch = generator_config.PRODUCT_IMAGE_AUTO_FETCH
        generator_config.PRODUCT_IMAGE_AUTO_FETCH = False

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        generator_config.PRODUCT_IMAGE_AUTO_FETCH = self.previous_product_image_auto_fetch
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'healthy')

    def test_company_header_scopes_products_and_countries(self):
        create_response = self.client.post('/api/companies/', json={
            'name': 'Second Company',
            'settings': {
                'currency': 'USD',
                'rate_display_format': 'USD {:.2f}',
            },
        })
        self.assertEqual(create_response.status_code, 201)
        company = create_response.get_json()['data']

        product_payload = {
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        }
        default_response = self.client.post('/api/products/', json=product_payload)
        self.assertEqual(default_response.status_code, 201)

        tenant_response = self.client.post(
            '/api/products/',
            json=product_payload,
            headers={'X-Company-ID': str(company['id'])},
        )
        self.assertEqual(tenant_response.status_code, 201)

        default_list = self.client.get('/api/products/').get_json()['data']
        tenant_list = self.client.get(
            '/api/products/',
            headers={'X-Company-ID': str(company['id'])},
        ).get_json()['data']

        self.assertEqual(len(default_list), 1)
        self.assertEqual(len(tenant_list), 1)
        self.assertNotEqual(default_list[0]['company_id'], tenant_list[0]['company_id'])

        tenant_countries = self.client.get(
            '/api/products/countries',
            headers={'X-Company-ID': str(company['id'])},
        ).get_json()
        self.assertEqual(tenant_countries['default_country'], 'United Arab Emirates')

    def test_company_logo_upload_updates_settings(self):
        image_bytes = io.BytesIO()
        Image.new("RGBA", (12, 8), "blue").save(image_bytes, format="PNG")
        image_bytes.seek(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.routes.company_routes._company_assets_dir', return_value=Path(tmpdir)):
                response = self.client.post(
                    '/api/companies/1/assets/company_logo_image',
                    data={'file': (image_bytes, 'logo.png')},
                    content_type='multipart/form-data',
                )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        settings = data['settings']
        self.assertEqual(settings['company_logo_image'], 'uploads/assets/company/company_logo_1.png')
        self.assertIn('/api/companies/assets/company_logo_1.png', settings['company_logo_url'])

    def test_company_settings_save_social_post_description(self):
        current = self.client.get('/api/companies/current')
        self.assertEqual(current.status_code, 200)
        company = current.get_json()['data']

        payload = {
            'name': company['name'],
            'subtitle': 'Daily wholesale rates',
            'default_country': 'United Arab Emirates',
            'address': 'Dubai, UAE',
            'website': 'https://example.com',
            'currency': 'AED',
            'rate_display_format': 'AED {:.2f}',
            'import_price_deduction_percent': 15,
            'exchange_rate_api_url': '',
            'exchange_rate_cache_hours': 24,
            'social_post_description': 'Default social caption\n\nFollow us for daily rates.',
        }

        response = self.client.put(f"/api/companies/{company['id']}/settings", json=payload)
        self.assertEqual(response.status_code, 200)
        settings = response.get_json()['data']['settings']
        self.assertEqual(settings['social_post_description'], payload['social_post_description'])

        refreshed = self.client.get('/api/companies/current').get_json()['data']['settings']
        self.assertEqual(refreshed['social_post_description'], payload['social_post_description'])

    def test_dashboard_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

    def test_import_preview_and_save_workflow(self):
        csv_content = (
            "S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED\n"
            "1,India,Air,Wheat Flour,25,Bag,72.50\n"
            "2,Thailand,Sea,Jasmine Rice,50,Sack,158.00\n"
        )

        preview_response = self.client.post(
            '/api/import/preview',
            data={'file': (io.BytesIO(csv_content.encode()), 'products.csv')},
            content_type='multipart/form-data',
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.get_json()['preview']
        self.assertEqual(preview['valid_count'], 2)
        self.assertEqual(preview['created_count'], 2)
        self.assertEqual(preview['updated_count'], 0)
        self.assertEqual(preview['skipped_count'], 0)

        save_response = self.client.post('/api/import/save', json={'content': csv_content})
        self.assertEqual(save_response.status_code, 200)
        save_data = save_response.get_json()['data']
        self.assertEqual(save_data['imported_count'], 2)
        self.assertEqual(save_data['created_count'], 2)

        with self.app.app_context():
            self.assertEqual(Product.query.count(), 2)
            self.assertEqual(ProductRateHistory.query.count(), 2)
            wheat_flour = Product.query.filter_by(product_name='Wheat Flour').one()
            self.assertEqual(wheat_flour.price_aed, 61.63)

    def test_import_preview_shows_diff_and_save_records_rate_history(self):
        with self.app.app_context():
            db.session.add(Product(
                serial_no=1,
                country_of_origin='India',
                shipment_by='Air',
                product_name='Wheat Flour',
                weight_kg=25,
                packing='Bag',
                price_aed=61.63,
            ))
            db.session.commit()

        csv_content = (
            "S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED\n"
            "1,India,Air,Wheat Flour,25,Bag,96.00\n"
            "2,Thailand,Sea,Jasmine Rice,50,Sack,158.00\n"
        )

        preview_response = self.client.post(
            '/api/import/preview',
            data={'file': (io.BytesIO(csv_content.encode()), 'products.csv')},
            content_type='multipart/form-data',
        )
        self.assertEqual(preview_response.status_code, 200)
        preview = preview_response.get_json()['preview']
        self.assertEqual(preview['created_count'], 1)
        self.assertEqual(preview['updated_count'], 1)
        self.assertEqual(preview['large_change_count'], 1)
        updated_row = next(row for row in preview['sample_data'] if row['action'] == 'updated')
        self.assertEqual(updated_row['old_price_aed'], 61.63)
        self.assertEqual(updated_row['uploaded_price_aed'], 96.00)
        self.assertEqual(updated_row['new_price_aed'], 81.60)
        self.assertEqual(updated_row['import_price_deduction_percent'], 15.0)
        self.assertTrue(updated_row['large_change'])

        save_response = self.client.post('/api/import/save', json={'content': csv_content})
        self.assertEqual(save_response.status_code, 200)
        save_data = save_response.get_json()['data']
        self.assertEqual(save_data['created_count'], 1)
        self.assertEqual(save_data['updated_count'], 1)
        self.assertEqual(save_data['skipped_count'], 0)

        with self.app.app_context():
            product = Product.query.filter_by(product_name='Wheat Flour').one()
            self.assertEqual(product.price_aed, 81.60)
            history = ProductRateHistory.query.filter_by(product_id=product.id).one()
            self.assertEqual(history.old_price_aed, 61.63)
            self.assertEqual(history.new_price_aed, 81.60)
            self.assertEqual(history.changed_by, 'import')

    def test_import_preview_hides_skipped_rows_from_sample_data(self):
        with self.app.app_context():
            db.session.add(Product(
                serial_no=1,
                country_of_origin='India',
                shipment_by='Air',
                product_name='Wheat Flour',
                weight_kg=25,
                packing='Bag',
                price_aed=61.63,
            ))
            db.session.commit()

        csv_content = (
            "S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED\n"
            "1,India,Air,Wheat Flour,25,Bag,72.50\n"
            "2,Thailand,Sea,Jasmine Rice,50,Sack,158.00\n"
        )

        response = self.client.post(
            '/api/import/preview',
            data={'file': (io.BytesIO(csv_content.encode()), 'products.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['preview']
        self.assertEqual(preview['created_count'], 1)
        self.assertEqual(preview['skipped_count'], 1)
        self.assertEqual(len(preview['sample_data']), 1)
        self.assertEqual(preview['sample_data'][0]['action'], 'created')
        self.assertEqual(preview['sample_data'][0]['product_name'], 'Jasmine Rice')

    def test_import_preview_returns_all_actionable_rows(self):
        csv_content = (
            "S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED\n"
            + "\n".join(
                f"{index},India,Air,Product {index},25,Bag,{70 + index}.00"
                for index in range(1, 13)
            )
            + "\n"
        )

        response = self.client.post(
            '/api/import/preview',
            data={'file': (io.BytesIO(csv_content.encode()), 'products.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['preview']
        self.assertEqual(preview['created_count'], 12)
        self.assertEqual(len(preview['sample_data']), 12)
        self.assertTrue(all(row['action'] == 'created' for row in preview['sample_data']))

    def test_import_preview_groups_repeated_validation_errors(self):
        csv_content = (
            "S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED\n"
            "1,India,Air,Wheat Flour,25,Bag,NA\n"
            "2,India,Air,Jasmine Rice,50,Sack,NA\n"
            "3,India,Air,Almonds,10,Carton,96.00\n"
        )

        response = self.client.post(
            '/api/import/preview',
            data={'file': (io.BytesIO(csv_content.encode()), 'products.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['preview']
        self.assertEqual(preview['error_count'], 1)
        self.assertEqual(
            preview['errors'],
            ["Rows 2, 3: 'Price in AED' must be a valid number, got 'NA'"],
        )
        self.assertEqual(preview['valid_count'], 1)

    def test_import_csv_maps_columns_by_order_not_header_name(self):
        csv_content = (
            "A,B,C,D,E,F,G\n"
            "1,India,Air,Wheat Flour,25,Bag,72.50\n"
        )

        response = self.client.post(
            '/api/import/preview',
            data={'file': (io.BytesIO(csv_content.encode()), 'products.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['preview']
        self.assertEqual(preview['valid_count'], 1)
        row = preview['sample_data'][0]
        self.assertEqual(row['country_of_origin'], 'India')
        self.assertEqual(row['shipment_by'], 'Air')
        self.assertEqual(row['product_name'], 'Wheat Flour')

    def test_import_csv_requires_expected_column_count(self):
        csv_content = (
            "A,B,C,D,E,F\n"
            "1,India,Air,Wheat Flour,25,Bag\n"
        )

        response = self.client.post(
            '/api/import/preview',
            data={'file': (io.BytesIO(csv_content.encode()), 'products.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        preview = response.get_json()['preview']
        self.assertEqual(preview['valid_count'], 0)
        self.assertIn('CSV must have at least 7 columns in this order', preview['errors'][0])

    def test_export_products_downloads_import_compatible_rate_sheet(self):
        with self.app.app_context():
            db.session.add_all([
                Product(
                    serial_no=2,
                    country_of_origin='Thailand',
                    shipment_by='Sea',
                    product_name='Jasmine Rice',
                    weight_kg=50,
                    packing='Sack',
                    price_aed=158.00,
                ),
                Product(
                    serial_no=1,
                    country_of_origin='India',
                    shipment_by='Air',
                    product_name='Wheat Flour',
                    weight_kg=25,
                    packing='Bag',
                    price_aed=72.50,
                ),
            ])
            db.session.commit()

        response = self.client.get('/api/products/export')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn(
            'attachment; filename=all_products_rate_update.csv',
            response.headers['Content-Disposition'],
        )
        csv_content = response.data.decode()
        self.assertIn(
            'S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED',
            csv_content,
        )
        self.assertIn('1,India,Air,Wheat Flour,25,Bag,72.5', csv_content)
        self.assertIn('2,Thailand,Sea,Jasmine Rice,50,Sack,158.0', csv_content)

    def test_image_import_preview_converts_rows_to_existing_csv_contract(self):
        preview_response = self.client.post(
            '/api/import/preview-image',
            data={'file': (io.BytesIO(b'fake image bytes'), 'products.png')},
            content_type='multipart/form-data',
        )

        self.assertEqual(preview_response.status_code, 404)
        data = preview_response.get_json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('disabled', data['message'])

    def test_pdf_import_preview_converts_rows_to_existing_csv_contract(self):
        preview_response = self.client.post(
            '/api/import/preview-pdf',
            data={'file': (io.BytesIO(b'%PDF fake bytes'), 'products.pdf')},
            content_type='multipart/form-data',
        )

        self.assertEqual(preview_response.status_code, 404)
        data = preview_response.get_json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('disabled', data['message'])

    def test_pdf_table_row_parser_uses_column_order(self):
        parsed = ProductPDFTableImporter.parse_table_row([
            '1',
            'India',
            'Sea',
            'Onion New Crop (18 Kg)',
            '1.0',
            'Sold by Weight',
            '3.20',
        ])

        self.assertEqual(parsed['serial_no'], '1')
        self.assertEqual(parsed['country_of_origin'], 'India')
        self.assertEqual(parsed['shipment_by'], 'Sea')
        self.assertEqual(parsed['product_name'], 'Onion New Crop (18 Kg)')
        self.assertEqual(parsed['weight_kg'], '1.0')
        self.assertEqual(parsed['packing'], 'Sold by Weight')
        self.assertEqual(parsed['price_aed'], '3.20')

    def test_pdf_import_falls_back_to_ocr_for_image_based_pdf(self):
        class FakePDF:
            pages = []

            def __enter__(self):
                page = type('FakePage', (), {'extract_tables': lambda self: []})()
                self.pages = [page]
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        fallback_rows = [{
            'serial_no': '1',
            'country_of_origin': 'India',
            'shipment_by': 'Sea',
            'product_name': 'Onion New Crop (18 Kg)',
            'weight_kg': '1.0',
            'packing': 'Sold by Weight',
            'price_aed': '3.20',
        }]
        upload = type('FakeUpload', (), {'read': lambda self: b'%PDF image only'})()

        with patch('pdfplumber.open', return_value=FakePDF()), patch(
            'app.services.importing.pdf_importer.ProductPDFTableImporter.extract_rows_from_pdf_images',
            return_value=(fallback_rows, []),
        ) as fallback:
            rows, warnings = ProductPDFTableImporter.extract_rows_from_upload(upload)

        self.assertEqual(rows, fallback_rows)
        self.assertEqual(warnings, [])
        fallback.assert_called_once_with(b'%PDF image only')

    def test_pdf_import_uses_openai_before_pdf_fallback_when_configured(self):
        from app.services.importing import pdf_importer

        previous_provider = pdf_importer.config.PDF_TABLE_EXTRACTION_PROVIDER
        previous_key = pdf_importer.config.OPENAI_API_KEY
        pdf_importer.config.PDF_TABLE_EXTRACTION_PROVIDER = 'openai'
        pdf_importer.config.OPENAI_API_KEY = 'test-key'
        ai_rows = [{
            'serial_no': '1',
            'country_of_origin': 'India',
            'shipment_by': 'Sea',
            'product_name': 'Onion New Crop (18 Kg)',
            'weight_kg': '1.0',
            'packing': 'Sold by Weight',
            'price_aed': '3.20',
        }]
        upload = type('FakeUpload', (), {
            'filename': 'daily-rates.pdf',
            'read': lambda self: b'%PDF image only',
        })()

        try:
            with patch(
                'app.services.importing.pdf_importer.ProductPDFTableImporter.extract_rows_with_configured_ai',
                return_value=ai_rows,
            ) as ai_extract, patch('pdfplumber.open') as pdf_open:
                rows, warnings = ProductPDFTableImporter.extract_rows_from_upload(upload)
        finally:
            pdf_importer.config.PDF_TABLE_EXTRACTION_PROVIDER = previous_provider
            pdf_importer.config.OPENAI_API_KEY = previous_key

        self.assertEqual(rows, ai_rows)
        self.assertEqual(warnings, [])
        ai_extract.assert_called_once_with(b'%PDF image only', 'daily-rates.pdf')
        pdf_open.assert_not_called()

    def test_ollama_pdf_extraction_calls_local_vision_model(self):
        from app.services.importing import pdf_importer

        previous_model = pdf_importer.config.OLLAMA_PDF_EXTRACTION_MODEL
        previous_url = pdf_importer.config.OLLAMA_BASE_URL
        pdf_importer.config.OLLAMA_PDF_EXTRACTION_MODEL = 'llama3.2-vision'
        pdf_importer.config.OLLAMA_BASE_URL = 'http://localhost:11434'

        response = type('FakeResponse', (), {
            'raise_for_status': lambda self: None,
            'json': lambda self: {
                'response': '{"rows":[{"serial_no":"1","country_of_origin":"India","shipment_by":"Sea","product_name":"Onion New Crop (18 Kg)","weight_kg":"1.0","packing":"Sold by Weight","price_aed":"3.20"}]}'
            },
        })()

        try:
            with patch(
                'app.services.importing.pdf_importer.ProductPDFTableImporter.render_pdf_pages_to_base64_png',
                return_value=['base64-page'],
            ), patch('app.services.importing.pdf_importer.requests.post', return_value=response) as post:
                rows = ProductPDFTableImporter.extract_rows_with_ollama(b'%PDF image only')
        finally:
            pdf_importer.config.OLLAMA_PDF_EXTRACTION_MODEL = previous_model
            pdf_importer.config.OLLAMA_BASE_URL = previous_url

        self.assertEqual(rows[0]['product_name'], 'Onion New Crop (18 Kg)')
        post.assert_called_once()
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['model'], 'llama3.2-vision')
        self.assertEqual(payload['images'], ['base64-page'])

    def test_ai_pdf_response_parser_normalizes_rows(self):
        rows = ProductPDFTableImporter.parse_ai_response("""
        ```json
        {"rows":[{"serial_no":1,"country_of_origin":"India","shipment_by":"Sea","product_name":"Onion New Crop (18 Kg)","weight_kg":"1.0 kg","packing":"Sold by Weight","price_aed":"AED 3.20"}]}
        ```
        """)

        self.assertEqual(rows[0]['serial_no'], '1')
        self.assertEqual(rows[0]['weight_kg'], '1.0')
        self.assertEqual(rows[0]['price_aed'], '3.20')

    def test_ocr_text_parser_returns_normalized_rows(self):
        rows, errors = ProductImageOCRImporter.parse_ocr_text(
            "S.No. Country of origin Shipment by Product Name Weight in kg Packing Price in AED\n"
            "1 India Air Wheat Flour 25 Bag AED 72.50\n"
        )

        self.assertEqual(errors, [])
        self.assertEqual(rows[0]['country_of_origin'], 'India')
        self.assertEqual(rows[0]['shipment_by'], 'Air')
        self.assertEqual(rows[0]['product_name'], 'Wheat Flour')
        self.assertEqual(rows[0]['price_aed'], '72.50')

    def test_ocr_data_parser_uses_column_order_and_ignores_page_text(self):
        words = [
            ("Market", 50, 20), ("Price", 110, 20), ("Updates", 170, 20),
            ("1", 24, 135), ("India", 115, 135), ("Sea", 280, 135), ("Onion", 390, 135),
            ("New", 445, 135), ("Crop", 490, 135), ("(18", 535, 135), ("Kg)", 575, 135),
            ("1.0", 640, 135), ("Sold", 725, 135), ("by", 765, 135), ("Weight", 800, 135), ("3.20", 905, 135),
            ("2", 24, 170), ("India", 115, 170), ("Sea", 280, 170), ("Elephant", 390, 170),
            ("Yam", 465, 170), ("(Suran)", 515, 170), ("9.0", 640, 170), ("Jute", 735, 170),
            ("Bag", 775, 170), ("17.00", 905, 170),
            ("Reporting", 50, 950), ("Daily", 120, 950),
        ]
        data = {
            "text": [word[0] for word in words],
            "left": [word[1] for word in words],
            "top": [word[2] for word in words],
            "width": [max(10, len(word[0]) * 7) for word in words],
            "height": [12 for _ in words],
            "conf": ["90" for _ in words],
            "block_num": [1 for _ in words],
            "par_num": [1 for _ in words],
            "line_num": [index for index, _ in enumerate(words)],
        }

        rows, errors = ProductImageOCRImporter.parse_ocr_data(data)

        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['product_name'], 'Onion New Crop (18 Kg)')
        self.assertEqual(rows[0]['packing'], 'Sold by Weight')
        self.assertEqual(rows[0]['price_aed'], '3.20')
        self.assertEqual(rows[1]['product_name'], 'Elephant Yam (Suran)')
        self.assertEqual(rows[1]['weight_kg'], '9.0')

    def test_import_updates_existing_by_product_name_and_country(self):
        first_import = (
            "S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED\n"
            "1,India,Air,Wheat Flour,25,Bag,72.50\n"
        )
        second_import = (
            "S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED\n"
            "9,India,Sea,Wheat Flour,50,Sack,145.00\n"
        )

        self.client.post('/api/import/save', json={'content': first_import})
        response = self.client.post('/api/import/save', json={'content': second_import})
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertEqual(Product.query.count(), 1)
            product = Product.query.filter_by(product_name='Wheat Flour', country_of_origin='India').first()
            self.assertEqual(product.shipment_by, 'Sea')
            self.assertEqual(product.weight_kg, '50')
            self.assertEqual(product.price_aed, 123.25)

    def test_product_crud(self):
        create_response = self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': '25 kg bag',
            'packing': 'Bag',
            'price_aed': 72.50,
        })
        self.assertEqual(create_response.status_code, 201)
        created_data = create_response.get_json()['data']
        product_id = created_data['id']
        self.assertEqual(created_data['weight_kg'], '25 kg bag')

        update_response = self.client.put(f'/api/products/{product_id}', json={
            'price_aed': 75.0,
            'shipment_by': 'Sea',
        })
        self.assertEqual(update_response.status_code, 200)
        data = update_response.get_json()['data']
        self.assertEqual(data['price_aed'], 75.0)
        self.assertEqual(data['shipment_by'], 'Sea')
        self.assertEqual(data['weight_kg'], '25 kg bag')

        list_response = self.client.get('/api/products/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.get_json()['pagination']['total'], 1)

        delete_response = self.client.delete(f'/api/products/{product_id}')
        self.assertEqual(delete_response.status_code, 200)

        with self.app.app_context():
            self.assertEqual(Product.query.count(), 0)

    def test_product_image_upload_updates_cached_image(self):
        create_response = self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Unit Test Image Upload',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })
        self.assertEqual(create_response.status_code, 201)
        product_id = create_response.get_json()['data']['id']

        image_bytes = io.BytesIO()
        Image.new("RGB", (8, 8), "green").save(image_bytes, format="PNG")
        image_bytes.seek(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            from app.routes import product_routes

            previous_project_root = product_routes.product_image_service.project_root
            previous_uploads_dir = product_routes.product_image_service.uploads_dir
            product_routes.product_image_service.project_root = Path(tmpdir)
            product_routes.product_image_service.uploads_dir = Path(tmpdir) / 'uploads/assets/products'
            try:
                response = self.client.post(
                    f'/api/products/{product_id}/image',
                    data={'file': (image_bytes, 'replacement.png')},
                    content_type='multipart/form-data',
                )
            finally:
                product_routes.product_image_service.project_root = previous_project_root
                product_routes.product_image_service.uploads_dir = previous_uploads_dir

            self.assertEqual(response.status_code, 200)
            data = response.get_json()['data']
            self.assertIn('/api/products/image/unit_test_image_upload.jpg', data['image_url'])
            self.assertTrue((Path(tmpdir) / 'uploads/assets/products/unit_test_image_upload.jpg').exists())

    def test_fetch_product_image_from_pexels_updates_product_image(self):
        create_response = self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Pexels Fetch Product',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })
        self.assertEqual(create_response.status_code, 201)
        product_id = create_response.get_json()['data']['id']

        with tempfile.TemporaryDirectory() as tmpdir:
            from app.routes import product_routes

            previous_project_root = product_routes.product_image_service.project_root
            previous_uploads_dir = product_routes.product_image_service.uploads_dir
            product_routes.product_image_service.project_root = Path(tmpdir)
            product_routes.product_image_service.uploads_dir = Path(tmpdir) / 'uploads/assets/products'
            output_path = Path(tmpdir) / 'uploads/assets/products/pexels_fetch_product.jpg'
            output_path.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), "blue").save(output_path, format="JPEG")

            try:
                with patch.object(
                    product_routes.product_image_service,
                    'fetch_product_image',
                    return_value='uploads/assets/products/pexels_fetch_product.jpg',
                ):
                    response = self.client.post(f'/api/products/{product_id}/image/pexels')
            finally:
                product_routes.product_image_service.project_root = previous_project_root
                product_routes.product_image_service.uploads_dir = previous_uploads_dir

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertIn('/api/products/image/pexels_fetch_product.jpg', data['image_url'])

    def test_search_product_images_from_pexels_returns_options(self):
        create_response = self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Pexels Search Product',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })
        self.assertEqual(create_response.status_code, 201)
        product_id = create_response.get_json()['data']['id']

        from app.routes import product_routes

        with patch.object(
            product_routes.product_image_service,
            'search_product_images',
            return_value=[{
                'image_url': 'https://images.pexels.com/photos/product.jpg',
                'thumb_url': 'https://images.pexels.com/photos/product_tiny.jpg',
                'alt': 'Product image',
                'photographer': 'Test Photographer',
            }],
        ) as mock_search:
            response = self.client.post(
                f'/api/products/{product_id}/image/pexels/search',
                json={'description': 'Pexels Search Product India', 'page': 3},
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['thumb_url'], 'https://images.pexels.com/photos/product_tiny.jpg')
        mock_search.assert_called_once_with(
            'Pexels Search Product',
            'India',
            description='Pexels Search Product India',
            page=3,
            per_page=5,
        )

    def test_select_product_image_from_pexels_updates_product_image(self):
        create_response = self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Pexels Select Product',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })
        self.assertEqual(create_response.status_code, 201)
        product_id = create_response.get_json()['data']['id']

        with tempfile.TemporaryDirectory() as tmpdir:
            from app.routes import product_routes

            previous_project_root = product_routes.product_image_service.project_root
            previous_uploads_dir = product_routes.product_image_service.uploads_dir
            product_routes.product_image_service.project_root = Path(tmpdir)
            product_routes.product_image_service.uploads_dir = Path(tmpdir) / 'uploads/assets/products'
            output_path = Path(tmpdir) / 'uploads/assets/products/pexels_select_product.jpg'
            output_path.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), "blue").save(output_path, format="JPEG")

            try:
                with patch.object(
                    product_routes.product_image_service,
                    'save_product_image_from_url',
                    return_value='uploads/assets/products/pexels_select_product.jpg',
                ):
                    response = self.client.post(
                        f'/api/products/{product_id}/image/pexels/select',
                        json={'image_url': 'https://images.pexels.com/photos/product.jpg'},
                    )
            finally:
                product_routes.product_image_service.project_root = previous_project_root
                product_routes.product_image_service.uploads_dir = previous_uploads_dir

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertIn('/api/products/image/pexels_select_product.jpg', data['image_url'])

    def test_manual_product_update_records_rate_history(self):
        create_response = self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })
        self.assertEqual(create_response.status_code, 201)
        product_id = create_response.get_json()['data']['id']

        update_response = self.client.put(f'/api/products/{product_id}', json={
            'price_aed': 80.00,
        })
        self.assertEqual(update_response.status_code, 200)

        with self.app.app_context():
            history = ProductRateHistory.query.filter_by(product_id=product_id).order_by(
                ProductRateHistory.changed_at.asc()
            ).all()
            self.assertEqual(len(history), 2)
            self.assertIsNone(history[0].old_price_aed)
            self.assertEqual(history[0].new_price_aed, 72.50)
            self.assertEqual(history[1].old_price_aed, 72.50)
            self.assertEqual(history[1].new_price_aed, 80.00)
            self.assertEqual(history[1].changed_by, 'manual')

    def test_product_stats_route(self):
        self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })

        response = self.client.get('/api/products/stats')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['total_products'], 1)
        self.assertEqual(data['total_countries'], 1)
        self.assertEqual(data['active_countries'], 1)
        self.assertIn('India', data['countries'])
        self.assertIn('Air', data['shipments'])
        self.assertEqual(data['currency'], 'AED')

    def test_country_management_crud_and_active_dropdown(self):
        create_response = self.client.post('/api/countries/', json={
            'name': 'Peru',
            'currency_code': 'pen',
            'logo_image': 'assets/countries/peru.jpg',
            'is_active': True,
        })
        self.assertEqual(create_response.status_code, 201)
        country = create_response.get_json()['data']
        self.assertEqual(country['name'], 'Peru')
        self.assertEqual(country['currency_code'], 'PEN')
        self.assertIsNone(country['logo_url'])

        dropdown_response = self.client.get('/api/products/countries')
        self.assertEqual(dropdown_response.status_code, 200)
        self.assertIn('Peru', dropdown_response.get_json()['data'])

        update_response = self.client.put(f"/api/countries/{country['id']}", json={
            'is_active': False,
        })
        self.assertEqual(update_response.status_code, 200)

        dropdown_response = self.client.get('/api/products/countries')
        self.assertEqual(dropdown_response.status_code, 200)
        self.assertNotIn('Peru', dropdown_response.get_json()['data'])

    def test_product_create_auto_adds_country(self):
        response = self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'Bangladesh',
            'shipment_by': 'Air',
            'product_name': 'Fresh Grapes',
            'weight_kg': 8,
            'packing': 'Box',
            'price_aed': 42.00,
        })
        self.assertEqual(response.status_code, 201)

        with self.app.app_context():
            country = Country.query.filter_by(name='Bangladesh').first()
            self.assertIsNotNone(country)
            self.assertEqual(country.currency_code, 'BDT')

    def test_seed_backfills_known_country_currency_codes(self):
        with self.app.app_context():
            country = Country(name='Bangladesh', currency_code=None, is_active=True)
            db.session.add(country)
            db.session.commit()

            seed_default_countries()

            self.assertEqual(Country.query.filter_by(name='Bangladesh').first().currency_code, 'BDT')

    def test_country_flag_upload_updates_logo_image(self):
        create_response = self.client.post('/api/countries/', json={
            'name': 'Flag Test Country',
            'currency_code': 'USD',
            'is_active': True,
        })
        self.assertEqual(create_response.status_code, 201)
        country_id = create_response.get_json()['data']['id']

        image_bytes = io.BytesIO()
        Image.new("RGB", (1200, 700), "yellow").save(image_bytes, format="PNG")
        image_bytes.seek(0)

        with tempfile.TemporaryDirectory() as tmpdir:
            previous_dir = self.app.config['COUNTRY_ASSETS_DIR']
            self.app.config['COUNTRY_ASSETS_DIR'] = tmpdir
            try:
                response = self.client.post(
                    f'/api/countries/{country_id}/flag',
                    data={'file': (image_bytes, 'flag.png')},
                    content_type='multipart/form-data',
                )
            finally:
                self.app.config['COUNTRY_ASSETS_DIR'] = previous_dir

            self.assertEqual(response.status_code, 200)
            data = response.get_json()['data']
            self.assertEqual(data['logo_image'], 'uploads/assets/countries/eastern-farms-llc/flag_test_country.jpg')
            self.assertIn('/api/countries/image/uploads/assets/countries/eastern-farms-llc/flag_test_country.jpg', data['logo_url'])
            saved_path = Path(tmpdir) / 'eastern-farms-llc' / 'flag_test_country.jpg'
            self.assertTrue(saved_path.exists())
            with Image.open(saved_path) as saved_image:
                self.assertEqual(saved_image.size, (300, 200))
                self.assertEqual(saved_image.format, 'JPEG')

    def test_country_listing_uses_company_country_folder_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            company_dir = Path(tmpdir) / 'eastern-farms-llc'
            company_dir.mkdir(parents=True)
            image_path = company_dir / 'company_folder_country.jpg'
            Image.new("RGB", (300, 200), "green").save(image_path, format="JPEG")

            previous_dir = self.app.config['COUNTRY_ASSETS_DIR']
            self.app.config['COUNTRY_ASSETS_DIR'] = tmpdir
            try:
                create_response = self.client.post('/api/countries/', json={
                    'name': 'Company Folder Country',
                    'currency_code': 'USD',
                    'is_active': True,
                })
                self.assertEqual(create_response.status_code, 201)
                data = create_response.get_json()['data']
                self.assertIsNone(data['logo_image'])
                self.assertIn('/api/countries/image/uploads/assets/countries/eastern-farms-llc/company_folder_country.jpg', data['logo_url'])

                list_response = self.client.get('/api/countries/')
                self.assertEqual(list_response.status_code, 200)
                listed = next(
                    country
                    for country in list_response.get_json()['data']
                    if country['name'] == 'Company Folder Country'
                )
                self.assertIn('/api/countries/image/uploads/assets/countries/eastern-farms-llc/company_folder_country.jpg', listed['logo_url'])
            finally:
                self.app.config['COUNTRY_ASSETS_DIR'] = previous_dir

    def test_generation_country_logo_map_uses_company_country_folder_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            company_dir = Path(tmpdir) / 'eastern-farms-llc'
            company_dir.mkdir(parents=True)
            Image.new("RGB", (300, 200), "blue").save(
                company_dir / 'generation_country.jpg',
                format="JPEG",
            )

            with self.app.app_context(), patch('app.services.country_service._country_assets_dir', return_value=Path(tmpdir)):
                db.session.add(Country(
                    company_id=1,
                    name='Generation Country',
                    currency_code='USD',
                    is_active=True,
                ))
                db.session.commit()

                logos = country_logo_map(company_id=1)

        self.assertEqual(
            logos['Generation Country'],
            'uploads/assets/countries/eastern-farms-llc/generation_country.jpg',
        )

    def test_generation_creates_selected_country_mp4_even_when_ppt_requested(self):
        self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })
        self.client.post('/api/products/', json={
            'serial_no': 2,
            'country_of_origin': 'Thailand',
            'shipment_by': 'Sea',
            'product_name': 'Jasmine Rice',
            'weight_kg': 50,
            'packing': 'Sack',
            'price_aed': 158.00,
        })

        with patch('app.routes.generation_routes.start_generation_job') as mock_start_job:
            response = self.client.post('/api/generation/generate', json={
                'country': 'India',
                'shipment_by': 'Air',
                'format': 'ppt',
            })

        self.assertEqual(response.status_code, 202)
        data = response.get_json()
        self.assertEqual(data['status'], 'accepted')
        self.assertEqual(data['data']['country'], 'India')
        self.assertEqual(data['data']['shipment_by'], 'Air')
        self.assertEqual(data['data']['product_count'], 1)
        self.assertEqual(data['data']['status'], 'queued')
        self.assertIn('job_id', data['data'])
        mock_start_job.assert_called_once()

    def test_generation_creates_selected_country_mp4(self):
        self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })

        with patch('app.routes.generation_routes.start_generation_job') as mock_start_job:
            response = self.client.post('/api/generation/generate', json={
                'country': 'India',
                'shipment_by': 'Air',
                'format': 'mp4',
            })

        self.assertEqual(response.status_code, 202)
        data = response.get_json()['data']
        self.assertEqual(data['country'], 'India')
        self.assertEqual(data['shipment_by'], 'Air')
        self.assertEqual(data['product_count'], 1)
        self.assertEqual(data['status'], 'queued')
        self.assertIn('job_id', data)
        mock_start_job.assert_called_once()

    def test_generation_uses_currency_code_from_countries_table(self):
        with self.app.app_context():
            country = Country.query.filter_by(name='Bangladesh').first()
            if not country:
                country = Country(name='Bangladesh', is_active=False)
                db.session.add(country)
            country.currency_code = 'BDT'
            db.session.add(Product(
                serial_no=1,
                country_of_origin='Bangladesh',
                shipment_by='Sea',
                product_name='Potato',
                weight_kg=10,
                packing='Bag',
                price_aed=25.00,
            ))
            db.session.commit()

            with patch('ppt_service.PPTGenerationService._get_aed_exchange_rates', return_value={'BDT': 32.5}) as mock_rates:
                with patch('ppt_service.MP4Generator') as mock_generator_class:
                    mock_generator = mock_generator_class.return_value
                    mock_generator.save.return_value = None

                    from app.services.ppt_service import PPTGenerationService
                    success, result, error = PPTGenerationService.generate_ppt(
                        country_filter='Bangladesh',
                        shipment_filter='Sea',
                    )

        self.assertTrue(success, error)
        mock_rates.assert_called_once_with(['BDT'])
        self.assertEqual(result['files'][0]['currency_code'], 'BDT')
        self.assertEqual(result['files'][0]['exchange_rate'], 32.5)

    def test_mp4_preview_serves_video_inline(self):
        os.makedirs('uploads/generated/videos', exist_ok=True)
        filename = 'unit_test_preview.mp4'
        path = Path('uploads/generated/videos') / filename
        path.write_bytes(b'fake mp4 bytes')

        try:
            response = self.client.get(f'/api/generation/preview/{filename}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'video/mp4')
            self.assertNotIn('attachment', response.headers.get('Content-Disposition', ''))
        finally:
            path.unlink(missing_ok=True)

    def test_preview_rejects_non_mp4_files(self):
        response = self.client.get('/api/generation/preview/example.pptx')
        self.assertEqual(response.status_code, 400)
        self.assertIn('MP4', response.get_json()['message'])

    def test_generation_requires_country(self):
        response = self.client.post('/api/generation/generate')
        self.assertEqual(response.status_code, 400)

    def test_generation_requires_shipment(self):
        response = self.client.post('/api/generation/generate', json={'country': 'India'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('shipment', response.get_json()['message'].lower())

    def test_generation_audio_upload_accepts_audio_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            previous_dir = self.app.config['GENERATION_AUDIO_DIR']
            self.app.config['GENERATION_AUDIO_DIR'] = tmpdir
            try:
                response = self.client.post(
                    '/api/generation/audio',
                    data={
                        'file': (io.BytesIO(b'fake audio bytes'), 'background.mp3'),
                        'rights_confirmed': 'true',
                    },
                    content_type='multipart/form-data',
                )
            finally:
                self.app.config['GENERATION_AUDIO_DIR'] = previous_dir

            self.assertEqual(response.status_code, 200)
            data = response.get_json()['data']
            self.assertTrue(data['file_path'].endswith('.mp3'))
            self.assertTrue(Path(data['file_path']).exists())
            self.assertIn('/api/generation/audio/', data['audio_url'])

    def test_generation_audio_upload_requires_rights_confirmation(self):
        response = self.client.post(
            '/api/generation/audio',
            data={'file': (io.BytesIO(b'fake audio bytes'), 'background.mp3')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('rights', response.get_json()['message'].lower())

    def test_generation_audio_list_and_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            previous_dir = self.app.config['GENERATION_AUDIO_DIR']
            self.app.config['GENERATION_AUDIO_DIR'] = tmpdir
            try:
                upload_response = self.client.post(
                    '/api/generation/audio',
                    data={
                        'file': (io.BytesIO(b'fake audio bytes'), 'background.mp3'),
                        'rights_confirmed': 'true',
                    },
                    content_type='multipart/form-data',
                )
                audio = upload_response.get_json()['data']

                list_response = self.client.get('/api/generation/audio')
                preview_response = self.client.get(audio['audio_url'])
            finally:
                self.app.config['GENERATION_AUDIO_DIR'] = previous_dir

            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(list_response.get_json()['data'][0]['id'], audio['id'])
            self.assertEqual(preview_response.status_code, 200)

    def test_generation_accepts_existing_audio_id(self):
        self.client.post('/api/products/', json={
            'serial_no': 1,
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': 25,
            'packing': 'Bag',
            'price_aed': 72.50,
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            previous_dir = self.app.config['GENERATION_AUDIO_DIR']
            self.app.config['GENERATION_AUDIO_DIR'] = tmpdir
            audio_path = Path(tmpdir) / 'existing.mp3'
            audio_path.write_bytes(b'fake audio bytes')
            try:
                with self.app.app_context():
                    from app.models import BackgroundAudio
                    audio = BackgroundAudio(
                        original_filename='existing.mp3',
                        stored_filename='existing.mp3',
                        file_path=str(audio_path),
                        rights_confirmed=True,
                    )
                    db.session.add(audio)
                    db.session.commit()
                    audio_id = audio.id

                with patch('app.routes.generation_routes.start_generation_job') as mock_start_job:
                    response = self.client.post('/api/generation/generate', json={
                        'country': 'India',
                        'shipment_by': 'Air',
                        'audio_id': str(audio_id),
                    })
            finally:
                self.app.config['GENERATION_AUDIO_DIR'] = previous_dir

        self.assertEqual(response.status_code, 202)
        self.assertEqual(mock_start_job.call_args.kwargs['audio_path'], str(audio_path))

    def test_generation_status(self):
        response = self.client.get('/api/generation/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertIn('total_products', data)
        self.assertIn('total_generations', data)
        self.assertIn('shipments_by_country', data)

    def test_generation_warns_for_duplicate_same_day_content(self):
        from app.routes.generation_routes import _generation_fingerprint

        with self.app.app_context():
            product = Product(
                company_id=1,
                serial_no=1,
                country_of_origin='India',
                shipment_by='Air',
                product_name='Tomato',
                weight_kg='5',
                packing='Box',
                price_aed=10,
            )
            db.session.add(product)
            db.session.flush()
            fingerprint, _payload = _generation_fingerprint(
                1,
                'India',
                'Air',
                [product],
                generation_date=date.today(),
            )
            db.session.add(GenerationHistory(
                company_id=1,
                filename='india_air_products_price_list_existing.mp4',
                product_count=1,
                generation_date=date.today(),
                content_fingerprint=fingerprint,
                file_path='uploads/generated/videos/india_air_products_price_list_existing.mp4',
                status='success',
            ))
            db.session.commit()

        response = self.client.post('/api/generation/generate', json={
            'country': 'India',
            'shipment_by': 'Air',
        })

        self.assertEqual(response.status_code, 409)
        data = response.get_json()
        self.assertEqual(data['status'], 'duplicate')
        self.assertTrue(data['data']['duplicate'])
        self.assertEqual(
            data['data']['existing_generation']['filename'],
            'india_air_products_price_list_existing.mp4',
        )

    def test_generation_force_bypasses_duplicate_warning(self):
        from app.routes.generation_routes import _generation_fingerprint

        with self.app.app_context():
            product = Product(
                company_id=1,
                serial_no=1,
                country_of_origin='India',
                shipment_by='Air',
                product_name='Tomato',
                weight_kg='5',
                packing='Box',
                price_aed=10,
            )
            db.session.add(product)
            db.session.flush()
            fingerprint, _payload = _generation_fingerprint(
                1,
                'India',
                'Air',
                [product],
                generation_date=date.today(),
            )
            db.session.add(GenerationHistory(
                company_id=1,
                filename='india_air_products_price_list_existing.mp4',
                product_count=1,
                generation_date=date.today(),
                content_fingerprint=fingerprint,
                file_path='uploads/generated/videos/india_air_products_price_list_existing.mp4',
                status='success',
            ))
            db.session.commit()

        with patch('app.routes.generation_routes.start_generation_job') as start_job:
            response = self.client.post('/api/generation/generate', json={
                'country': 'India',
                'shipment_by': 'Air',
                'force': True,
            })

        self.assertEqual(response.status_code, 202)
        start_job.assert_called_once()

    def test_generation_share_metadata_returns_product_names_for_mp4(self):
        with self.app.app_context():
            db.session.add_all([
                Product(
                    company_id=1,
                    serial_no=1,
                    country_of_origin='India',
                    shipment_by='Air',
                    product_name='Tomato',
                    weight_kg='5',
                    packing='Box',
                    price_aed=10,
                ),
                Product(
                    company_id=1,
                    serial_no=2,
                    country_of_origin='India',
                    shipment_by='Air',
                    product_name='Onion',
                    weight_kg='10',
                    packing='Bag',
                    price_aed=12,
                ),
                Product(
                    company_id=1,
                    serial_no=3,
                    country_of_origin='India',
                    shipment_by='Sea',
                    product_name='Potato',
                    weight_kg='25',
                    packing='Bag',
                    price_aed=20,
                ),
            ])
            db.session.add(GenerationHistory(
                company_id=1,
                filename='india_air_products_price_list_20260721_120000.mp4',
                product_count=2,
                file_path='uploads/generated/videos/india_air_products_price_list_20260721_120000.mp4',
                status='success',
            ))
            db.session.commit()

        response = self.client.get('/api/generation/share-metadata/india_air_products_price_list_20260721_120000.mp4')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['country'], 'India')
        self.assertEqual(data['shipment_by'], 'Air')
        self.assertEqual(data['product_names'], ['Onion', 'Tomato'])
        self.assertNotIn('Potato', data['product_names'])

    def test_youtube_status_reports_missing_configuration(self):
        with patch.dict(os.environ, {
            'YOUTUBE_CLIENT_ID': '',
            'YOUTUBE_CLIENT_SECRET': '',
        }):
            response = self.client.get('/api/social/youtube/status')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertFalse(data['configured'])
        self.assertFalse(data['connected'])

    def test_youtube_connect_url_requires_oauth_configuration(self):
        with patch.dict(os.environ, {
            'YOUTUBE_CLIENT_ID': '',
            'YOUTUBE_CLIENT_SECRET': '',
        }):
            response = self.client.get('/api/social/youtube/connect-url')

        self.assertEqual(response.status_code, 400)
        self.assertIn('YOUTUBE_CLIENT_ID', response.get_json()['message'])

    def test_youtube_publish_requires_connected_channel(self):
        output_path = Path('uploads/generated/videos/unit_test_youtube.mp4')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b'fake mp4')
        self.addCleanup(lambda: output_path.unlink(missing_ok=True))

        with self.app.app_context():
            db.session.add(GenerationHistory(
                company_id=1,
                filename=output_path.name,
                product_count=1,
                file_path=str(output_path),
                status='success',
            ))
            db.session.commit()

        response = self.client.post('/api/social/youtube/publish', json={
            'filename': output_path.name,
            'title': 'Unit Test Video',
            'description': 'Unit test description',
            'privacy_status': 'private',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('not connected', response.get_json()['message'])

    def test_facebook_status_reports_missing_configuration(self):
        with patch.dict(os.environ, {
            'FACEBOOK_APP_ID': '',
            'FACEBOOK_APP_SECRET': '',
        }):
            response = self.client.get('/api/social/facebook/status')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertFalse(data['configured'])
        self.assertFalse(data['connected'])
        self.assertEqual(data['personal_sharing'], 'manual')

    def test_facebook_connect_url_requires_oauth_configuration(self):
        with patch.dict(os.environ, {
            'FACEBOOK_APP_ID': '',
            'FACEBOOK_APP_SECRET': '',
        }):
            response = self.client.get('/api/social/facebook/connect-url')

        self.assertEqual(response.status_code, 400)
        self.assertIn('FACEBOOK_APP_ID', response.get_json()['message'])

    def test_facebook_connect_url_supports_business_login_config_id(self):
        with patch.dict(os.environ, {
            'FACEBOOK_APP_ID': 'test-app-id',
            'FACEBOOK_APP_SECRET': 'test-secret',
            'FACEBOOK_LOGIN_CONFIG_ID': 'test-config-id',
            'FACEBOOK_REDIRECT_URI': 'http://localhost:5001/api/social/facebook/callback',
        }):
            response = self.client.get('/api/social/facebook/connect-url')

        self.assertEqual(response.status_code, 200)
        auth_url = response.get_json()['data']['auth_url']
        self.assertIn('config_id=test-config-id', auth_url)
        self.assertNotIn('scope=', auth_url)

    def test_facebook_pages_without_page_tokens_reports_permission_issue(self):
        fake_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'data': [{'id': 'page-id', 'name': 'Test Page'}]},
        })()

        from app.services.social.facebook_service import FacebookPublishError, fetch_facebook_pages

        with patch('facebook_service.requests.get', return_value=fake_response):
            with self.assertRaises(FacebookPublishError) as error:
                fetch_facebook_pages('user-token')

        self.assertIn('did not return Page access tokens', str(error.exception))

    def test_facebook_pages_fetches_missing_page_token_by_page_id(self):
        accounts_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'data': [{'id': 'page-id', 'name': 'Test Page'}]},
        })()
        page_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'access_token': 'page-token'},
        })()

        from app.services.social.facebook_service import fetch_facebook_pages

        with patch('facebook_service.requests.get', side_effect=[accounts_response, page_response]):
            pages = fetch_facebook_pages('user-token')

        self.assertEqual(pages[0]['id'], 'page-id')
        self.assertEqual(pages[0]['access_token'], 'page-token')

    def test_facebook_pages_fetches_assigned_pages_when_accounts_empty(self):
        accounts_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'data': []},
        })()
        assigned_pages_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'data': [{
                'id': 'assigned-page-id',
                'name': 'Assigned Page',
                'tasks': ['CREATE_CONTENT'],
            }]},
        })()
        page_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'access_token': 'assigned-page-token'},
        })()

        from app.services.social.facebook_service import fetch_facebook_pages

        with patch(
            'facebook_service.requests.get',
            side_effect=[accounts_response, assigned_pages_response, page_response],
        ):
            pages = fetch_facebook_pages('user-token')

        self.assertEqual(pages[0]['id'], 'assigned-page-id')
        self.assertEqual(pages[0]['access_token'], 'assigned-page-token')

    def test_facebook_pages_empty_reports_granted_permissions(self):
        accounts_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'data': []},
        })()
        assigned_pages_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'data': []},
        })()
        permissions_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'data': [
                {'permission': 'pages_show_list', 'status': 'granted'},
                {'permission': 'email', 'status': 'declined'},
            ]},
        })()

        from app.services.social.facebook_service import FacebookPublishError, fetch_facebook_pages

        with patch(
            'facebook_service.requests.get',
            side_effect=[accounts_response, assigned_pages_response, permissions_response],
        ):
            with self.assertRaises(FacebookPublishError) as error:
                fetch_facebook_pages('user-token')

        self.assertIn('/me/assigned_pages', str(error.exception))
        self.assertIn('Granted permissions in this token: pages_show_list', str(error.exception))

    def test_facebook_publish_requires_connected_page(self):
        output_path = Path('uploads/generated/videos/unit_test_facebook.mp4')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b'fake mp4')
        self.addCleanup(lambda: output_path.unlink(missing_ok=True))

        with self.app.app_context():
            db.session.add(GenerationHistory(
                company_id=1,
                filename=output_path.name,
                product_count=1,
                file_path=str(output_path),
                status='success',
            ))
            db.session.commit()

        response = self.client.post('/api/social/facebook/publish', json={
            'filename': output_path.name,
            'title': 'Unit Test Video',
            'description': 'Unit test description',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('not connected', response.get_json()['message'])

    def test_instagram_status_depends_on_facebook_page_connection(self):
        response = self.client.get('/api/social/instagram/status')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertFalse(data['connected'])
        self.assertFalse(data['facebook_connected'])
        self.assertEqual(data['publishing_target'], 'reels')

    def test_instagram_publish_requires_public_base_url(self):
        output_path = Path('uploads/generated/videos/unit_test_instagram.mp4')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b'fake mp4')
        self.addCleanup(lambda: output_path.unlink(missing_ok=True))

        with self.app.app_context():
            db.session.add(GenerationHistory(
                company_id=1,
                filename=output_path.name,
                product_count=1,
                file_path=str(output_path),
                status='success',
            ))
            db.session.add(SocialConnection(
                company_id=1,
                provider='facebook',
                access_token='page-token',
                refresh_token='user-token',
                external_account_id='page-id',
                external_account_name='Page Name',
            ))
            db.session.commit()

        with patch.dict(os.environ, {'SOCIAL_PUBLIC_BASE_URL': '', 'APP_PUBLIC_BASE_URL': ''}):
            response = self.client.post('/api/social/instagram/publish', json={
                'filename': output_path.name,
                'title': 'Unit Test Reel',
                'description': 'Unit test caption',
            })

        self.assertEqual(response.status_code, 400)
        self.assertIn('SOCIAL_PUBLIC_BASE_URL', response.get_json()['message'])

    def test_instagram_publish_preflights_public_mp4_url(self):
        output_path = Path('uploads/generated/videos/unit_test_instagram_preflight.mp4')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b'fake mp4')
        self.addCleanup(lambda: output_path.unlink(missing_ok=True))

        with self.app.app_context():
            db.session.add(GenerationHistory(
                company_id=1,
                filename=output_path.name,
                product_count=1,
                file_path=str(output_path),
                status='success',
            ))
            db.session.add(SocialConnection(
                company_id=1,
                provider='facebook',
                access_token='page-token',
                refresh_token='user-token',
                external_account_id='page-id',
                external_account_name='Page Name',
            ))
            db.session.commit()

        fake_response = type('FakeResponse', (), {
            'status_code': 404,
            'headers': {'Content-Type': 'text/html', 'Server': 'Apache'},
            'close': lambda self: None,
        })()

        with patch.dict(os.environ, {'SOCIAL_PUBLIC_BASE_URL': 'https://example.ngrok-free.dev'}), \
                patch('app.routes.social_routes.requests.get', return_value=fake_response):
            response = self.client.post('/api/social/instagram/publish', json={
                'filename': output_path.name,
                'title': 'Unit Test Reel',
                'description': 'Unit test caption',
            })

        self.assertEqual(response.status_code, 400)
        self.assertIn('HTTP 404 from Apache', response.get_json()['message'])

    def test_instagram_publish_returns_existing_published_post(self):
        output_path = Path('uploads/generated/videos/unit_test_instagram_existing.mp4')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b'fake mp4')
        self.addCleanup(lambda: output_path.unlink(missing_ok=True))

        with self.app.app_context():
            generation = GenerationHistory(
                company_id=1,
                filename=output_path.name,
                product_count=1,
                file_path=str(output_path),
                status='success',
            )
            db.session.add(generation)
            db.session.flush()
            db.session.add(SocialConnection(
                company_id=1,
                provider='facebook',
                access_token='page-token',
                refresh_token='user-token',
                external_account_id='page-id',
                external_account_name='Page Name',
            ))
            db.session.add(SocialPublishHistory(
                company_id=1,
                provider='instagram',
                generation_id=generation.id,
                filename=output_path.name,
                title='Existing Reel',
                status='published',
                external_post_id='media-id',
                external_post_url='https://www.instagram.com/p/media-id/',
            ))
            db.session.commit()

        with patch(
            'app.routes.social_routes.fetch_instagram_media_permalink',
            return_value='https://www.instagram.com/reel/ABC123/',
        ) as fetch_permalink, patch('app.routes.social_routes.upload_instagram_reel') as upload_reel:
            response = self.client.post('/api/social/instagram/publish', json={
                'filename': output_path.name,
                'title': 'Unit Test Reel',
                'description': 'Unit test caption',
            })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['message'], 'Already published to Instagram')
        self.assertEqual(data['data']['external_post_url'], 'https://www.instagram.com/reel/ABC123/')
        fetch_permalink.assert_called_once()
        upload_reel.assert_not_called()

    def test_instagram_container_error_includes_meta_status_and_video_url(self):
        status_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {
                'status_code': 'ERROR',
                'status': 'The video file you selected is in a format that we do not support.',
            },
        })()

        from app.services.social.facebook_service import FacebookPublishError, _wait_for_instagram_container

        connection = type('Connection', (), {'access_token': 'page-token'})()
        with patch('facebook_service.requests.get', return_value=status_response):
            with self.assertRaises(FacebookPublishError) as error:
                _wait_for_instagram_container(
                    connection,
                    'container-id',
                    'https://example.com/api/generation/preview/test.mp4',
                    attempts=1,
                    delay_seconds=0,
                )

        message = str(error.exception)
        self.assertIn('format that we do not support', message)
        self.assertIn('https://example.com/api/generation/preview/test.mp4', message)

    def test_instagram_publish_uses_media_permalink_from_meta(self):
        account_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {
                'instagram_business_account': {
                    'id': 'ig-user-id',
                    'username': 'easternfarmsllc',
                },
            },
        })()
        create_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'id': 'creation-id'},
        })()
        status_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'status_code': 'FINISHED'},
        })()
        publish_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'id': 'media-id'},
        })()
        permalink_response = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'permalink': 'https://www.instagram.com/reel/ABC123/'},
        })()

        from app.services.social.facebook_service import upload_instagram_reel

        connection = type('Connection', (), {
            'access_token': 'page-token',
            'external_account_id': 'page-id',
            'is_connected': lambda self: True,
        })()
        with patch('facebook_service.requests.get', side_effect=[
            account_response,
            status_response,
            permalink_response,
        ]), patch('facebook_service.requests.post', side_effect=[
            create_response,
            publish_response,
        ]):
            result = upload_instagram_reel(
                connection,
                'https://example.com/api/generation/preview/test.mp4',
                'Test caption',
            )

        self.assertEqual(result['media_id'], 'media-id')
        self.assertEqual(result['url'], 'https://www.instagram.com/reel/ABC123/')

    def test_social_hashtags_falls_back_without_ollama(self):
        with patch.dict(os.environ, {'OLLAMA_BASE_URL': ''}):
            response = self.client.post('/api/social/hashtags', json={
                'title': 'India wholesale prices',
                'country': 'India',
                'shipment_by': 'Air',
                'products': ['Tomato', 'Onion'],
                'count': 15,
            })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['source'], 'fallback')
        self.assertEqual(data['hashtags'][0], '#wholesaleprices2025')
        self.assertIn('#air', data['dynamic_hashtags'])
        self.assertEqual(data['product_hashtags'], ['#tomato', '#onion'])
        self.assertIn('#tomato', data['hashtags'])
        self.assertIn('#india', data['hashtags'])

    def test_social_hashtags_uses_ollama_when_available(self):
        response_payload = type('FakeResponse', (), {
            'ok': True,
            'json': lambda self: {'response': '["#tomato", "#dubaiimporters", "#easternfarmsllc", "#freshproduceuae"]'},
        })()

        with patch.dict(os.environ, {
            'OLLAMA_BASE_URL': 'http://localhost:11434',
            'HASHTAG_OLLAMA_MODEL': 'llama3.2',
        }), patch('app.routes.social_routes.requests.post', return_value=response_payload):
            response = self.client.post('/api/social/hashtags', json={
                'title': 'India wholesale prices',
                'country': 'India',
                'shipment_by': 'Air',
                'products': ['Tomato'],
                'count': 15,
            })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['source'], 'ollama')
        self.assertEqual(data['hashtags'][:3], ['#wholesaleprices2025', '#freshvegetablesdubai', '#import'])
        self.assertIn('#india', data['dynamic_hashtags'])
        self.assertIn('#air', data['dynamic_hashtags'])
        self.assertEqual(data['product_hashtags'], ['#tomato'])
        self.assertIn('#tomato', data['generated_hashtags'])
        self.assertIn('#freshproduceuae', data['ai_hashtags'])
        self.assertNotIn('#dubaiimporters', data['ai_hashtags'])

    def test_linkedin_status_reports_missing_configuration(self):
        with patch.dict(os.environ, {
            'LINKEDIN_CLIENT_ID': '',
            'LINKEDIN_CLIENT_SECRET': '',
        }):
            response = self.client.get('/api/social/linkedin/page/status')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertFalse(data['configured'])
        self.assertFalse(data['connected'])
        self.assertEqual(data['publishing_target'], 'page')

    def test_linkedin_connect_url_requires_oauth_configuration(self):
        with patch.dict(os.environ, {
            'LINKEDIN_CLIENT_ID': '',
            'LINKEDIN_CLIENT_SECRET': '',
        }):
            response = self.client.get('/api/social/linkedin/personal/connect-url')

        self.assertEqual(response.status_code, 400)
        self.assertIn('LINKEDIN_CLIENT_ID', response.get_json()['message'])

    def test_linkedin_personal_connect_url_uses_member_social_scope(self):
        with patch.dict(os.environ, {
            'LINKEDIN_CLIENT_ID': 'test-client-id',
            'LINKEDIN_CLIENT_SECRET': 'test-secret',
            'LINKEDIN_REDIRECT_URI': 'http://localhost:5001/api/social/linkedin/callback',
            'LINKEDIN_PERSONAL_SCOPES': 'openid profile w_member_social',
            'LINKEDIN_PAGE_SCOPES': 'openid profile rw_organization_admin w_organization_social',
            'LINKEDIN_PROMPT': 'login',
        }):
            response = self.client.get('/api/social/linkedin/personal/connect-url')

        self.assertEqual(response.status_code, 200)
        auth_url = response.get_json()['data']['auth_url']
        self.assertIn('client_id=test-client-id', auth_url)
        self.assertIn('w_member_social', auth_url)
        self.assertNotIn('w_organization_social', auth_url)
        self.assertIn('state=1%3Apersonal%3A', auth_url)
        self.assertIn('prompt=login', auth_url)

    def test_linkedin_page_connect_url_uses_organization_social_scope(self):
        with patch.dict(os.environ, {
            'LINKEDIN_CLIENT_ID': 'test-client-id',
            'LINKEDIN_CLIENT_SECRET': 'test-secret',
            'LINKEDIN_REDIRECT_URI': 'http://localhost:5001/api/social/linkedin/callback',
            'LINKEDIN_PERSONAL_SCOPES': 'openid profile w_member_social',
            'LINKEDIN_PAGE_SCOPES': 'openid profile rw_organization_admin w_organization_social',
            'LINKEDIN_PROMPT': 'login',
        }):
            response = self.client.get('/api/social/linkedin/page/connect-url')

        self.assertEqual(response.status_code, 200)
        auth_url = response.get_json()['data']['auth_url']
        self.assertIn('client_id=test-client-id', auth_url)
        self.assertIn('rw_organization_admin', auth_url)
        self.assertIn('w_organization_social', auth_url)
        self.assertNotIn('w_member_social', auth_url)
        self.assertIn('state=1%3Apage%3A', auth_url)
        self.assertIn('prompt=login', auth_url)

    def test_linkedin_publish_requires_connected_account(self):
        output_path = Path('uploads/generated/videos/unit_test_linkedin.mp4')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b'fake mp4')
        self.addCleanup(lambda: output_path.unlink(missing_ok=True))

        with self.app.app_context():
            db.session.add(GenerationHistory(
                company_id=1,
                filename=output_path.name,
                product_count=1,
                file_path=str(output_path),
                status='success',
            ))
            db.session.commit()

        response = self.client.post('/api/social/linkedin/personal/publish', json={
            'filename': output_path.name,
            'title': 'Unit Test Video',
            'description': 'Unit test description',
            'visibility': 'PUBLIC',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('not connected', response.get_json()['message'])

    def test_all_pages_load(self):
        for path in ['/', '/import', '/products', '/generate']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, f'Failed for {path}')

        self.assertEqual(self.client.get('/import-pdf').status_code, 404)

    def test_csv_template(self):
        response = self.client.get('/api/import/template')
        self.assertEqual(response.status_code, 200)
        self.assertIn('S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED', response.get_json()['template'])

    def test_sample_csv_download(self):
        response = self.client.get('/api/import/sample')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        self.assertIn(b'Wheat Flour', response.data)
        self.assertIn(b'Black Pepper', response.data)


if __name__ == '__main__':
    unittest.main()
