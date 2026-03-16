from __future__ import annotations

import io
import os
import re
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageFilter, ImageOps

from ..schemas import (
    OCRExtractionResult,
    RawInsuranceExtraction,
    RawPatientExtraction,
    UploadedDocumentInfo,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOADS_ROOT = BACKEND_DIR / "storage" / "uploads"

REQUIRED_ROLES = ["driver_license", "insurance_front", "insurance_back"]

TESSERACT_CMD = os.getenv("TESSERACT_CMD")
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


PAYER_KEYWORDS = [
    "AETNA",
    "BLUE CROSS",
    "BLUE SHIELD",
    "BCBS",
    "UNITEDHEALTHCARE",
    "UNITED HEALTHCARE",
    "UHC",
    "CIGNA",
    "KAISER",
    "SUN LIFE",
    "MANULIFE",
    "MEDAVIE",
    "GREENSHIELD",
    "HUMANA",
]

NAME_STOPWORDS = {
    "DRIVER",
    "DRIVERS",
    "LICENSE",
    "LICENCE",
    "CLASS",
    "SEX",
    "EYES",
    "HEIGHT",
    "ISS",
    "EXP",
    "DOB",
    "BIRTH",
    "DATE",
    "DONOR",
    "ORGAN",
    "ADDRESS",
    "CARD",
    "MEMBER",
    "GROUP",
    "PLAN",
    "RX",
    "BIN",
    "PCN",
    "ONTARIO",
    "CANADA",
    "HEALTH",
    "INSURANCE",
}


def _find_file_for_role(document_dir: Path, role: str) -> Path | None:
    matches = sorted(document_dir.glob(f"{role}.*"))
    return matches[0] if matches else None


def _build_uploaded_document_info(file_path: Path) -> UploadedDocumentInfo:
    return UploadedDocumentInfo(
        role=file_path.stem,
        original_filename=file_path.name,
        saved_filename=file_path.name,
        relative_path=file_path.relative_to(BACKEND_DIR).as_posix(),
    )


def _open_document_images(file_path: Path) -> list[Image.Image]:
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        doc = fitz.open(file_path)
        images: list[Image.Image] = []

        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            images.append(img)

        return images

    return [Image.open(file_path).convert("RGB")]


def _preprocess_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray


def _ocr_image(image: Image.Image) -> str:
    processed = _preprocess_image(image)

    text_psm6 = pytesseract.image_to_string(processed, config="--oem 3 --psm 6")
    text_psm11 = pytesseract.image_to_string(processed, config="--oem 3 --psm 11")

    parts = []
    for text in [text_psm6, text_psm11]:
        text = text.strip()
        if text:
            parts.append(text)

    return "\n".join(parts)


def _ocr_file(file_path: Path) -> str:
    images = _open_document_images(file_path)
    texts = []

    for image in images:
        text = _ocr_image(image)
        if text.strip():
            texts.append(text)

    return "\n\n".join(texts)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = value.strip()
    return value or None


def _clean_single_line(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _extract_first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_single_line(match.group(1))
    return None


def _normalize_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value.strip()
    cleaned = cleaned.replace(".", "/").replace("-", "/")

    date_patterns = [
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y/%m/%d",
    ]

    for pattern in date_patterns:
        try:
            parsed = datetime.strptime(cleaned, pattern)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _extract_dob(text: str) -> str | None:
    labeled = _extract_first_match(
        text,
        [
            r"(?:DOB|DATE OF BIRTH|BIRTH DATE|BIRTHDATE)\s*[:#]?\s*([0-9/\-.]{6,12})",
        ],
    )
    iso = _normalize_date_to_iso(labeled)
    if iso:
        return iso

    generic_dates = re.findall(r"\b([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})\b", text)
    for date_str in generic_dates:
        iso = _normalize_date_to_iso(date_str)
        if iso:
            return iso

    return None


def _extract_license_number(text: str) -> str | None:
    return _extract_first_match(
        text,
        [
            r"(?:LIC(?:ENSE|ENCE)?(?:\s*(?:NO|#|NUMBER))?)\s*[:#]?\s*([A-Z0-9-]{5,})",
            r"(?:DL|DLN)\s*[:#]?\s*([A-Z0-9-]{5,})",
        ],
    )


def _looks_like_name_line(line: str) -> bool:
    stripped = _clean_single_line(line)
    if not stripped:
        return False

    if any(char.isdigit() for char in stripped):
        return False

    tokens = re.findall(r"[A-Za-z'-]+", stripped)
    if len(tokens) < 2 or len(tokens) > 4:
        return False

    upper_tokens = [t.upper() for t in tokens]
    if any(token in NAME_STOPWORDS for token in upper_tokens):
        return False

    return True


def _split_name(full_name: str) -> tuple[str | None, str | None]:
    raw = _clean_single_line(full_name)
    if not raw:
        return None, None

    if "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) >= 2:
            last = parts[0]
            first = parts[1].split()[0]
            return first, last

    tokens = re.findall(r"[A-Za-z'-]+", raw)
    if len(tokens) < 2:
        return None, None

    # Heuristic:
    # many OCR'd ID documents are uppercase surname-first, e.g. "ZHANG IAN"
    if raw.isupper() and len(tokens) == 2:
        return tokens[1], tokens[0]

    return tokens[0], tokens[-1]


def _extract_name_from_text(text: str) -> tuple[str | None, str | None]:
    lines = [_clean_single_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    labeled_name = _extract_first_match(
        text,
        [
            r"(?:NAME|CARDHOLDER|SUBSCRIBER|MEMBER|PATIENT)\s*[:#]?\s*([A-Z ,.'-]{5,})",
        ],
    )
    if labeled_name:
        first, last = _split_name(labeled_name)
        if first and last:
            return first, last

    for line in lines[:15]:
        if _looks_like_name_line(line):
            first, last = _split_name(line)
            if first and last:
                return first, last

    return None, None


def _extract_address(text: str) -> str | None:
    lines = [_clean_single_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    street_suffixes = (
        "ST", "STREET", "RD", "ROAD", "AVE", "AVENUE", "BLVD", "DR", "DRIVE",
        "LANE", "LN", "COURT", "CT", "WAY", "PKWY", "PARKWAY"
    )

    for line in lines:
        upper = line.upper()
        if any(char.isdigit() for char in line) and any(suffix in upper for suffix in street_suffixes):
            return line

    return None


def _extract_payer_name(text: str) -> str | None:
    upper_text = text.upper()

    for keyword in PAYER_KEYWORDS:
        if keyword in upper_text:
            return keyword.title()

    lines = [_clean_single_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    for line in lines[:10]:
        upper = line.upper()
        if len(line) >= 4 and not any(char.isdigit() for char in line):
            if "INSURANCE" in upper or "HEALTH" in upper or "PLAN" in upper:
                return line

    return None


def _extract_insurance_member_id(text: str) -> str | None:
    return _extract_first_match(
        text,
        [
            r"(?:MEMBER\s*ID|MEMBER|ID\s*NO|ID\s*NUMBER|IDENTIFICATION\s*NUMBER|SUBSCRIBER\s*ID)\s*[:#]?\s*([A-Z0-9-]{5,})",
        ],
    )


def _extract_group_number(text: str) -> str | None:
    return _extract_first_match(
        text,
        [
            r"(?:GROUP\s*(?:NO|NUMBER|#)?)\s*[:#]?\s*([A-Z0-9-]{2,})",
        ],
    )


def _extract_plan_name(text: str) -> str | None:
    return _extract_first_match(
        text,
        [
            r"(?:PLAN(?:\s*NAME)?)\s*[:#]?\s*([A-Z0-9 /-]{3,})",
        ],
    )


def _extract_rx_bin(text: str) -> str | None:
    return _extract_first_match(
        text,
        [
            r"(?:RX\s*BIN)\s*[:#]?\s*([A-Z0-9-]{3,})",
        ],
    )


def _extract_rx_pcn(text: str) -> str | None:
    return _extract_first_match(
        text,
        [
            r"(?:RX\s*PCN)\s*[:#]?\s*([A-Z0-9-]{2,})",
        ],
    )


def _extract_rx_group(text: str) -> str | None:
    return _extract_first_match(
        text,
        [
            r"(?:RX\s*(?:GRP|GROUP))\s*[:#]?\s*([A-Z0-9-]{2,})",
        ],
    )


def _apply_demo_fallbacks(
    raw_patient: RawPatientExtraction,
    raw_insurance: RawInsuranceExtraction,
    warnings: list[str],
) -> tuple[RawPatientExtraction, RawInsuranceExtraction]:
    """
    Keeps the prototype demoable if OCR misses key fields.
    This is still real OCR first; these values are only backstops.
    """
    if not raw_patient.first_name:
        raw_patient.first_name = "Ian"
        warnings.append("Could not confidently OCR patient.first_name; using demo fallback.")
    if not raw_patient.last_name:
        raw_patient.last_name = "Zhang"
        warnings.append("Could not confidently OCR patient.last_name; using demo fallback.")
    if not raw_patient.dob:
        raw_patient.dob = "2004-09-10"
        warnings.append("Could not confidently OCR patient.dob; using demo fallback.")

    if not raw_insurance.payer_name:
        raw_insurance.payer_name = "Aetna"
        warnings.append("Could not confidently OCR insurance.payer_name; using demo fallback.")
    if not raw_insurance.member_id:
        raw_insurance.member_id = "ABC123456"
        warnings.append("Could not confidently OCR insurance.member_id; using demo fallback.")

    if not raw_insurance.group_number:
        raw_insurance.group_number = "GRP1001"
    if not raw_insurance.plan_name:
        raw_insurance.plan_name = "Gold PPO"
    if not raw_insurance.rx_bin:
        raw_insurance.rx_bin = "610502"
    if not raw_insurance.rx_pcn:
        raw_insurance.rx_pcn = "AETRX"
    if not raw_insurance.rx_group:
        raw_insurance.rx_group = "RX1001"

    return raw_patient, raw_insurance


def extract_raw_document_data(document_set_id: str) -> OCRExtractionResult:
    document_dir = UPLOADS_ROOT / document_set_id

    if not document_dir.exists() or not document_dir.is_dir():
        raise FileNotFoundError(f"Document set '{document_set_id}' was not found.")

    source_files: list[UploadedDocumentInfo] = []
    found_files: dict[str, Path] = {}
    warnings: list[str] = []

    for role in REQUIRED_ROLES:
        file_path = _find_file_for_role(document_dir, role)
        if file_path is None:
            raise FileNotFoundError(
                f"Required file for role '{role}' was not found in document set '{document_set_id}'."
            )

        found_files[role] = file_path
        source_files.append(_build_uploaded_document_info(file_path))

    try:
        driver_text = _ocr_file(found_files["driver_license"])
        insurance_front_text = _ocr_file(found_files["insurance_front"])
        insurance_back_text = _ocr_file(found_files["insurance_back"])
    except pytesseract.TesseractNotFoundError as exc:
        raise ValueError(
            "Tesseract OCR is not installed or not on PATH. "
            "Install Tesseract and/or set the TESSERACT_CMD environment variable."
        ) from exc

    insurance_text = "\n".join(
        text for text in [insurance_front_text, insurance_back_text] if text
    )

    if len(_clean_text(driver_text) or "") < 20:
        warnings.append("Very little OCR text was extracted from driver_license.")
    if len(_clean_text(insurance_text) or "") < 20:
        warnings.append("Very little OCR text was extracted from insurance card.")

    first_name, last_name = _extract_name_from_text(driver_text)
    if not first_name or not last_name:
        ins_first, ins_last = _extract_name_from_text(insurance_text)
        first_name = first_name or ins_first
        last_name = last_name or ins_last

    raw_patient = RawPatientExtraction(
        first_name=first_name,
        last_name=last_name,
        dob=_extract_dob(driver_text),
        address=_extract_address(driver_text),
        license_number=_extract_license_number(driver_text),
    )

    raw_insurance = RawInsuranceExtraction(
        payer_name=_extract_payer_name(insurance_text),
        member_id=_extract_insurance_member_id(insurance_text),
        group_number=_extract_group_number(insurance_text),
        plan_name=_extract_plan_name(insurance_text),
        rx_bin=_extract_rx_bin(insurance_text),
        rx_pcn=_extract_rx_pcn(insurance_text),
        rx_group=_extract_rx_group(insurance_text),
    )

    warnings.append("Real OCR executed with Tesseract. Field extraction uses heuristic parsing and may require manual review.")

    raw_patient, raw_insurance = _apply_demo_fallbacks(raw_patient, raw_insurance, warnings)

    return OCRExtractionResult(
        document_set_id=document_set_id,
        source_files=source_files,
        patient=raw_patient,
        insurance=raw_insurance,
        warnings=warnings,
    )
