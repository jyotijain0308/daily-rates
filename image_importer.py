"""Image table OCR utilities for product imports."""
import csv
import re
from io import StringIO
from statistics import median
from typing import Dict, List, Optional, Tuple

from PIL import Image

from csv_importer import ProductCSVImporter
from src.config import IMAGE_IMPORT_ALLOWED_EXTENSIONS, OCR_TESSERACT_CONFIG


class ImageImportError(Exception):
    """Raised when an uploaded image cannot be processed."""


class OCRUnavailableError(ImageImportError):
    """Raised when OCR dependencies are not installed or configured."""


class ProductImageOCRImporter:
    """Extract product rows from an image of a table."""

    IMAGE_EXTENSIONS = IMAGE_IMPORT_ALLOWED_EXTENSIONS

    @staticmethod
    def extract_rows_from_upload(file_storage) -> Tuple[List[Dict], List[str], str]:
        """Read an uploaded image and return normalized rows, errors, and OCR text."""
        try:
            image = Image.open(file_storage.stream)
            image.load()
        except Exception as exc:
            raise ImageImportError(f"Could not read image file: {exc}") from exc

        return ProductImageOCRImporter.extract_rows_from_image(image)

    @staticmethod
    def extract_rows_from_image(image: Image.Image) -> Tuple[List[Dict], List[str], str]:
        """Extract normalized product rows from a PIL image."""
        try:
            import pytesseract
        except ImportError as exc:
            raise OCRUnavailableError(
                "Image import requires pytesseract. Install it with `pip install -r requirements.txt`."
            ) from exc

        try:
            prepared_image = ProductImageOCRImporter.prepare_image(image)
            data = pytesseract.image_to_data(
                prepared_image,
                config=OCR_TESSERACT_CONFIG,
                output_type=pytesseract.Output.DICT,
            )
            text = ProductImageOCRImporter.ocr_data_to_text(data)
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRUnavailableError(
                "Image import requires the Tesseract OCR binary. Install Tesseract and try again."
            ) from exc
        except Exception as exc:
            raise ImageImportError(f"OCR failed: {exc}") from exc

        positioned_rows, positioned_errors = ProductImageOCRImporter.parse_ocr_data(data)
        text_rows, text_errors = ProductImageOCRImporter.parse_ocr_text(text)
        rows = ProductImageOCRImporter.merge_rows(positioned_rows + text_rows)

        if rows:
            return rows, [], text

        return [], positioned_errors + text_errors, text

    @staticmethod
    def prepare_image(image: Image.Image) -> Image.Image:
        """Prepare an uploaded table screenshot for OCR without changing content."""
        prepared = image.convert("RGB")
        max_width = 1800
        if prepared.width < max_width:
            scale = max_width / prepared.width
            prepared = prepared.resize(
                (max_width, int(prepared.height * scale)),
                Image.Resampling.LANCZOS,
            )
        return prepared

    @staticmethod
    def ocr_data_to_text(data: Dict) -> str:
        """Rebuild plain OCR text from pytesseract image_to_data output."""
        lines = {}
        for index, text in enumerate(data.get("text", [])):
            cleaned = ProductImageOCRImporter.clean_line(text)
            if not cleaned:
                continue
            key = (
                data.get("block_num", [0])[index],
                data.get("par_num", [0])[index],
                data.get("line_num", [0])[index],
            )
            lines.setdefault(key, []).append(cleaned)
        return "\n".join(" ".join(words) for _, words in sorted(lines.items()))

    @staticmethod
    def parse_ocr_data(data: Dict) -> Tuple[List[Dict], List[str]]:
        """Parse OCR rows by expected table column order, ignoring non-row content."""
        words = ProductImageOCRImporter.extract_ocr_words(data)
        if not words:
            return [], ["No readable OCR words were found in the image"]

        word_lines = ProductImageOCRImporter.group_words_by_y(words)
        rows = []
        for line in word_lines:
            parsed = ProductImageOCRImporter.parse_ordered_row(line)
            if parsed:
                rows.append(parsed)

        errors = []
        if not rows:
            errors.append("No product table rows were found in the image")

        return rows, errors

    @staticmethod
    def extract_ocr_words(data: Dict) -> List[Dict]:
        """Extract non-empty OCR words with coordinates from pytesseract data."""
        words = []
        for index, raw_text in enumerate(data.get("text", [])):
            text = ProductImageOCRImporter.clean_line(raw_text)
            if not text:
                continue

            try:
                confidence = float(data.get("conf", ["-1"])[index])
            except (TypeError, ValueError):
                confidence = -1
            if confidence < 0:
                continue

            left = int(data.get("left", [0])[index])
            top = int(data.get("top", [0])[index])
            width = int(data.get("width", [0])[index])
            height = int(data.get("height", [0])[index])
            if width <= 0 or height <= 0:
                continue

            words.append({
                "text": text,
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
                "center_x": left + width / 2,
                "center_y": top + height / 2,
                "height": height,
            })
        return words

    @staticmethod
    def group_words_by_y(words: List[Dict]) -> List[List[Dict]]:
        """Group OCR words into visual rows using their y coordinate."""
        if not words:
            return []

        typical_height = median(word["height"] for word in words)
        threshold = max(8, typical_height * 0.75)
        lines = []

        for word in sorted(words, key=lambda item: item["center_y"]):
            matching_line = None
            for line in lines:
                if abs(ProductImageOCRImporter.line_center_y(line) - word["center_y"]) <= threshold:
                    matching_line = line
                    break
            if matching_line is None:
                lines.append([word])
            else:
                matching_line.append(word)

        return [
            sorted(line, key=lambda item: item["center_x"])
            for line in sorted(lines, key=ProductImageOCRImporter.line_center_y)
        ]

    @staticmethod
    def line_center_y(line: List[Dict]) -> float:
        return sum(word["center_y"] for word in line) / len(line)

    @staticmethod
    def find_table_header_words(lines: List[List[Dict]]) -> List[Dict]:
        """Find the row containing the product table headers."""
        for line in lines:
            normalized = " ".join(word["text"].lower() for word in line)
            if (
                "country" in normalized
                and "origin" in normalized
                and "shipment" in normalized
                and "product" in normalized
                and "packing" in normalized
                and "price" in normalized
            ):
                return line
        return []

    @staticmethod
    def detect_columns(header_words: List[Dict]) -> Optional[List[Dict]]:
        """Detect table column boundaries from header word positions."""
        anchors = {
            "serial_no": ProductImageOCRImporter.find_header_anchor(header_words, ["s.no.", "s.no", "4.9"]),
            "country_of_origin": ProductImageOCRImporter.find_header_anchor(header_words, ["country", "origin"]),
            "shipment_by": ProductImageOCRImporter.find_header_anchor(header_words, ["shipment"]),
            "product_name": ProductImageOCRImporter.find_header_anchor(header_words, ["product"]),
            "weight_kg": ProductImageOCRImporter.find_header_anchor(header_words, ["weight"]),
            "packing": ProductImageOCRImporter.find_header_anchor(header_words, ["packing"]),
            "price_aed": ProductImageOCRImporter.find_header_anchor(header_words, ["price"]),
        }

        if anchors["serial_no"] is None:
            anchors["serial_no"] = min(word["center_x"] for word in header_words)

        required = [
            "country_of_origin",
            "shipment_by",
            "product_name",
            "weight_kg",
            "packing",
            "price_aed",
        ]
        if any(anchors[field] is None for field in required):
            return None

        ordered = [
            ("serial_no", anchors["serial_no"]),
            ("country_of_origin", anchors["country_of_origin"]),
            ("shipment_by", anchors["shipment_by"]),
            ("product_name", anchors["product_name"]),
            ("weight_kg", anchors["weight_kg"]),
            ("packing", anchors["packing"]),
            ("price_aed", anchors["price_aed"]),
        ]
        ordered.sort(key=lambda item: item[1])

        boundaries = []
        for index in range(len(ordered) - 1):
            boundaries.append((ordered[index][1] + ordered[index + 1][1]) / 2)

        columns = []
        for index, (field, center) in enumerate(ordered):
            left = float("-inf") if index == 0 else boundaries[index - 1]
            right = float("inf") if index == len(ordered) - 1 else boundaries[index]
            columns.append({"field": field, "left": left, "right": right, "center": center})
        return columns

    @staticmethod
    def find_header_anchor(header_words: List[Dict], tokens: List[str]) -> Optional[float]:
        matches = [
            word["center_x"]
            for word in header_words
            if any(word["text"].lower().strip("():") == token for token in tokens)
        ]
        if matches:
            return sum(matches) / len(matches)
        return None

    @staticmethod
    def parse_positioned_row(line: List[Dict], columns: List[Dict]) -> Optional[Dict]:
        """Convert one positioned OCR row into normalized product fields."""
        cells = {column["field"]: [] for column in columns}
        for word in line:
            for column in columns:
                if column["left"] <= word["center_x"] < column["right"]:
                    cells[column["field"]].append(word["text"])
                    break

        serial_no = ProductImageOCRImporter.clean_serial_number(" ".join(cells["serial_no"]))
        if not serial_no:
            return None

        product_words = list(cells["product_name"])
        weight_words = list(cells["weight_kg"])
        weight_index = ProductImageOCRImporter.find_last_numeric_token_index(weight_words)
        if weight_index is not None:
            product_words.extend(weight_words[:weight_index])
            weight_kg = ProductImageOCRImporter.clean_number(weight_words[weight_index])
        else:
            weight_kg = ProductImageOCRImporter.clean_number(" ".join(weight_words))

        country_of_origin = ProductImageOCRImporter.clean_cell_text(cells["country_of_origin"])
        shipment_by = ProductImageOCRImporter.clean_cell_text(cells["shipment_by"])
        product_name = ProductImageOCRImporter.clean_cell_text(product_words)
        packing = ProductImageOCRImporter.clean_cell_text(cells["packing"])
        price_text = " ".join(cells["price_aed"])
        price_aed = ProductImageOCRImporter.clean_number(price_text)

        if not product_name or not country_of_origin or not shipment_by:
            return None

        return {
            "serial_no": serial_no,
            "country_of_origin": country_of_origin,
            "shipment_by": shipment_by,
            "product_name": product_name,
            "weight_kg": weight_kg,
            "packing": packing,
            "price_aed": price_aed,
        }

    @staticmethod
    def parse_ordered_row(line: List[Dict]) -> Optional[Dict]:
        """Parse one OCR row by fixed column order instead of header names."""
        words = [word["text"] for word in sorted(line, key=lambda item: item["center_x"])]
        words = [
            word for word in words
            if word.lower() not in {"aed", "inr", "usd", "price:"}
        ]

        if len(words) < 7:
            return None

        serial_no = ProductImageOCRImporter.clean_serial_number(words[0])
        if not serial_no:
            return None

        shipment_index = ProductImageOCRImporter.find_shipment_index(words)
        if shipment_index <= 1:
            return None

        country_of_origin = ProductImageOCRImporter.clean_cell_text(words[1:shipment_index])
        shipment_by = words[shipment_index]
        remaining = words[shipment_index + 1:]

        price_index = ProductImageOCRImporter.find_last_price_token_index(remaining)
        if price_index is None or price_index <= 0:
            return None

        price_token = remaining[price_index]
        price_aed = ProductImageOCRImporter.clean_number(price_token)
        before_price = remaining[:price_index]

        weight_index = ProductImageOCRImporter.find_last_weight_token_index(before_price)
        if weight_index is None or weight_index <= 0:
            return None

        product_name = ProductImageOCRImporter.clean_cell_text(before_price[:weight_index])
        weight_kg = ProductImageOCRImporter.clean_number(before_price[weight_index])
        packing = ProductImageOCRImporter.clean_cell_text(before_price[weight_index + 1:])

        if not product_name or not country_of_origin or not shipment_by:
            return None

        return {
            "serial_no": serial_no,
            "country_of_origin": country_of_origin,
            "shipment_by": shipment_by,
            "product_name": product_name,
            "weight_kg": weight_kg,
            "packing": packing,
            "price_aed": price_aed,
        }

    @staticmethod
    def clean_cell_text(words: List[str]) -> str:
        text = " ".join(words)
        text = text.replace("~", "-").replace("—", "-")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def find_last_numeric_token_index(words: List[str]) -> Optional[int]:
        for index in range(len(words) - 1, -1, -1):
            if ProductImageOCRImporter.clean_number(words[index]):
                return index
        return None

    @staticmethod
    def find_last_price_token_index(words: List[str]) -> Optional[int]:
        for index in range(len(words) - 1, -1, -1):
            value = words[index].lower().strip()
            if value in {"na", "n/a", "-"} or ProductImageOCRImporter.clean_number(value):
                return index
        return None

    @staticmethod
    def find_last_weight_token_index(words: List[str]) -> Optional[int]:
        for index in range(len(words) - 1, -1, -1):
            value = words[index].lower().strip()
            if value in {"-", "—"} or ProductImageOCRImporter.clean_number(value):
                return index
        return None

    @staticmethod
    def parse_ocr_text(text: str) -> Tuple[List[Dict], List[str]]:
        """Parse OCR text into the same normalized row shape used by CSV import."""
        rows = []
        errors = []

        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = ProductImageOCRImporter.clean_line(raw_line)
            if not line or ProductImageOCRImporter.is_header_line(line):
                continue

            parsed = ProductImageOCRImporter.parse_line(raw_line)
            if parsed:
                rows.append(parsed)
            else:
                errors.append(f"OCR line {line_number}: Could not read product row: {raw_line.strip()}")

        if not rows and not errors:
            errors.append("No table rows were found in the image")

        return rows, errors

    @staticmethod
    def merge_rows(rows: List[Dict]) -> List[Dict]:
        """Merge duplicate OCR rows by serial number, keeping the most complete row."""
        best_by_serial = {}
        for row in rows:
            serial_no = row.get("serial_no")
            if not serial_no:
                continue
            current = best_by_serial.get(serial_no)
            if current is None or ProductImageOCRImporter.row_score(row) > ProductImageOCRImporter.row_score(current):
                best_by_serial[serial_no] = row

        return [
            best_by_serial[serial]
            for serial in sorted(best_by_serial, key=lambda value: int(value))
        ]

    @staticmethod
    def row_score(row: Dict) -> int:
        score = 0
        for field in ["country_of_origin", "shipment_by", "product_name", "weight_kg", "packing", "price_aed"]:
            if row.get(field):
                score += 1
        score += min(len(row.get("product_name", "")), 40)
        return score

    @staticmethod
    def clean_line(line: str) -> str:
        """Normalize common OCR separators without changing product text."""
        cleaned = line.strip().replace("|", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    @staticmethod
    def is_header_line(line: str) -> bool:
        lowered = line.lower()
        header_terms = ["product", "country", "shipment", "packing", "price", "weight"]
        return sum(1 for term in header_terms if term in lowered) >= 3

    @staticmethod
    def parse_line(line: str) -> Optional[Dict]:
        """Parse one OCR table line with conservative column-position heuristics."""
        pipe_row = ProductImageOCRImporter.parse_pipe_line(line)
        if pipe_row:
            return pipe_row

        parts = [part.strip() for part in re.split(r"\t|,| {2,}", line) if part.strip()]

        if len(parts) < 7:
            parts = line.split()

        parts = [
            part for part in parts
            if part.lower() not in {"aed", "inr", "usd", "price:"}
        ]

        if len(parts) < 7:
            return None

        serial_no = ProductImageOCRImporter.clean_serial_number(parts[0])
        if not serial_no:
            return None
        price_aed = ProductImageOCRImporter.clean_number(parts[-1])
        packing = parts[-2]
        weight_kg = ProductImageOCRImporter.clean_number(parts[-3])

        middle = parts[1:-3]
        if len(middle) < 3:
            return None

        shipment_index = ProductImageOCRImporter.find_shipment_index(middle)
        if shipment_index <= 0 or shipment_index >= len(middle) - 1:
            shipment_index = 1

        country_of_origin = " ".join(middle[:shipment_index])
        shipment_by = middle[shipment_index]
        product_name = " ".join(middle[shipment_index + 1:])

        return {
            "serial_no": serial_no,
            "country_of_origin": country_of_origin,
            "shipment_by": shipment_by,
            "product_name": product_name,
            "weight_kg": weight_kg,
            "packing": packing,
            "price_aed": price_aed,
        }

    @staticmethod
    def parse_pipe_line(line: str) -> Optional[Dict]:
        """Parse OCR text rows that preserve table separators."""
        if "|" not in line:
            return None

        cells = [
            ProductImageOCRImporter.clean_cell_text([cell])
            for cell in line.split("|")
            if ProductImageOCRImporter.clean_cell_text([cell])
        ]
        if len(cells) < 6:
            return None

        serial_no = ProductImageOCRImporter.clean_serial_number(cells[0])
        if not serial_no:
            return None

        country_of_origin = cells[1] if len(cells) > 1 else ""
        shipment_by = ""
        product_name = ""

        if len(cells) >= 7:
            shipment_by = cells[2]
            product_name = " ".join(cells[3:-3])
            weight_kg = ProductImageOCRImporter.clean_number(cells[-3])
            packing = cells[-2]
            price_aed = ProductImageOCRImporter.clean_number(cells[-1])
        else:
            shipment_and_product = cells[2]
            tokens = shipment_and_product.split()
            shipment_index = ProductImageOCRImporter.find_shipment_index(tokens)
            if shipment_index < 0:
                return None
            shipment_by = tokens[shipment_index]
            product_name = " ".join(tokens[shipment_index + 1:])
            weight_kg = ProductImageOCRImporter.clean_number(cells[-3])
            packing = cells[-2]
            price_aed = ProductImageOCRImporter.clean_number(cells[-1])

        product_name = product_name.strip("[]{} ")
        if not country_of_origin or not shipment_by or not product_name:
            return None

        return {
            "serial_no": serial_no,
            "country_of_origin": country_of_origin,
            "shipment_by": shipment_by,
            "product_name": product_name,
            "weight_kg": weight_kg,
            "packing": packing,
            "price_aed": price_aed,
        }

    @staticmethod
    def find_shipment_index(parts: List[str]) -> int:
        """Find the likely shipment column inside OCR tokens."""
        shipment_values = {"air", "sea", "road", "land", "courier", "cargo"}
        for index, part in enumerate(parts):
            if part.lower() in shipment_values:
                return index
        return -1

    @staticmethod
    def clean_number(value: str) -> str:
        """Keep only numeric characters that the CSV validator accepts."""
        return re.sub(r"[^0-9.]", "", value)

    @staticmethod
    def clean_serial_number(value: str) -> str:
        """Return a serial number only when the token is a clean whole number."""
        cleaned = str(value).strip().strip("(|). ")
        return cleaned if re.fullmatch(r"\d{1,4}", cleaned) else ""

    @staticmethod
    def rows_to_csv_content(rows: List[Dict]) -> str:
        """Convert normalized rows to CSV text accepted by ProductCSVImporter."""
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=ProductCSVImporter.CSV_COLUMNS)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                "S.No.": row.get("serial_no", ""),
                "Country of origin": row.get("country_of_origin", ""),
                "Shipment by": row.get("shipment_by", ""),
                "Product Name": row.get("product_name", ""),
                "Weight in kg": row.get("weight_kg", ""),
                "Packing": row.get("packing", ""),
                "Price in AED": row.get("price_aed", ""),
            })

        return output.getvalue()
