"""MP4 generator for country-specific product price lists."""
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.generation.config import (
    COLORS, COMPANY_ADDRESS, COMPANY_LOGO_IMAGE, COMPANY_NAME, COMPANY_WEBSITE,
    COUNTRY_LOGO_IMAGES, CURRENCY, RATE_DISPLAY_FORMAT, UAE_LOGO_IMAGE
)
from app.services.generation.product_image_service import ProductImageService
from app.services.storage_service import resolve_asset_file

logger = logging.getLogger(__name__)


class MP4Generator:
    """Generate a simple MP4 from country/product price-list frames."""

    WIDTH = 1280
    HEIGHT = 720
    FPS = 30
    SECONDS_PER_SLIDE = 3

    def __init__(self, country_logo_images=None, company_settings=None):
        self.slides = []
        self.font_regular = self._font(34)
        self.font_small = self._font(24)
        self.font_heading = self._font(46)
        self.font_title = self._font(62)
        self.font_price = self._font(58)
        self.product_images = ProductImageService()
        self.country_logo_images = country_logo_images or COUNTRY_LOGO_IMAGES
        self.company_settings = company_settings

    @property
    def company_name(self):
        if self.company_settings and self.company_settings.company:
            return self.company_settings.company.name
        return COMPANY_NAME

    @property
    def company_address(self):
        return getattr(self.company_settings, "address", COMPANY_ADDRESS)

    @property
    def company_website(self):
        return getattr(self.company_settings, "website", COMPANY_WEBSITE)

    @property
    def company_logo_image(self):
        return getattr(self.company_settings, "company_logo_image", COMPANY_LOGO_IMAGE)

    @property
    def destination_logo_image(self):
        return getattr(self.company_settings, "destination_logo_image", UAE_LOGO_IMAGE)

    @property
    def currency(self):
        return getattr(self.company_settings, "currency", CURRENCY)

    @property
    def rate_display_format(self):
        return getattr(self.company_settings, "rate_display_format", RATE_DISPLAY_FORMAT)

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
        return resolve_asset_file(image_path)

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

    def _product_image_path(self, product_name: str, country_of_origin: Optional[str] = None) -> Optional[str]:
        return self.product_images.get_product_image_path(
            product_name,
            country_of_origin,
            fetch_if_missing=False,
        )

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
        self.slides.append(frame.convert("RGB"))

    def add_country_title_slide(self, country_name: str, current_date: datetime = None,
                                shipment_by: Optional[str] = None):
        if current_date is None:
            current_date = datetime.now()

        frame = self._blank("background")
        draw = ImageDraw.Draw(frame)
        self._paste_fit_image_centered_or_text(
            frame, draw, self.company_logo_image, self.company_name,
            (64, 43, 1152, 91), self._rgb("primary")
        )
        self._paste_fit_image_centered_or_text(
            frame, draw, self.country_logo_images.get(country_name), country_name,
            (64, 187, 1152, 211), self._rgb("primary")
        )
        self._draw_centered_text(
            draw, f"{country_name} Products Price List",
            self.font_title, 418, self._rgb("primary"), self.WIDTH - 140
        )
        if shipment_by:
            self._draw_centered_text(
                draw, f"Shipment by: {shipment_by}",
                self.font_regular, 512, self._rgb("accent"), self.WIDTH - 180
            )
            date_y = 590
        else:
            date_y = 562
        self._draw_centered_text(
            draw, current_date.strftime("%B %d, %Y"),
            self.font_heading, date_y, self._rgb("text")
        )
        self._append_slide(frame)

    def add_product_slide(self, product, slide_number=None):
        frame = self._blank("background")
        draw = ImageDraw.Draw(frame)

        self._paste_fit_image_or_text(
            frame, draw, self.company_logo_image, self.company_name,
            (48, 24, 190, 75), self._rgb("primary")
        )
        self._paste_fit_image_or_text(
            frame, draw, self.country_logo_images.get(product.country_of_origin), product.country_of_origin,
            (1110, 24, 115, 75), self._rgb("primary")
        )

        self._draw_centered_text(
            draw, product.product_name,
            self.font_title, 120, self._rgb("primary"), self.WIDTH - 140
        )
        self._draw_centered_text(
            draw, f"{product.weight_kg} | {product.packing}",
            self.font_regular, 205, self._rgb("accent"), self.WIDTH - 180
        )
        self._paste_fit_image_or_text(
            frame, draw, self._product_image_path(product.product_name, product.country_of_origin), product.product_name,
            (190, 270, 900, 195), self._rgb("primary")
        )

        band = (150, 525, self.WIDTH - 150, 625)
        draw.rectangle(band, fill=self._rgb("primary"))
        self._draw_centered_text(
            draw, f"Price: {self.rate_display_format.format(product.price_aed)}",
            self.font_price, 545, self._rgb("light_text"), self.WIDTH - 220
        )
        self._append_slide(frame)

    def add_thank_you_slide(self, country_name: str, exchange_rate: Optional[float] = None,
                            currency_code: Optional[str] = None):
        frame = self._blank("background")
        draw = ImageDraw.Draw(frame)

        self._paste_fit_image_centered_or_text(
            frame, draw, self.company_logo_image, self.company_name,
            (64, 43, 1152, 91), self._rgb("primary")
        )
        self._paste_fit_image_or_text(
            frame, draw, self.country_logo_images.get(country_name), country_name,
            (70, 192, 243, 120), self._rgb("primary")
        )
        self._paste_fit_image_or_text(
            frame, draw, self.destination_logo_image, "UAE",
            (967, 192, 243, 120), self._rgb("primary")
        )

        rate_text = "Exchange rate not available"
        if exchange_rate and currency_code:
            rate_text = f"1 {self.currency} = {exchange_rate:.2f} {currency_code}"
        card = (403, 216, 877, 287)
        draw.rectangle(card, fill=(255, 244, 229), outline=self._rgb("accent"), width=3)
        self._draw_centered_text(draw, rate_text, self.font_heading, 229, self._rgb("primary"), 450)

        address_parts = [part.strip() for part in self.company_address.split(",") if part.strip()]
        address_line_1 = ", ".join(address_parts[:3]) if address_parts else self.company_address
        address_line_2 = ", ".join(address_parts[3:]) if len(address_parts) > 3 else ""

        self._draw_centered_text(draw, self.company_name, self.font_title, 413, self._rgb("primary"), self.WIDTH - 120)
        self._draw_centered_text(draw, address_line_1, self.font_regular, 500, self._rgb("text"), self.WIDTH - 120)
        if address_line_2:
            self._draw_centered_text(draw, address_line_2, self.font_regular, 548, self._rgb("text"), self.WIDTH - 120)
            website_y = 596
        else:
            website_y = 548
        self._draw_centered_text(draw, self.company_website, self.font_regular, website_y, self._rgb("accent"), self.WIDTH - 120)
        self._append_slide(frame)

    def save(self, file_path: str, is_cancelled=None, audio_path: Optional[str] = None):
        is_cancelled = is_cancelled or (lambda: False)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_video = temp_file.name
        temp_file.close()

        try:
            with imageio.get_writer(temp_video, fps=self.FPS, codec="libx264", quality=8) as writer:
                for slide in self.slides:
                    frame = np.asarray(slide)
                    for _ in range(self.SECONDS_PER_SLIDE * self.FPS):
                        if is_cancelled():
                            raise RuntimeError("MP4 generation cancelled")
                        writer.append_data(frame)

            self._encode_social_mp4(temp_video, file_path, audio_path, is_cancelled)
        finally:
            Path(temp_video).unlink(missing_ok=True)
        logger.info("MP4 saved to %s", file_path)

    def _encode_social_mp4(
        self,
        video_path: str,
        output_path: str,
        audio_path: Optional[str],
        is_cancelled,
    ):
        audio_file = Path(audio_path) if audio_path else None
        has_audio_file = bool(audio_file and audio_file.exists())
        if audio_path and not has_audio_file:
            logger.warning("Background audio file not found: %s", audio_path)
            shutil.move(video_path, output_path)
            return

        duration_seconds = max(1, len(self.slides) * self.SECONDS_PER_SLIDE)
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-i", video_path,
        ]
        if has_audio_file:
            command.extend([
                "-stream_loop", "-1",
                "-i", str(audio_file),
            ])
            audio_map = "1:a:0"
        else:
            command.extend([
                "-f", "lavfi",
                "-t", str(duration_seconds),
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            ])
            audio_map = "1:a:0"

        command.extend([
            "-t", str(duration_seconds),
            "-map", "0:v:0",
            "-map", audio_map,
            "-c:v", "libx264",
            "-profile:v", "high",
            "-level", "4.0",
            "-pix_fmt", "yuv420p",
            "-r", str(self.FPS),
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "48000",
            "-ac", "2",
            "-movflags", "+faststart",
            "-shortest",
            output_path,
        ])

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while process.poll() is None:
            if is_cancelled():
                process.kill()
                process.communicate()
                raise RuntimeError("MP4 generation cancelled")
        _, stderr = process.communicate()
        if process.returncode != 0:
            logger.warning("Could not finalize social MP4: %s", stderr.decode("utf-8", errors="ignore"))
            shutil.move(video_path, output_path)
