"""End-to-end API tests for PPT Daily Rates System"""
import io
import os
import tempfile
import unittest

from wsgi import create_app, db
from models import Product


class TestPPTDailyRatesAPI(unittest.TestCase):
    """Integration tests covering the full workflow"""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.db_path}',
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
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
        self.assertEqual(preview_response.get_json()['preview']['valid_count'], 2)

        save_response = self.client.post('/api/import/save', json={'content': csv_content})
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(save_response.get_json()['data']['imported_count'], 2)

        with self.app.app_context():
            self.assertEqual(Product.query.count(), 2)

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

    def test_generation_creates_selected_country_ppt(self):
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
            'format': 'ppt',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(os.path.exists(data['data']['filepath']))
        self.assertEqual(data['data']['country_count'], 1)
        self.assertEqual(len(data['data']['files']), 1)
        self.assertEqual(data['data']['files'][0]['country'], 'India')
        self.assertTrue(data['data']['filename'].endswith('.pptx'))

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
            'format': 'mp4',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertTrue(data['filename'].endswith('.mp4'))
        self.assertTrue(os.path.exists(data['filepath']))

    def test_generation_requires_country(self):
        response = self.client.post('/api/generation/generate')
        self.assertEqual(response.status_code, 400)

    def test_generation_status(self):
        response = self.client.get('/api/generation/status')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertIn('total_products', data)
        self.assertIn('total_generations', data)

    def test_all_pages_load(self):
        for path in ['/', '/import', '/products', '/generate']:
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
