import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import config
from product_image_service import ProductImageService


class TestProductImageService(unittest.TestCase):
    def setUp(self):
        self.previous_auto_fetch = config.PRODUCT_IMAGE_AUTO_FETCH
        self.previous_product_dir = config.PRODUCT_IMAGES_DIR
        self.tmpdir = tempfile.TemporaryDirectory()

        config.PRODUCT_IMAGE_AUTO_FETCH = True
        config.PRODUCT_IMAGES_DIR = "assets/products"
        self.service = ProductImageService()
        self.service.assets_root = Path(self.tmpdir.name)

    def tearDown(self):
        config.PRODUCT_IMAGE_AUTO_FETCH = self.previous_auto_fetch
        config.PRODUCT_IMAGES_DIR = self.previous_product_dir
        self.tmpdir.cleanup()

    def test_uses_cached_local_image_first(self):
        image_path = Path(self.tmpdir.name) / "assets/products/unit_test_cached_product.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"existing")

        with patch("product_image_service.requests.get") as mock_get:
            result = self.service.get_product_image_path("Unit Test Cached Product")

        self.assertEqual(result, "assets/products/unit_test_cached_product.jpg")
        mock_get.assert_not_called()

    def test_fetches_and_caches_pexels_image_when_missing(self):
        search_response = Mock()
        search_response.json.return_value = {
            "photos": [
                {
                    "src": {
                        "large": "https://images.pexels.com/photos/wheat.jpg",
                    }
                }
            ]
        }
        search_response.raise_for_status.return_value = None

        image_response = Mock()
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), "white").save(image_bytes, format="JPEG")
        image_response.content = image_bytes.getvalue()
        image_response.headers = {"content-type": "image/jpeg"}
        image_response.raise_for_status.return_value = None

        with patch("product_image_service.requests.get", side_effect=[search_response, image_response]):
            result = self.service.get_product_image_path("Unit Test Fetched Product")

        self.assertEqual(result, "assets/products/unit_test_fetched_product.jpg")
        cached_file = Path(self.tmpdir.name) / result
        self.assertTrue(cached_file.exists())


if __name__ == "__main__":
    unittest.main()
