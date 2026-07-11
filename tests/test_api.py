"""End-to-end API tests for PPT Daily Rates System"""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from wsgi import create_app, db
from models import Product, ProductRateHistory
from image_importer import ProductImageOCRImporter
from pdf_importer import ProductPDFTableImporter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import config as generator_config


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

    def test_import_preview_shows_diff_and_save_records_rate_history(self):
        with self.app.app_context():
            db.session.add(Product(
                serial_no=1,
                country_of_origin='India',
                shipment_by='Air',
                product_name='Wheat Flour',
                weight_kg=25,
                packing='Bag',
                price_aed=72.50,
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
        self.assertEqual(updated_row['old_price_aed'], 72.50)
        self.assertEqual(updated_row['new_price_aed'], 96.00)
        self.assertTrue(updated_row['large_change'])

        save_response = self.client.post('/api/import/save', json={'content': csv_content})
        self.assertEqual(save_response.status_code, 200)
        save_data = save_response.get_json()['data']
        self.assertEqual(save_data['created_count'], 1)
        self.assertEqual(save_data['updated_count'], 1)
        self.assertEqual(save_data['skipped_count'], 0)

        with self.app.app_context():
            product = Product.query.filter_by(product_name='Wheat Flour').one()
            self.assertEqual(product.price_aed, 96.00)
            history = ProductRateHistory.query.filter_by(product_id=product.id).one()
            self.assertEqual(history.old_price_aed, 72.50)
            self.assertEqual(history.new_price_aed, 96.00)
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
                price_aed=72.50,
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
        self.assertIn('1,India,Air,Wheat Flour,25.0,Bag,72.5', csv_content)
        self.assertIn('2,Thailand,Sea,Jasmine Rice,50.0,Sack,158.0', csv_content)

    def test_image_import_preview_converts_rows_to_existing_csv_contract(self):
        extracted_rows = [{
            'serial_no': '1',
            'country_of_origin': 'India',
            'shipment_by': 'Air',
            'product_name': 'Wheat Flour',
            'weight_kg': '25',
            'packing': 'Bag',
            'price_aed': '72.50',
        }]

        with patch(
            'app.routes.import_routes.ProductImageOCRImporter.extract_rows_from_upload',
            return_value=(extracted_rows, [], '1 India Air Wheat Flour 25 Bag 72.50'),
        ):
            preview_response = self.client.post(
                '/api/import/preview-image',
                data={'file': (io.BytesIO(b'fake image bytes'), 'products.png')},
                content_type='multipart/form-data',
            )

        self.assertEqual(preview_response.status_code, 200)
        data = preview_response.get_json()
        self.assertEqual(data['preview']['valid_count'], 1)
        self.assertIn('S.No.,Country of origin,Shipment by,Product Name,Weight in kg,Packing,Price in AED', data['content'])

        save_response = self.client.post('/api/import/save', json={'content': data['content']})
        self.assertEqual(save_response.status_code, 200)

        with self.app.app_context():
            self.assertEqual(Product.query.count(), 1)

    def test_pdf_import_preview_converts_rows_to_existing_csv_contract(self):
        extracted_rows = [{
            'serial_no': '1',
            'country_of_origin': 'India',
            'shipment_by': 'Sea',
            'product_name': 'Onion New Crop (18 Kg)',
            'weight_kg': '1.0',
            'packing': 'Sold by Weight',
            'price_aed': '3.20',
        }]

        with patch(
            'app.routes.import_routes.ProductPDFTableImporter.extract_rows_from_upload',
            return_value=(extracted_rows, []),
        ):
            preview_response = self.client.post(
                '/api/import/preview-pdf',
                data={'file': (io.BytesIO(b'%PDF fake bytes'), 'products.pdf')},
                content_type='multipart/form-data',
            )

        self.assertEqual(preview_response.status_code, 200)
        data = preview_response.get_json()
        self.assertEqual(data['preview']['valid_count'], 1)
        self.assertEqual(data['extracted_count'], 1)
        self.assertIn('Onion New Crop (18 Kg)', data['content'])

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
            'pdf_importer.ProductPDFTableImporter.extract_rows_from_pdf_images',
            return_value=(fallback_rows, []),
        ) as fallback:
            rows, warnings = ProductPDFTableImporter.extract_rows_from_upload(upload)

        self.assertEqual(rows, fallback_rows)
        self.assertEqual(warnings, [])
        fallback.assert_called_once_with(b'%PDF image only')

    def test_pdf_import_uses_openai_before_pdf_fallback_when_configured(self):
        import pdf_importer

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
                'pdf_importer.ProductPDFTableImporter.extract_rows_with_configured_ai',
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
        import pdf_importer

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
                'pdf_importer.ProductPDFTableImporter.render_pdf_pages_to_base64_png',
                return_value=['base64-page'],
            ), patch('pdf_importer.requests.post', return_value=response) as post:
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
            self.assertEqual(product.weight_kg, 50)
            self.assertEqual(product.price_aed, 145.00)

    def test_product_crud(self):
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
            'price_aed': 75.0,
            'shipment_by': 'Sea',
        })
        self.assertEqual(update_response.status_code, 200)
        data = update_response.get_json()['data']
        self.assertEqual(data['price_aed'], 75.0)
        self.assertEqual(data['shipment_by'], 'Sea')

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

            previous_assets_root = product_routes.product_image_service.assets_root
            product_routes.product_image_service.assets_root = Path(tmpdir)
            try:
                response = self.client.post(
                    f'/api/products/{product_id}/image',
                    data={'file': (image_bytes, 'replacement.png')},
                    content_type='multipart/form-data',
                )
            finally:
                product_routes.product_image_service.assets_root = previous_assets_root

            self.assertEqual(response.status_code, 200)
            data = response.get_json()['data']
            self.assertIn('/api/products/image/unit_test_image_upload.jpg', data['image_url'])
            self.assertTrue((Path(tmpdir) / 'assets/products/unit_test_image_upload.jpg').exists())

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

            previous_assets_root = product_routes.product_image_service.assets_root
            product_routes.product_image_service.assets_root = Path(tmpdir)
            output_path = Path(tmpdir) / 'assets/products/pexels_fetch_product.jpg'
            output_path.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), "blue").save(output_path, format="JPEG")

            try:
                with patch.object(
                    product_routes.product_image_service,
                    'fetch_product_image',
                    return_value='assets/products/pexels_fetch_product.jpg',
                ):
                    response = self.client.post(f'/api/products/{product_id}/image/pexels')
            finally:
                product_routes.product_image_service.assets_root = previous_assets_root

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

            previous_assets_root = product_routes.product_image_service.assets_root
            product_routes.product_image_service.assets_root = Path(tmpdir)
            output_path = Path(tmpdir) / 'assets/products/pexels_select_product.jpg'
            output_path.parent.mkdir(parents=True)
            Image.new("RGB", (8, 8), "blue").save(output_path, format="JPEG")

            try:
                with patch.object(
                    product_routes.product_image_service,
                    'save_product_image_from_url',
                    return_value='assets/products/pexels_select_product.jpg',
                ):
                    response = self.client.post(
                        f'/api/products/{product_id}/image/pexels/select',
                        json={'image_url': 'https://images.pexels.com/photos/product.jpg'},
                    )
            finally:
                product_routes.product_image_service.assets_root = previous_assets_root

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
        self.assertIn('India', data['countries'])
        self.assertIn('Air', data['shipments'])
        self.assertEqual(data['currency'], 'AED')

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

        response = self.client.post('/api/generation/generate', json={
            'country': 'India',
            'shipment_by': 'Air',
            'format': 'ppt',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(os.path.exists(data['data']['filepath']))
        self.assertEqual(data['data']['country_count'], 1)
        self.assertEqual(len(data['data']['files']), 1)
        self.assertEqual(data['data']['files'][0]['country'], 'India')
        self.assertEqual(data['data']['files'][0]['shipment_by'], 'Air')
        self.assertEqual(data['data']['shipment_by'], 'Air')
        self.assertTrue(data['data']['filename'].endswith('.mp4'))
        self.assertIn('india_air_products_price_list', data['data']['filename'])

        download_response = self.client.get(
            f"/api/generation/download/{data['data']['filename']}"
        )
        self.assertEqual(download_response.status_code, 200)

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

        response = self.client.post('/api/generation/generate', json={
            'country': 'India',
            'shipment_by': 'Air',
            'format': 'mp4',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertTrue(data['filename'].endswith('.mp4'))
        self.assertTrue(os.path.exists(data['filepath']))

    def test_mp4_preview_serves_video_inline(self):
        os.makedirs('output', exist_ok=True)
        filename = 'unit_test_preview.mp4'
        path = Path('output') / filename
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

    def test_generation_status(self):
        response = self.client.get('/api/generation/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertIn('total_products', data)
        self.assertIn('total_generations', data)
        self.assertIn('shipments_by_country', data)

    def test_all_pages_load(self):
        for path in ['/', '/import', '/import-pdf', '/products', '/generate']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, f'Failed for {path}')

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
