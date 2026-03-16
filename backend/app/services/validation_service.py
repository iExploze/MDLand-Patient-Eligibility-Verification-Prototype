import re
from datetime import datetime

from ..schemas import (
    EligibilityVerificationRequest,
    InsuranceInfo,
    OCRExtractionResult,
    Patient,
)

DATE_PATTERNS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%Y/%m/%d",
]


def _clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _normalize_name(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    if not cleaned:
        return None
    return cleaned.title()


def _normalize_dob(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    if not cleaned:
        return None

    for pattern in DATE_PATTERNS:
        try:
            parsed = datetime.strptime(cleaned, pattern)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _normalize_member_id(value: str | None) -> str | None:
    cleaned = _clean_string(value)
    if not cleaned:
        return None
    return cleaned.upper().replace(" ", "")


def validate_and_build_request(
    raw_result: OCRExtractionResult,
) -> tuple[EligibilityVerificationRequest, list[str]]:
    """
    Converts raw OCR output into the structured request model used by the eligibility API.
    Returns the validated request plus validation warnings.
    """
    warnings = list(raw_result.warnings)

    first_name = _normalize_name(raw_result.patient.first_name)
    last_name = _normalize_name(raw_result.patient.last_name)
    dob = _normalize_dob(raw_result.patient.dob)
    address = _clean_string(raw_result.patient.address)
    license_number = _normalize_member_id(raw_result.patient.license_number)

    payer_name = _clean_string(raw_result.insurance.payer_name)
    member_id = _normalize_member_id(raw_result.insurance.member_id)
    group_number = _normalize_member_id(raw_result.insurance.group_number)
    plan_name = _clean_string(raw_result.insurance.plan_name)
    rx_bin = _normalize_member_id(raw_result.insurance.rx_bin)
    rx_pcn = _normalize_member_id(raw_result.insurance.rx_pcn)
    rx_group = _normalize_member_id(raw_result.insurance.rx_group)

    missing_fields: list[str] = []

    if not first_name:
        missing_fields.append("patient.first_name")
    if not last_name:
        missing_fields.append("patient.last_name")
    if not dob:
        missing_fields.append("patient.dob")
    if not payer_name:
        missing_fields.append("insurance.payer_name")
    if not member_id:
        missing_fields.append("insurance.member_id")

    if missing_fields:
        raise ValueError(
            "Missing or invalid required extracted fields: " + ", ".join(missing_fields)
        )

    if raw_result.patient.dob and dob != raw_result.patient.dob:
        warnings.append(
            f"DOB normalized from '{raw_result.patient.dob}' to '{dob}'."
        )

    if member_id and len(member_id) < 5:
        warnings.append("Member ID looks unusually short; consider manual review.")

    request = EligibilityVerificationRequest(
        patient=Patient(
            first_name=first_name,
            last_name=last_name,
            dob=dob,
            address=address,
            license_number=license_number,
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

    return request, warnings