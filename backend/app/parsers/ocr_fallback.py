"""OCR fallback for PDFs with broken text encoding.

Many Indian bank/credit card statements use embedded fonts with broken
ToUnicode mappings, causing pdfplumber to extract garbled text (U+FFFD).
This module detects that case and falls back to OCR via pytesseract.
"""

import pytesseract
from PIL import Image


def is_garbled(text: str, threshold: float = 0.3) -> bool:
    """Check if extracted text is garbled (high ratio of replacement chars)."""
    if not text or len(text) < 20:
        return True
    replacement_count = text.count("\ufffd") + text.count("�")
    # Also count chars that are just whitespace/control
    printable_ascii = sum(1 for c in text if c.isalnum())
    if printable_ascii == 0:
        return True
    garbled_ratio = replacement_count / len(text)
    return garbled_ratio > threshold


def ocr_page(page, resolution: int = 300) -> str:
    """Convert a pdfplumber page to image and OCR it."""
    img = page.to_image(resolution=resolution)
    pil_image = img.annotated
    text = pytesseract.image_to_string(pil_image)
    return text


def extract_text_with_ocr_fallback(page, resolution: int = 300) -> str:
    """Extract text from a page, falling back to OCR if text is garbled."""
    text = page.extract_text() or ""
    if is_garbled(text):
        text = ocr_page(page, resolution=resolution)
    return text


def extract_tables_with_ocr_fallback(page, resolution: int = 300):
    """Extract tables from a page. If normal extraction yields nothing
    and text is garbled, use OCR to get text and return it as raw text
    (caller will parse with regex)."""
    tables = page.extract_tables()
    if tables:
        # Verify the table content isn't garbled
        sample = ""
        for row in tables[0][:3]:
            sample += " ".join(str(cell) for cell in row if cell)
        if not is_garbled(sample):
            return tables, None  # tables are good, no OCR text

    # Tables are empty or garbled — try OCR
    text = page.extract_text() or ""
    if is_garbled(text):
        ocr_text = ocr_page(page, resolution=resolution)
        return [], ocr_text  # no usable tables, return OCR text

    return tables, None
