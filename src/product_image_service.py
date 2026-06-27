"""Product image lookup and Pexels-backed cache."""
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

import config

logger = logging.getLogger(__name__)


class ProductImageService:
    """Resolve product images locally, then fetch/cache from Pexels when missing."""

    IMAGE_EXTENSIONS = ("png", "jpg", "jpeg")

    def __init__(self):
        self.assets_root = Path(__file__).resolve().parent

    def get_product_image_path(self, product_name: str) -> Optional[str]:
        """Return a generator-compatible image path for a product."""
        slug = self.slugify(product_name)
        if not slug:
            return None

        local_path = self._find_local_image(slug)
        if local_path:
            return local_path

        if not self._can_fetch():
            return None

        return self._fetch_from_pexels(product_name, slug)

    @staticmethod
    def slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    def _find_local_image(self, slug: str) -> Optional[str]:
        for extension in self.IMAGE_EXTENSIONS:
            candidate = f"{config.PRODUCT_IMAGES_DIR}/{slug}.{extension}"
            if self._resolve_asset(candidate):
                return candidate
        return None

    def _resolve_asset(self, image_path: str) -> Optional[Path]:
        path = Path(image_path)
        if path.is_absolute() and path.exists():
            return path

        candidates = [
            Path.cwd() / image_path,
            Path.cwd() / "src" / image_path,
            self.assets_root / image_path,
            self.assets_root.parent / image_path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _can_fetch(self) -> bool:
        return (
            getattr(config, "PRODUCT_IMAGE_AUTO_FETCH", False)
            and getattr(config, "PRODUCT_IMAGE_PROVIDER", "") == "pexels"
            and bool(getattr(config, "PEXELS_API_KEY", ""))
        )

    def _fetch_from_pexels(self, product_name: str, slug: str) -> Optional[str]:
        try:
            response = requests.get(
                config.PEXELS_API_URL,
                headers={"Authorization": config.PEXELS_API_KEY},
                params={
                    "query": product_name,
                    "per_page": 1,
                    "orientation": "landscape",
                },
                timeout=config.PRODUCT_IMAGE_FETCH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            photos = response.json().get("photos", [])
            if not photos:
                logger.info("No Pexels image found for product: %s", product_name)
                return None

            image_url = self._select_image_url(photos[0])
            if not image_url:
                logger.info("Pexels result did not contain an image URL for: %s", product_name)
                return None

            return self._download_image(image_url, slug)
        except Exception as exc:
            logger.warning("Could not fetch Pexels image for %s: %s", product_name, exc)
            return None

    def _select_image_url(self, photo: dict) -> Optional[str]:
        sources = photo.get("src", {})
        for size in ("large", "medium", "original"):
            if sources.get(size):
                return sources[size]
        return None

    def _download_image(self, image_url: str, slug: str) -> Optional[str]:
        try:
            response = requests.get(
                image_url,
                timeout=config.PRODUCT_IMAGE_FETCH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            relative_path = f"{config.PRODUCT_IMAGES_DIR}/{slug}.jpg"
            output_path = self.assets_root / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with Image.open(BytesIO(response.content)) as downloaded_image:
                downloaded_image.convert("RGB").save(output_path, format="JPEG", quality=90)

            logger.info("Cached Pexels product image: %s", output_path)
            return relative_path
        except Exception as exc:
            logger.warning("Could not download Pexels image %s: %s", image_url, exc)
            return None
