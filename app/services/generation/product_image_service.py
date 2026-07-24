"""Product image lookup and Pexels-backed cache."""
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import requests
from PIL import Image

from app.services.generation import config
from app.services.storage_service import resolve_asset_file

logger = logging.getLogger(__name__)


class ProductImageService:
    """Resolve product images locally, then fetch/cache from Pexels when missing."""

    IMAGE_EXTENSIONS = ("png", "jpg", "jpeg")

    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[3]
        self.uploads_dir = self.project_root / getattr(
            config,
            "PRODUCT_IMAGE_UPLOADS_DIR",
            "uploads/assets/products",
        )

    def get_product_image_path(
        self,
        product_name: str,
        country_of_origin: Optional[str] = None,
        fetch_if_missing: bool = True,
    ) -> Optional[str]:
        """Return a generator-compatible image path for a product."""
        slug = self.slugify(product_name)
        if not slug:
            return None

        local_path = self._find_local_image(slug)
        if local_path:
            return local_path

        if not fetch_if_missing:
            return None

        if not self._can_fetch():
            return None

        return self._fetch_from_pexels(product_name, slug, country_of_origin)

    @staticmethod
    def slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    def _find_local_image(self, slug: str) -> Optional[str]:
        for extension in self.IMAGE_EXTENSIONS:
            candidate = f"{self._upload_relative_dir()}/{slug}.{extension}"
            if self._resolve_asset(candidate):
                return candidate
        for extension in self.IMAGE_EXTENSIONS:
            candidate = f"{config.PRODUCT_IMAGES_DIR}/{slug}.{extension}"
            if self._resolve_asset(candidate):
                return candidate
        return None

    def _resolve_asset(self, image_path: str) -> Optional[Path]:
        return resolve_asset_file(image_path, extra_dirs=[self.uploads_dir])

    def _can_fetch(self) -> bool:
        return (
            getattr(config, "PRODUCT_IMAGE_AUTO_FETCH", False)
            and self._can_use_pexels()
        )

    def _can_use_pexels(self) -> bool:
        return (
            getattr(config, "PRODUCT_IMAGE_PROVIDER", "") == "pexels"
            and bool(getattr(config, "PEXELS_API_KEY", ""))
        )

    def _build_search_query(
        self,
        product_name: str,
        country_of_origin: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Build a search query specific enough for agro product imagery."""
        if description and description.strip():
            query_parts = [description]
        else:
            query_parts = [product_name]
            if country_of_origin:
                query_parts.append(country_of_origin)

        search_category = getattr(config, "PRODUCT_IMAGE_SEARCH_CATEGORY", "")
        if search_category:
            query_parts.append(search_category)

        return " ".join(part.strip() for part in query_parts if part and part.strip())

    def _fetch_from_pexels(
        self,
        product_name: str,
        slug: str,
        country_of_origin: Optional[str] = None,
    ) -> Optional[str]:
        search_query = self._build_search_query(product_name, country_of_origin)
        try:
            response = requests.get(
                config.PEXELS_API_URL,
                headers={"Authorization": config.PEXELS_API_KEY},
                params={
                    "query": search_query,
                    "per_page": 1,
                    "orientation": "landscape",
                },
                timeout=config.PRODUCT_IMAGE_FETCH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            photos = response.json().get("photos", [])
            if not photos:
                logger.info("No Pexels image found for product query: %s", search_query)
                return None

            image_url = self._select_image_url(photos[0])
            if not image_url:
                logger.info("Pexels result did not contain an image URL for query: %s", search_query)
                return None

            return self._download_image(image_url, slug)
        except Exception as exc:
            logger.warning("Could not fetch Pexels image for query %s: %s", search_query, exc)
            return None

    def search_product_images(
        self,
        product_name: str,
        country_of_origin: Optional[str] = None,
        description: Optional[str] = None,
        page: int = 1,
        per_page: int = 5,
    ) -> List[dict]:
        """Return Pexels image choices for a product without downloading them."""
        if not self._can_use_pexels():
            logger.info("Pexels image search is not configured")
            return []

        search_query = self._build_search_query(product_name, country_of_origin, description)
        try:
            page = max(1, int(page or 1))
        except (TypeError, ValueError):
            page = 1
        try:
            per_page = min(5, max(1, int(per_page or 5)))
        except (TypeError, ValueError):
            per_page = 5

        try:
            response = requests.get(
                config.PEXELS_API_URL,
                headers={"Authorization": config.PEXELS_API_KEY},
                params={
                    "query": search_query,
                    "per_page": per_page,
                    "page": page,
                    "orientation": "landscape",
                },
                timeout=config.PRODUCT_IMAGE_FETCH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            photos = response.json().get("photos", [])
        except Exception as exc:
            logger.warning("Could not search Pexels images for query %s: %s", search_query, exc)
            return []

        candidates = []
        for photo in photos:
            image_url = self._select_image_url(photo)
            if not image_url:
                continue
            sources = photo.get("src", {})
            candidates.append({
                "image_url": image_url,
                "thumb_url": sources.get("tiny") or sources.get("small") or image_url,
                "alt": photo.get("alt") or product_name,
                "photographer": photo.get("photographer") or "",
            })

        return candidates

    def _select_image_url(self, photo: dict) -> Optional[str]:
        sources = photo.get("src", {})
        for size in ("medium", "large", "original"):
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

            relative_path = f"{self._upload_relative_dir()}/{slug}.jpg"
            output_path = self.project_root / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with Image.open(BytesIO(response.content)) as downloaded_image:
                self._save_sized_jpeg(downloaded_image, output_path)

            logger.info("Cached Pexels product image: %s", output_path)
            return relative_path
        except Exception as exc:
            logger.warning("Could not download Pexels image %s: %s", image_url, exc)
            return None

    def fetch_product_image(self, product_name: str, country_of_origin: Optional[str] = None) -> Optional[str]:
        """Fetch and cache a product image from the configured provider."""
        slug = self.slugify(product_name)
        if not slug:
            return None

        if not self._can_use_pexels():
            logger.info("Product image fetch is not configured")
            return None

        return self._fetch_from_pexels(product_name, slug, country_of_origin)

    def save_product_image_from_url(self, product_name: str, image_url: str) -> Optional[str]:
        """Download and cache a selected Pexels image for a product."""
        slug = self.slugify(product_name)
        if not slug:
            return None

        if not image_url.startswith("https://images.pexels.com/"):
            logger.warning("Rejected non-Pexels image URL: %s", image_url)
            return None

        return self._download_image(image_url, slug)

    def _save_sized_jpeg(self, image: Image.Image, output_path: Path) -> None:
        """Resize to configured bounds and save as a compressed JPEG."""
        max_size = (
            getattr(config, "PRODUCT_IMAGE_MAX_WIDTH", 1200),
            getattr(config, "PRODUCT_IMAGE_MAX_HEIGHT", 800),
        )
        resized = image.convert("RGB")
        resized.thumbnail(max_size, Image.Resampling.LANCZOS)
        resized.save(
            output_path,
            format="JPEG",
            quality=getattr(config, "PRODUCT_IMAGE_JPEG_QUALITY", 85),
            optimize=True,
        )

    def save_product_image(self, product_name: str, image_stream) -> Optional[str]:
        """Save a manually uploaded product image into the product image cache."""
        slug = self.slugify(product_name)
        if not slug:
            return None

        output_dir = self.uploads_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        for extension in self.IMAGE_EXTENSIONS:
            cached_file = output_dir / f"{slug}.{extension}"
            if cached_file.exists():
                cached_file.unlink()

        relative_path = f"{self._upload_relative_dir()}/{slug}.jpg"
        output_path = self.project_root / relative_path

        with Image.open(image_stream) as uploaded_image:
            self._save_sized_jpeg(uploaded_image, output_path)

        logger.info("Updated product image: %s", output_path)
        return relative_path

    def _upload_relative_dir(self) -> str:
        return str(self.uploads_dir.relative_to(self.project_root))
