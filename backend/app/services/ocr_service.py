from pathlib import Path

from ..schemas import (
    OCRExtractionResult,
    RawInsuranceExtraction,
    RawPatientExtraction,
    UploadedDocumentInfo,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOADS_ROOT = BACKEND_DIR / "storage" / "uploads"

REQUIRED_ROLES = ["driver_license", "insurance_front", "insurance_back"]


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


def extract_raw_document_data(document_set_id: str) -> OCRExtractionResult:
    """
    Mock OCR layer.

    Reads the uploaded document set from disk and returns raw extracted fields.
    This is intentionally separated from validation/normalization.
    """
    document_dir = UPLOADS_ROOT / document_set_id

    if not document_dir.exists() or not document_dir.is_dir():
        raise FileNotFoundError(f"Document set '{document_set_id}' was not found.")

    source_files: list[UploadedDocumentInfo] = []
    warnings: list[str] = []
    found_files: dict[str, Path] = {}

    for role in REQUIRED_ROLES:
        file_path = _find_file_for_role(document_dir, role)
        if file_path is None:
            raise FileNotFoundError(
                f"Required file for role '{role}' was not found in document set '{document_set_id}'."
            )

        found_files[role] = file_path
        source_files.append(_build_uploaded_document_info(file_path))

    combined_names = " ".join(path.name.lower() for path in found_files.values())

    # Mock patient extraction
    raw_patient = RawPatientExtraction(
        first_name="Ian",
        last_name="Zhang",
        dob="2004-09-10",
        address="Toronto, ON",
        license_number="Z1234567",
    )

    # Mock insurance extraction with simple filename-based branching
    raw_insurance = RawInsuranceExtraction(
        payer_name="Aetna",
        member_id="ABC123456",
        group_number="GRP1001",
        plan_name="Gold PPO",
        rx_bin="610502",
        rx_pcn="AETRX",
        rx_group="RX1001",
    )

    if "bcbs" in combined_names or "blue" in combined_names:
        raw_insurance = RawInsuranceExtraction(
            payer_name="Blue Cross Blue Shield",
            member_id="BCBS998877",
            group_number="BC1001",
            plan_name="Silver PPO",
            rx_bin="004336",
            rx_pcn="ADV",
            rx_group="BCBSRX1",
        )
    elif "expired" in combined_names:
        raw_insurance = RawInsuranceExtraction(
            payer_name="Expired Health Plan",
            member_id="ABC123456",
            group_number="GRP1001",
            plan_name="Terminated Plan",
            rx_bin=None,
            rx_pcn=None,
            rx_group=None,
        )

    warnings.append(
        "Using mock OCR extraction. Replace services/ocr_service.py with a real OCR provider later."
    )

    return OCRExtractionResult(
        document_set_id=document_set_id,
        source_files=source_files,
        patient=raw_patient,
        insurance=raw_insurance,
        warnings=warnings,
    )