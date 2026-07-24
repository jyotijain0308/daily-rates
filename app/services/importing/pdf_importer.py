"""PDF table extraction utilities for product imports."""
import base64
import csv
import json
import re
from io import BytesIO, StringIO
from typing import Dict, List, Optional, Tuple

import requests

from app.services.importing.csv_importer import ProductCSVImporter
from app.services.importing.image_importer import ProductImageOCRImporter
from app.services.generation import config


class PDFImportError(Exception):
    """Raised when a PDF cannot be processed."""


class ProductPDFTableImporter:
    """Extract product table rows from a text-based PDF."""

    @staticmethod
    def extract_rows_from_upload(file_storage) -> Tuple[List[Dict], List[str]]:
        """Read an uploaded PDF and return normalized product rows plus warnings."""
        try:
            import pdfplumber
        except ImportError as exc:
            raise PDFImportError(
                "PDF import requires pdfplumber. Install it with `pip install -r requirements.txt`."
            ) from exc

        try:
            pdf_bytes = file_storage.read()
            if not pdf_bytes:
                return [], ["PDF file is empty"]

            warnings = []
            if ProductPDFTableImporter.should_use_ai():
                try:
                    ai_rows = ProductPDFTableImporter.extract_rows_with_configured_ai(
                        pdf_bytes,
                        getattr(file_storage, "filename", "products.pdf") or "products.pdf",
                    )
                    if ai_rows:
                        return ai_rows, []
                    warnings.append("AI extraction did not return product rows; falling back to PDF table extraction")
                except Exception as exc:
                    warnings.append(f"AI extraction failed; falling back to PDF/OCR extraction: {exc}")

            rows = []
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables() or []
                    for table in tables:
                        for raw_row in table or []:
                            parsed = ProductPDFTableImporter.parse_table_row(raw_row)
                            if parsed:
                                rows.append(parsed)

                    if not tables:
                        warnings.append(f"Page {page_number}: No extractable table found")

            if not rows:
                ocr_rows, ocr_warnings = ProductPDFTableImporter.extract_rows_from_pdf_images(pdf_bytes)
                if ocr_rows:
                    return ocr_rows, ocr_warnings
                warnings.extend(ocr_warnings)
                warnings.append("No product table rows were found in the PDF")

            return rows, warnings
        except PDFImportError:
            raise
        except Exception as exc:
            raise PDFImportError(f"Could not extract tables from PDF: {exc}") from exc

    @staticmethod
    def should_use_ai() -> bool:
        provider = getattr(config, "PDF_TABLE_EXTRACTION_PROVIDER", "ollama")
        if provider == "openai":
            return bool(getattr(config, "OPENAI_API_KEY", ""))
        return provider == "ollama"

    @staticmethod
    def extract_rows_with_configured_ai(pdf_bytes: bytes, filename: str) -> List[Dict]:
        provider = getattr(config, "PDF_TABLE_EXTRACTION_PROVIDER", "ollama")
        if provider == "openai":
            return ProductPDFTableImporter.extract_rows_with_openai(pdf_bytes, filename)
        if provider == "ollama":
            return ProductPDFTableImporter.extract_rows_with_ollama(pdf_bytes)
        return []

    @staticmethod
    def extract_rows_with_openai(pdf_bytes: bytes, filename: str) -> List[Dict]:
        """Use an AI vision/file model to extract product table rows from a PDF."""
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise PDFImportError(
                "AI PDF import requires openai. Install it with `pip install -r requirements.txt`."
            ) from exc

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")
        prompt = (
            "Extract only the product-rate table rows from this PDF. Ignore page titles, QR codes, "
            "watermarks, headers, footers, phone numbers, and non-table text. The table columns are in this "
            "fixed order: S.No., Country of origin, Shipment by, Product Name, Weight in kg, Packing, "
            "Price in AED. Return only valid JSON, with this shape: "
            "{\"rows\":[{\"serial_no\":\"1\",\"country_of_origin\":\"India\",\"shipment_by\":\"Sea\","
            "\"product_name\":\"Onion New Crop (18 Kg)\",\"weight_kg\":\"1.0\","
            "\"packing\":\"Sold by Weight\",\"price_aed\":\"3.20\"}]}. "
            "Use empty string for NA or unreadable numeric values. Preserve product names as written."
        )

        response = client.responses.create(
            model=config.OPENAI_PDF_EXTRACTION_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": filename,
                            "file_data": f"data:application/pdf;base64,{encoded_pdf}",
                        },
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        output_text = getattr(response, "output_text", "") or ""
        return ProductPDFTableImporter.parse_ai_response(output_text)

    @staticmethod
    def extract_rows_with_ollama(pdf_bytes: bytes) -> List[Dict]:
        """Use a local Ollama vision model to extract product rows from rendered PDF pages."""
        rows = []
        for page_number, encoded_png in enumerate(
            ProductPDFTableImporter.render_pdf_pages_to_base64_png(pdf_bytes),
            start=1,
        ):
            prompt = ProductPDFTableImporter.ai_extraction_prompt(
                f"Extract only table rows from page {page_number}."
            )
            response = requests.post(
                f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={
                    "model": config.OLLAMA_PDF_EXTRACTION_MODEL,
                    "prompt": prompt,
                    "images": [encoded_png],
                    "stream": False,
                    "format": "json",
                },
                timeout=120,
            )
            response.raise_for_status()
            output_text = response.json().get("response", "")
            rows.extend(ProductPDFTableImporter.parse_ai_response(output_text))
        return ProductPDFTableImporter.merge_rows(rows)

    @staticmethod
    def render_pdf_pages_to_base64_png(pdf_bytes: bytes) -> List[str]:
        """Render PDF pages into base64 PNG images for local vision models."""
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise PDFImportError(
                "Ollama PDF import requires pypdfium2. Install it with `pip install -r requirements.txt`."
            ) from exc

        encoded_pages = []
        pdf = pdfium.PdfDocument(pdf_bytes)
        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]
                try:
                    image = page.render(scale=3).to_pil().convert("RGB")
                    buffer = BytesIO()
                    image.save(buffer, format="PNG", optimize=True)
                    encoded_pages.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
                finally:
                    page.close()
        finally:
            pdf.close()
        return encoded_pages

    @staticmethod
    def ai_extraction_prompt(prefix: str = "") -> str:
        return (
            f"{prefix} "
            "Extract only the product-rate table rows. Ignore page titles, QR codes, "
            "watermarks, headers, footers, phone numbers, and non-table text. The table columns are in this "
            "fixed order: S.No., Country of origin, Shipment by, Product Name, Weight in kg, Packing, "
            "Price in AED. Return only valid JSON, with this exact shape: "
            "{\"rows\":[{\"serial_no\":\"1\",\"country_of_origin\":\"India\",\"shipment_by\":\"Sea\","
            "\"product_name\":\"Onion New Crop (18 Kg)\",\"weight_kg\":\"1.0\","
            "\"packing\":\"Sold by Weight\",\"price_aed\":\"3.20\"}]}. "
            "Use empty string for NA or unreadable numeric values. Preserve product names as written."
        )

    @staticmethod
    def parse_ai_response(output_text: str) -> List[Dict]:
        """Parse and normalize AI JSON table extraction output."""
        cleaned = output_text.strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
        if fence_match:
            cleaned = fence_match.group(1).strip()

        payload = json.loads(cleaned)
        raw_rows = payload if isinstance(payload, list) else payload.get("rows", [])
        if not isinstance(raw_rows, list):
            return []

        rows = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            normalized = ProductPDFTableImporter.normalize_ai_row(raw_row)
            if normalized:
                rows.append(normalized)
        return rows

    @staticmethod
    def merge_rows(rows: List[Dict]) -> List[Dict]:
        best_by_serial = {}
        for row in rows:
            serial_no = row.get("serial_no")
            if not serial_no:
                continue
            best_by_serial[serial_no] = row
        return [
            best_by_serial[serial]
            for serial in sorted(best_by_serial, key=lambda value: int(value))
        ]

    @staticmethod
    def normalize_ai_row(row: Dict) -> Optional[Dict]:
        serial_no = ProductPDFTableImporter.clean_number(row.get("serial_no", ""))
        if not serial_no or not serial_no.isdigit():
            return None

        return {
            "serial_no": serial_no,
            "country_of_origin": ProductPDFTableImporter.clean_cell(row.get("country_of_origin", "")),
            "shipment_by": ProductPDFTableImporter.clean_cell(row.get("shipment_by", "")),
            "product_name": ProductPDFTableImporter.clean_cell(row.get("product_name", "")),
            "weight_kg": ProductPDFTableImporter.clean_number(row.get("weight_kg", "")),
            "packing": ProductPDFTableImporter.clean_cell(row.get("packing", "")),
            "price_aed": ProductPDFTableImporter.clean_number(row.get("price_aed", "")),
        }

    @staticmethod
    def extract_rows_from_pdf_images(pdf_bytes: bytes) -> Tuple[List[Dict], List[str]]:
        """Render image-based PDF pages and extract tables using OCR."""
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise PDFImportError(
                "Image-based PDF import requires pypdfium2. Install it with `pip install -r requirements.txt`."
            ) from exc

        rows = []
        warnings = []

        try:
            pdf = pdfium.PdfDocument(pdf_bytes)
            try:
                for page_index in range(len(pdf)):
                    page = pdf[page_index]
                    try:
                        bitmap = page.render(scale=4)
                        image = bitmap.to_pil()
                        page_rows, page_errors, _ = ProductImageOCRImporter.extract_rows_from_image(image)
                        rows.extend(page_rows)
                        if page_errors:
                            warnings.extend(
                                f"Page {page_index + 1}: {error}" for error in page_errors
                            )
                    finally:
                        page.close()
            finally:
                pdf.close()
        except PDFImportError:
            raise
        except Exception as exc:
            raise PDFImportError(f"Could not render PDF pages for OCR: {exc}") from exc

        if rows:
            return rows, []

        warnings.append("No OCR-readable product rows were found in image-based PDF pages")

        return rows, warnings

    @staticmethod
    def parse_table_row(raw_row: List[str]) -> Optional[Dict]:
        """Parse one PDF table row by expected column order."""
        cells = [ProductPDFTableImporter.clean_cell(cell) for cell in raw_row if ProductPDFTableImporter.clean_cell(cell)]
        if len(cells) < 7:
            return None

        serial_no = ProductPDFTableImporter.clean_number(cells[0])
        if not serial_no or not serial_no.isdigit():
            return None

        if len(cells) == 7:
            product_name = cells[3]
            weight_kg = cells[4]
            packing = cells[5]
            price_aed = cells[6]
        else:
            product_name = " ".join(cells[3:-3])
            weight_kg = cells[-3]
            packing = cells[-2]
            price_aed = cells[-1]

        return {
            "serial_no": serial_no,
            "country_of_origin": cells[1],
            "shipment_by": cells[2],
            "product_name": product_name,
            "weight_kg": ProductPDFTableImporter.clean_number(weight_kg),
            "packing": packing,
            "price_aed": ProductPDFTableImporter.clean_number(price_aed),
        }

    @staticmethod
    def clean_cell(value) -> str:
        text = "" if value is None else str(value)
        return " ".join(text.replace("\n", " ").split())

    @staticmethod
    def clean_number(value: str) -> str:
        return "".join(char for char in str(value) if char.isdigit() or char == ".")

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
