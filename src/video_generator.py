"""MP4 generator for country-specific product price lists."""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from config import (
    COLORS, COMPANY_ADDRESS, COMPANY_LOGO_IMAGE, COMPANY_NAME, COMPANY_WEBSITE,
    COUNTRY_LOGO_IMAGES, PRODUCT_IMAGES_DIR, CURRENCY, RATE_DISPLAY_FORMAT, UAE_LOGO_IMAGE
)

logger = logging.getLogger(__name__)


class MP4Generator:
    """Generate a simple MP4 from country/product price-list frames."""

    WIDTH = 1280
    HEIGHT = 720
    FPS = 1
    SECONDS_PER_SLIDE = 3

    def __init__(self):
        self.frames = []
        self.font_regular = self._font(34)
        self.font_small = self._font(24)
        self.font_heading = self._font(46)
        self.font_title = self._font(62)
        self.font_price = self._font(58)

    def _font(self, size: int):
        for candidate in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]:
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _rgb(self, key: str):
        color = COLORS[key]
        return color[0], color[1], color[2]

    def _resolve_asset(self, image_path: Optional[str]) -> Optional[Path]:
        if not image_path:
            return None

        path = Path(image_path)
        if path.is_absolute() and path.exists():
            return path

        candidates = [
            Path.cwd() / image_path,
            Path.cwd() / "src" / image_path,
            Path(__file__).resolve().parent / image_path,
            Path(__file__).resolve().parent.parent / image_path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _draw_centered_text(self, draw, text, font, y, fill, max_width=None):
        lines = self._wrap_text(draw, text, font, max_width or self.WIDTH - 120)
        line_height = font.size + 8 if hasattr(font, "size") else 32
        for idx, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (self.WIDTH - (bbox[2] - bbox[0])) / 2
            draw.text((x, y + idx * line_height), line, font=font, fill=fill)
        return y + len(lines) * line_height

    def _wrap_text(self, draw, text, font, max_width):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _paste_actual_image_or_text(self, image, draw, image_path, fallback_text, center_x, top, text_fill):
        asset = self._resolve_asset(image_path)
        if asset:
            try:
                logo = Image.open(asset).convert("RGBA")
                left = int(center_x - logo.width / 2)
                image.alpha_composite(logo, (left, int(top)))
                return top + logo.height
            except Exception as exc:
                logger.warning("Could not add image %s: %s", asset, exc)

        bbox = draw.textbbox((0, 0), fallback_text, font=self.font_small)
        draw.text((center_x - (bbox[2] - bbox[0]) / 2, top), fallback_text, font=self.font_small, fill=text_fill)
        return top + 34

    def _paste_fit_image_centered_or_text(self, image, draw, image_path, fallback_text, box, text_fill):
        left, top, width, height = box
        asset = self._resolve_asset(image_path)
        if asset:
            try:
                source = Image.open(asset).convert("RGBA")
                scale = min(width / source.width, height / source.height)
                resized = source.resize((int(source.width * scale), int(source.height * scale)))
                x = int(left + (width - resized.width) / 2)
                y = int(top + (height - resized.height) / 2)
                image.alpha_composite(resized, (x, y))
                return
            except Exception as exc:
                logger.warning("Could not add image %s: %s", asset, exc)

        self._draw_centered_text(draw, fallback_text, self.font_small, top + height / 2 - 15, text_fill, width)

    def _blank(self, background="background"):
        return Image.new("RGBA", (self.WIDTH, self.HEIGHT), self._rgb(background) + (255,))

    def _product_image_path(self, product_name: str) -> Optional[str]:
        slug = re.sub(r"[^a-z0-9]+", "_", product_name.lower()).strip("_")
        for extension in ("png", "jpg", "jpeg"):
            candidate = f"{PRODUCT_IMAGES_DIR}/{slug}.{extension}"
            if self._resolve_asset(candidate):
                return candidate
        return None

    def _paste_fit_image_or_text(self, image, draw, image_path, fallback_text, box, text_fill):
        left, top, width, height = box
        asset = self._resolve_asset(image_path)
        if asset:
            try:
                source = Image.open(asset).convert("RGBA")
                scale = min(width / source.width, height / source.height)
                resized = source.resize((int(source.width * scale), int(source.height * scale)))
                x = int(left + (width - resized.width) / 2)
                y = int(top + (height - resized.height) / 2)
                image.alpha_composite(resized, (x, y))
                return
            except Exception as exc:
                logger.warning("Could not add image %s: %s", asset, exc)

        self._draw_centered_text(draw, fallback_text, self.font_small, top + height / 2 - 15, text_fill, width)

    def _append_slide(self, frame):
        rgb_frame = frame.convert("RGB")
        for _ in range(self.SECONDS_PER_SLIDE * self.FPS):
            self.frames.append(np.asarray(rgb_frame))

    def add_country_title_slide(self, country_name: str, current_date: datetime = None):
        if current_date is None:
            current_date = datetime.now()

        frame = self._blank("background")
        draw = ImageDraw.Draw(frame)
        self._paste_fit_image_centered_or_text(
            frame, draw, COMPANY_LOGO_IMAGE, COMPANY_NAME,
            (64, 43, 1152, 91), self._rgb("primary")
        )
        self._paste_fit_image_centered_or_text(
            frame, draw, COUNTRY_LOGO_IMAGES.get(country_name), country_name,
            (64, 187, 1152, 211), self._rgb("primary")
        )
        self._draw_centered_text(
            draw, f"{country_name} Products Price List",
            self.font_title, 418, self._rgb("primary"), self.WIDTH - 140
        )
        self._draw_centered_text(
            draw, current_date.strftime("%B %d, %Y"),
            self.font_heading, 562, self._rgb("text")
        )
        self._append_slide(frame)

    def add_product_slide(self, product, slide_number=None):
        frame = self._blank("background")
        draw = ImageDraw.Draw(frame)

        self._paste_actual_image_or_text(
            frame, draw, COMPANY_LOGO_IMAGE, COMPANY_NAME,
            120, 32, self._rgb("primary")
        )
        self._paste_fit_image_or_text(
            frame, draw, COUNTRY_LOGO_IMAGES.get(product.country_of_origin), product.country_of_origin,
            (1110, 24, 115, 75), self._rgb("primary")
        )

        self._draw_centered_text(
            draw, f"{product.product_name} {product.weight_kg:g}kg {product.packing}",
            self.font_title, 120, self._rgb("primary"), self.WIDTH - 140
        )
        self._paste_fit_image_or_text(
            frame, draw, self._product_image_path(product.product_name), product.product_name,
            (190, 235, 900, 230), self._rgb("primary")
        )

        band = (150, 525, self.WIDTH - 150, 625)
        draw.rectangle(band, fill=self._rgb("primary"))
        self._draw_centered_text(
            draw, f"Price: {RATE_DISPLAY_FORMAT.format(product.price_aed)}",
            self.font_price, 545, self._rgb("light_text"), self.WIDTH - 220
        )
        self._append_slide(frame)

    def add_thank_you_slide(self, country_name: str, exchange_rate: Optional[float] = None,
                            currency_code: Optional[str] = None):
        frame = self._blank("background")
        draw = ImageDraw.Draw(frame)

        self._paste_fit_image_centered_or_text(
            frame, draw, COMPANY_LOGO_IMAGE, COMPANY_NAME,
            (64, 43, 1152, 91), self._rgb("primary")
        )
        self._paste_fit_image_or_text(
            frame, draw, COUNTRY_LOGO_IMAGES.get(country_name), country_name,
            (70, 192, 243, 120), self._rgb("primary")
        )
        self._paste_fit_image_or_text(
            frame, draw, UAE_LOGO_IMAGE, "UAE",
            (967, 192, 243, 120), self._rgb("primary")
        )

        rate_text = "Exchange rate not available"
        if exchange_rate and currency_code:
            rate_text = f"1 {CURRENCY} = {exchange_rate:.2f} {currency_code}"
        card = (403, 216, 877, 287)
        draw.rectangle(card, fill=(255, 244, 229), outline=self._rgb("accent"), width=3)
        self._draw_centered_text(draw, rate_text, self.font_heading, 229, self._rgb("primary"), 450)

        address_parts = [part.strip() for part in COMPANY_ADDRESS.split(",") if part.strip()]
        address_line_1 = ", ".join(address_parts[:3]) if address_parts else COMPANY_ADDRESS
        address_line_2 = ", ".join(address_parts[3:]) if len(address_parts) > 3 else ""

        self._draw_centered_text(draw, COMPANY_NAME, self.font_title, 413, self._rgb("primary"), self.WIDTH - 120)
        self._draw_centered_text(draw, address_line_1, self.font_regular, 500, self._rgb("text"), self.WIDTH - 120)
        if address_line_2:
            self._draw_centered_text(draw, address_line_2, self.font_regular, 548, self._rgb("text"), self.WIDTH - 120)
            website_y = 596
        else:
            website_y = 548
        self._draw_centered_text(draw, COMPANY_WEBSITE, self.font_regular, website_y, self._rgb("accent"), self.WIDTH - 120)
        self._append_slide(frame)

    def save(self, file_path: str):
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with imageio.get_writer(file_path, fps=self.FPS, codec="libx264", quality=8) as writer:
            for frame in self.frames:
                writer.append_data(frame)
        logger.info("MP4 saved to %s", file_path)
