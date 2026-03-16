from pathlib import Path

from ..schemas import (
    EligibilityVerificationRequest,
    InsuranceInfo,
    Patient,
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


def extract_document_set(
    document_set_id: str,
) -> tuple[EligibilityVerificationRequest, list[UploadedDocumentInfo], list[str]]:
    """
    Mock extraction service.

    Reads the uploaded document set from disk, verifies the expected files exist,
    and returns structured patient + insurance data.
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

    # Mock extraction logic for now.
    # You can later replace this with Tesseract / cloud OCR / document AI / vision model.
    payer_name = "Aetna"
    member_id = "ABC123456"
    group_number = "GRP1001"
    plan_name = "Gold PPO"
    rx_bin = "610502"
    rx_pcn = "AETRX"
    rx_group = "RX1001"

    all_filenames = " ".join(path.name.lower() for path in found_files.values())

    if "bcbs" in all_filenames or "blue" in all_filenames:
        payer_name = "Blue Cross Blue Shield"
        member_id = "BCBS998877"
        group_number = "BC1001"
        plan_name = "Silver PPO"
        rx_bin = "004336"
        rx_pcn = "ADV"
        rx_group = "BCBSRX1"
    elif "expired" in all_filenames:
        payer_name = "Expired Health Plan"

    extracted_request = EligibilityVerificationRequest(
        patient=Patient(
            first_name="Ian",
            last_name="Zhang",
            dob="2004-09-10",
            address="Toronto, ON",
            license_number="Z1234567",
        ),
        insurance=InsuranceInfo(
            payer_name=payer_name,
            member_id=member_id,
            group_number=group_number,
            plan_name=plan_name,
            rx_bin=rx_bin,
            rx_pcn=rx_pcn,
            rx_group=rx_group,
        ),
    )

    warnings.append(
        "Using mock OCR extraction. Replace services/ocr_service.py with a real OCR provider later."
    )

    return extracted_request, source_files, warnings