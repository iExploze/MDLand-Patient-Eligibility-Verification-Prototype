from ..schemas import (
    EligibilityVerificationRequest,
    EligibilitySummary,
    PharmacyInfo,
)


def verify_eligibility(request: EligibilityVerificationRequest) -> EligibilitySummary:
    """
    Simulated rule engine for insurance eligibility.
    This is intentionally simple for the prototype.
    """
    notes: list[str] = []

    payer = request.insurance.payer_name.strip().lower()
    member_id = request.insurance.member_id.strip()
    dob = request.patient.dob.strip()

    if not member_id or len(member_id) < 5:
        return EligibilitySummary(
            coverage_status="manual_review",
            copay_amount=None,
            pharmacy=None,
            notes=["Member ID is missing or too short."],
        )

    if len(dob) != 10 or dob.count("-") != 2:
        return EligibilitySummary(
            coverage_status="manual_review",
            copay_amount=None,
            pharmacy=None,
            notes=["DOB format is invalid. Expected YYYY-MM-DD."],
        )

    # Fake payer-based rules
    if "aetna" in payer:
        return EligibilitySummary(
            coverage_status="active",
            copay_amount=25,
            pharmacy=PharmacyInfo(
                bin=request.insurance.rx_bin or "610502",
                pcn=request.insurance.rx_pcn or "AETRX",
                group=request.insurance.rx_group or request.insurance.group_number,
            ),
            notes=["Eligibility verified through mock Aetna rule set."],
        )

    if "blue cross" in payer or "bcbs" in payer:
        return EligibilitySummary(
            coverage_status="active",
            copay_amount=35,
            pharmacy=PharmacyInfo(
                bin=request.insurance.rx_bin or "004336",
                pcn=request.insurance.rx_pcn or "ADV",
                group=request.insurance.rx_group or request.insurance.group_number,
            ),
            notes=["Eligibility verified through mock BCBS rule set."],
        )

    if "expired" in payer:
        return EligibilitySummary(
            coverage_status="inactive",
            copay_amount=None,
            pharmacy=None,
            notes=["Policy marked inactive by mock rule set."],
        )

    return EligibilitySummary(
        coverage_status="active",
        copay_amount=40,
        pharmacy=PharmacyInfo(
            bin=request.insurance.rx_bin,
            pcn=request.insurance.rx_pcn,
            group=request.insurance.rx_group or request.insurance.group_number,
        ),
        notes=["Eligibility verified through default mock rule set."],
    )