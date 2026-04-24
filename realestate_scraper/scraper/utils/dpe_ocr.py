import io
import os
import re
from typing import Iterable


def _extract_letter(text: str) -> str:
    if not text:
        return ""

    patterns: Iterable[str] = (
        r"classe\s+[eé]nergie\s*([A-G])\b",
        r"\bdpe\s*[:\-]?\s*([A-G])\b",
        r"\b([A-G])\b(?=.*(?:kwh|kwhep|energie|énergie))",
        r"\b([A-G])\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return match.group(1).upper()
    return ""


def infer_dpe_from_image_url(image_url: str) -> str:
    if not image_url:
        return ""
    patterns = (
        r"(?:^|[_/\-])dpe[_\- ]*([A-G])(?:[._/\-]|$)",
        r"(?:^|[_/\-])classe[_\- ]*([A-G])(?:[._/\-]|$)",
        r"(?:^|[_/\-])energy[_\- ]*([A-G])(?:[._/\-]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, image_url, re.I)
        if match:
            return match.group(1).upper()
    return ""


def ocr_dpe_from_image_bytes(image_bytes: bytes, image_url: str = "") -> str:
    inferred = infer_dpe_from_image_url(image_url)
    if inferred:
        return inferred
    if not image_bytes:
        return ""

    try:
        from PIL import Image, ImageFilter, ImageOps
        import pytesseract
    except Exception:
        return ""

    tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        base_image = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception:
        return ""

    variants = []
    for scale in (2, 3, 4):
        resized = base_image.resize(
            (max(1, base_image.width * scale), max(1, base_image.height * scale))
        )
        variants.append(ImageOps.autocontrast(resized))

    processed = []
    for image in variants:
        processed.append(image)
        processed.append(image.point(lambda px: 255 if px > 180 else 0, mode="1"))
        processed.append(ImageOps.invert(image).point(lambda px: 255 if px > 110 else 0, mode="1"))
        processed.append(image.filter(ImageFilter.SHARPEN))

    for image in processed:
        try:
            text = pytesseract.image_to_string(
                image,
                config="--psm 6 -c tessedit_char_whitelist=ABCDEFGabcdefg0123456789kwhKWHepm²:- ",
            )
        except Exception:
            continue
        letter = _extract_letter(text)
        if letter:
            return letter

    return ""
