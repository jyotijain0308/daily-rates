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
        self.previous_search_category = config.PRODUCT_IMAGE_SEARCH_CATEGORY
        self.previous_max_width = config.PRODUCT_IMAGE_MAX_WIDTH
        self.previous_max_height = config.PRODUCT_IMAGE_MAX_HEIGHT
        self.previous_jpeg_quality = config.PRODUCT_IMAGE_JPEG_QUALITY
        self.tmpdir = tempfile.TemporaryDirectory()

        config.PRODUCT_IMAGE_AUTO_FETCH = True
        config.PRODUCT_IMAGES_DIR = "assets/products"
        config.PRODUCT_IMAGE_SEARCH_CATEGORY = "agro product"
        config.PRODUCT_IMAGE_MAX_WIDTH = 1200
        config.PRODUCT_IMAGE_MAX_HEIGHT = 800
        config.PRODUCT_IMAGE_JPEG_QUALITY = 85
        self.service = ProductImageService()
        self.service.assets_root = Path(self.tmpdir.name)

    def tearDown(self):
        config.PRODUCT_IMAGE_AUTO_FETCH = self.previous_auto_fetch
        config.PRODUCT_IMAGES_DIR = self.previous_product_dir
        config.PRODUCT_IMAGE_SEARCH_CATEGORY = self.previous_search_category
        config.PRODUCT_IMAGE_MAX_WIDTH = self.previous_max_width
        config.PRODUCT_IMAGE_MAX_HEIGHT = self.previous_max_height
        config.PRODUCT_IMAGE_JPEG_QUALITY = self.previous_jpeg_quality
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

        with patch("product_image_service.requests.get", side_effect=[search_response, image_response]) as mock_get:
            result = self.service.get_product_image_path("Unit Test Fetched Product", "India")

        self.assertEqual(result, "assets/products/unit_test_fetched_product.jpg")
        self.assertEqual(
            mock_get.call_args_list[0].kwargs["params"]["query"],
            "Unit Test Fetched Product India agro product",
        )
        cached_file = Path(self.tmpdir.name) / result
        self.assertTrue(cached_file.exists())

    def test_downsizes_fetched_image_before_caching(self):
        config.PRODUCT_IMAGE_MAX_WIDTH = 100
        config.PRODUCT_IMAGE_MAX_HEIGHT = 80

        search_response = Mock()
        search_response.json.return_value = {
            "photos": [{"src": {"large": "https://images.pexels.com/photos/large.jpg"}}]
        }
        search_response.raise_for_status.return_value = None

        image_response = Mock()
        image_bytes = BytesIO()
        Image.new("RGB", (800, 600), "white").save(image_bytes, format="JPEG")
        image_response.content = image_bytes.getvalue()
        image_response.raise_for_status.return_value = None

        with patch("product_image_service.requests.get", side_effect=[search_response, image_response]):
            result = self.service.get_product_image_path("Large Fetched Product", "India")

        with Image.open(Path(self.tmpdir.name) / result) as cached_image:
            self.assertLessEqual(cached_image.width, 100)
            self.assertLessEqual(cached_image.height, 80)

    def test_downsizes_uploaded_image_before_caching(self):
        config.PRODUCT_IMAGE_MAX_WIDTH = 100
        config.PRODUCT_IMAGE_MAX_HEIGHT = 80

        image_bytes = BytesIO()
        Image.new("RGB", (800, 600), "green").save(image_bytes, format="PNG")
        image_bytes.seek(0)

        result = self.service.save_product_image("Large Uploaded Product", image_bytes)

        with Image.open(Path(self.tmpdir.name) / result) as cached_image:
            self.assertLessEqual(cached_image.width, 100)
            self.assertLessEqual(cached_image.height, 80)

    def test_builds_search_query_with_optional_country_and_category(self):
        query = self.service._build_search_query("Wheat Flour", "United Arab Emirates")

        self.assertEqual(query, "Wheat Flour United Arab Emirates agro product")


if __name__ == "__main__":
    unittest.main()
