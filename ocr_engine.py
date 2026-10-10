#!/usr/bin/env python3
"""
ocr_engine.py
=============
Extract key fields from a scanned Bangladeshi land record (khatian / deed).

Pipeline
--------
1. Preprocess the image (optional, needs OpenCV).
2. Run PaddleOCR with Bengali ("bn"); optionally fall back to Tesseract ("ben").
3. Rebuild text lines from OCR boxes (sorted top-to-bottom, left-to-right).
4. Pull out fields with regular expressions.
5. If image processing / OCR fails, fall back to a mock structured parser
   (clearly flagged in the metadata so fake data is never mistaken for real).

Fields returned
---------------
    khatian_no  <- খতিয়ান নং
    plot_no     <- দাগ নং
    owner_name  <- মালিকের নাম
    mouza       <- মৌজা
    land_area   <- জমির পরিমাণ

Usage
-----
    python ocr_engine.py scan.jpg
    python ocr_engine.py scan.jpg --ascii-digits --meta
    python ocr_engine.py --mock

    from ocr_engine import extract_land_record
    record = extract_land_record("scan.jpg")
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import statistics
import sys
import unicodedata
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ocr_engine")

FIELD_KEYS = ("khatian_no", "plot_no", "owner_name", "mouza", "land_area")

# --------------------------------------------------------------------------- #
# Text normalisation helpers
# --------------------------------------------------------------------------- #

_BN_DIGITS = "০১২৩৪৫৬৭৮৯"
_BN_TO_ASCII = str.maketrans(_BN_DIGITS, "0123456789")
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)


def normalize_text(text: str) -> str:
    """NFC-normalise, drop zero-width chars, unify colons/dashes/spaces.
    Newlines are preserved so line structure survives."""
    text = unicodedata.normalize("NFC", text).translate(_INVISIBLE)
    text = text.replace("：", ":").replace("–", "-").replace("—", "-")
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def to_ascii_digits(value: Optional[str]) -> Optional[str]:
    return value.translate(_BN_TO_ASCII) if value else value


# --------------------------------------------------------------------------- #
# Regular expressions
# --------------------------------------------------------------------------- #

_SEP = r"\s*[:ঃ\-.]*\s*"            # ':' , 'ঃ' (visarga), '-', '.' between label and value
_NUM = r"[০-৯0-9]"
_NO = r"(?:নং|নম্বর|নাম্বার|নঃ|নo|No\.?)?"   # "No." suffix, optional

# Words that mark the start of the *next* label; used to stop free-text captures.
_STOP = (
    r"(?:পিতা|পিতার|স্বামী|স্বামীর|মাতা|মাতার|মৌজা|মৌজার|দাগ|খতিয়ান|জমির|জেলা|উপজেলা|"
    r"থানা|জে\.?\s*এল|জেএল|সাবেক|হাল|শ্রেণী|ঠিকানা|ইউনিয়ন|পরিমাণ)"
)

_UNITS = r"(?:একর|শতক|শতাংশ|ডেসিমেল|কাঠা|বিঘা|হেক্টর|acres?|decimals?|শত)"

PATTERNS: Dict[str, List[re.Pattern]] = {
    "khatian_no": [
        re.compile(rf"খতিয়ান\s*{_NO}{_SEP}({_NUM}+(?:\s*/\s*{_NUM}+)?)"),
    ],
    "plot_no": [
        # Allows "১২৩", "১২৩/১", "১২৩, ১২৪, ১২৫"
        re.compile(
            rf"দাগ\s*{_NO}{_SEP}({_NUM}+(?:\s*[/,]\s*{_NUM}+)*)"
        ),
    ],
    "owner_name": [
        re.compile(
            rf"(?:মালিকের|মালিক|রায়তের|রায়ত|দখলকারের|দখলকার)\s*নাম{_SEP}"
            rf"([^\n:]+?)(?=\s+{_STOP}|\s*[,;|]|\n|$)"
        ),
    ],
    "mouza": [
        re.compile(
            rf"মৌজা(?:র\s*নাম)?{_SEP}"
            rf"([^\n:০-৯0-9]+?)(?=\s+{_STOP}|\s*[,;|]|\n|$)"
        ),
    ],
    "land_area": [
        re.compile(
            rf"জমির\s*পরিমাণ{_SEP}"
            rf"({_NUM}[{_BN_DIGITS}0-9.,/ ]*?\s*{_UNITS}?(?:\s*{_NUM}[{_BN_DIGITS}0-9.,/ ]*?\s*{_UNITS})*)"
            rf"(?=\s+{_STOP}|\s*[;|]|\n|$)",
            re.IGNORECASE,
        ),
        re.compile(rf"পরিমাণ{_SEP}({_NUM}[{_BN_DIGITS}0-9.,]*\s*{_UNITS})", re.IGNORECASE),
    ],
}


def _clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" \t:-ঃ.,;|।'\"")
    return value


def parse_fields(raw_text: str, ascii_digits: bool = False) -> Dict[str, Optional[str]]:
    """Run the regexes over OCR text. Missing fields come back as None."""
    text = normalize_text(raw_text)
    result: Dict[str, Optional[str]] = {k: None for k in FIELD_KEYS}

    for key, patterns in PATTERNS.items():
        for pat in patterns:
            m = pat.search(text)
            if m:
                value = _clean_value(m.group(1))
                if value:
                    result[key] = value
                    break

    if ascii_digits:
        for key in ("khatian_no", "plot_no", "land_area"):
            result[key] = to_ascii_digits(result[key])
    return result


# --------------------------------------------------------------------------- #
# Image handling + OCR backends
# --------------------------------------------------------------------------- #

class OCRError(RuntimeError):
    """Raised when no OCR backend could read the image."""


def preprocess_image(image_path: str):
    """Light cleanup with OpenCV (grayscale -> upscale -> denoise).
    Returns a BGR numpy array, or None if OpenCV is unavailable (the raw path
    is then handed to the OCR engine directly)."""
    try:
        import cv2  # type: ignore
    except ImportError:
        logger.info("OpenCV not installed; skipping preprocessing.")
        return None

    img = cv2.imread(image_path)
    if img is None:
        raise OCRError(f"Could not decode image: {image_path}")

    h, w = img.shape[:2]
    if max(h, w) < 1600:  # small scans OCR poorly; upscale
        scale = 1600 / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, h=12, templateWindowSize=7, searchWindowSize=21)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)  # Paddle expects 3 channels


def _flatten_points(box: Any) -> List[Tuple[float, float]]:
    pts = []
    for p in box:
        try:
            pts.append((float(p[0]), float(p[1])))
        except (TypeError, IndexError):
            pass
    return pts


def _items_to_text(items: List[Tuple[Any, str]]) -> str:
    """Group (box, text) OCR items into reading-order lines."""
    boxes = []
    for box, text in items:
        text = (text or "").strip()
        if not text:
            continue
        pts = _flatten_points(box)
        if not pts:
            boxes.append((0.0, 0.0, 1.0, text))
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        boxes.append((min(xs), (min(ys) + max(ys)) / 2, max(ys) - min(ys), text))

    if not boxes:
        return ""

    median_h = statistics.median(b[2] for b in boxes) or 1.0
    tol = max(median_h * 0.6, 4.0)
    boxes.sort(key=lambda b: (b[1], b[0]))

    rows: List[List[Tuple[float, float, float, str]]] = []
    for b in boxes:
        if rows and abs(b[1] - statistics.mean(r[1] for r in rows[-1])) <= tol:
            rows[-1].append(b)
        else:
            rows.append([b])

    return "\n".join(" ".join(t[3] for t in sorted(row, key=lambda t: t[0])) for row in rows)


_PADDLE_INSTANCE = None


def _get_paddle(lang: str):
    """Create the PaddleOCR engine once (model load is slow)."""
    global _PADDLE_INSTANCE
    if _PADDLE_INSTANCE is not None:
        return _PADDLE_INSTANCE

    from paddleocr import PaddleOCR  # type: ignore

    try:  # PaddleOCR 3.x API
        _PADDLE_INSTANCE = PaddleOCR(lang=lang, use_textline_orientation=True)
    except (TypeError, ValueError):  # PaddleOCR 2.x API
        _PADDLE_INSTANCE = PaddleOCR(lang=lang, use_angle_cls=True, show_log=False)
    return _PADDLE_INSTANCE


def ocr_with_paddle(image: Any, lang: str = "bn") -> str:
    ocr = _get_paddle(lang)
    items: List[Tuple[Any, str]] = []

    if hasattr(ocr, "predict"):  # 3.x
        for page in ocr.predict(image):
            data = page.get("res", page) if isinstance(page, dict) else page
            texts = data.get("rec_texts", [])
            boxes = data.get("rec_polys")
            if boxes is None:
                boxes = data.get("rec_boxes", [])
            for i, t in enumerate(texts):
                box = boxes[i] if i < len(boxes) else []
                if len(box) == 4 and not hasattr(box[0], "__len__"):  # [x1,y1,x2,y2]
                    x1, y1, x2, y2 = box
                    box = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
                items.append((box, t))
    else:  # 2.x
        for page in ocr.ocr(image, cls=True) or []:
            for line in page or []:
                box, (text, _conf) = line
                items.append((box, text))

    return _items_to_text(items)


def ocr_with_tesseract(image_path: str) -> str:
    """Optional secondary engine (needs pytesseract + the 'ben' language pack)."""
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore

    return pytesseract.image_to_string(Image.open(image_path), lang="ben")


def run_ocr(image_path: str, lang: str = "bn", use_tesseract_fallback: bool = True) -> Tuple[str, str]:
    """Return (raw_text, engine_name) or raise OCRError."""
    if not image_path or not os.path.isfile(image_path):
        raise OCRError(f"Image not found: {image_path!r}")

    errors: List[str] = []

    try:
        processed = preprocess_image(image_path)
        text = ocr_with_paddle(processed if processed is not None else image_path, lang)
        if text.strip():
            return text, "paddleocr"
        errors.append("PaddleOCR returned no text")
    except ImportError as exc:
        errors.append(f"PaddleOCR not installed ({exc})")
    except Exception as exc:  # noqa: BLE001 - OCR libs raise many error types
        errors.append(f"PaddleOCR failed: {exc}")

    if use_tesseract_fallback:
        try:
            text = ocr_with_tesseract(image_path)
            if text.strip():
                return text, "tesseract"
            errors.append("Tesseract returned no text")
        except ImportError as exc:
            errors.append(f"Tesseract unavailable ({exc})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Tesseract failed: {exc}")

    raise OCRError("; ".join(errors))


# --------------------------------------------------------------------------- #
# Mock parser (fallback / testing)
# --------------------------------------------------------------------------- #

MOCK_OCR_TEXT = """\
গণপ্রজাতন্ত্রী বাংলাদেশ সরকার
খতিয়ান নং : ১২৪৫
জেলা : ঢাকা   উপজেলা : সাভার
মৌজা : আশুলিয়া   জে এল নং : ৫৪
দাগ নং : ৭৮৯/১
মালিকের নাম : মোঃ আব্দুর রহমান পিতা : মৃত আব্দুল করিম
জমির পরিমাণ : ০.৩৩ একর
"""


def mock_parse(ascii_digits: bool = False) -> Dict[str, Optional[str]]:
    """Run the *same* regex pipeline over canned text so the mock path
    exercises the real extraction logic."""
    return parse_fields(MOCK_OCR_TEXT, ascii_digits=ascii_digits)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def extract_land_record(
    image_path: Optional[str],
    lang: str = "bn",
    ascii_digits: bool = False,
    allow_mock: bool = True,
    with_meta: bool = False,
) -> Dict[str, Any]:
    """
    Extract land record fields from a scanned image.

    Parameters
    ----------
    image_path    : path to the scanned khatian / deed image
    lang          : PaddleOCR language code (default "bn")
    ascii_digits  : convert Bengali digits (১২৩) to ASCII (123) in numeric fields
    allow_mock    : on OCR failure, return mock data instead of raising
    with_meta     : add a "_meta" key (engine used, warnings, raw text)

    Returns
    -------
    dict with keys khatian_no, plot_no, owner_name, mouza, land_area
    (values are str, or None if not found).
    """
    meta: Dict[str, Any] = {"engine": None, "is_mock": False, "warnings": [], "raw_text": ""}

    try:
        raw_text, engine = run_ocr(image_path or "", lang=lang)
        meta.update(engine=engine, raw_text=raw_text)
        record = parse_fields(raw_text, ascii_digits=ascii_digits)
        missing = [k for k, v in record.items() if v is None]
        if missing:
            meta["warnings"].append(f"Fields not found: {', '.join(missing)}")
            logger.warning("Fields not found in OCR text: %s", missing)
    except OCRError as exc:
        if not allow_mock:
            raise
        logger.warning("OCR failed (%s). Returning MOCK data - do not use as real.", exc)
        meta.update(engine="mock", is_mock=True, raw_text=MOCK_OCR_TEXT)
        meta["warnings"].append(f"OCR failed, mock data returned: {exc}")
        record = mock_parse(ascii_digits=ascii_digits)

    out: Dict[str, Any] = dict(record)
    if with_meta:
        out["_meta"] = meta
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="OCR a scanned land khatian/deed image.")
    ap.add_argument("image", nargs="?", help="path to the scanned image")
    ap.add_argument("--lang", default="bn", help="PaddleOCR language code (default: bn)")
    ap.add_argument("--ascii-digits", action="store_true", help="convert Bengali digits to 0-9")
    ap.add_argument("--no-mock", action="store_true", help="raise instead of returning mock data on failure")
    ap.add_argument("--mock", action="store_true", help="skip OCR and use the mock parser")
    ap.add_argument("--meta", action="store_true", help="include engine/warning metadata")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    if not args.image and not args.mock:
        ap.error("provide an image path or use --mock")

    try:
        if args.mock:
            result: Dict[str, Any] = dict(mock_parse(args.ascii_digits))
            if args.meta:
                result["_meta"] = {"engine": "mock", "is_mock": True, "warnings": [], "raw_text": MOCK_OCR_TEXT}
        else:
            result = extract_land_record(
                args.image,
                lang=args.lang,
                ascii_digits=args.ascii_digits,
                allow_mock=not args.no_mock,
                with_meta=args.meta,
            )
    except OCRError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())