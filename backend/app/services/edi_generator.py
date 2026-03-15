from ..schemas import EligibilityVerificationRequest, EligibilitySummary


def generate_mock_271(
    request: EligibilityVerificationRequest,
    summary: EligibilitySummary,
) -> str:
    """
    Generates a simplified mock 271-like response.
    Not real X12, but structured enough for the prototype parser.
    """
    pharmacy = summary.pharmacy or None

    segments = [
        "ST*271*0001",
        f"NM1*IL*1*{request.patient.last_name}*{request.patient.first_name}",
        f"DMG*D8*{request.patient.dob.replace('-', '')}",
        f"PAYER*{request.insurance.payer_name}",
        f"MEMBER*{request.insurance.member_id}",
        f"EB*1*{summary.coverage_status.upper()}",
    ]

    if summary.copay_amount is not None:
        segments.append(f"COPAY*{summary.copay_amount}")

    if pharmacy:
        if pharmacy.bin:
            segments.append(f"RX*BIN*{pharmacy.bin}")
        if pharmacy.pcn:
            segments.append(f"RX*PCN*{pharmacy.pcn}")
        if pharmacy.group:
            segments.append(f"RX*GRP*{pharmacy.group}")

    for note in summary.notes:
        segments.append(f"MSG*{note}")

    segments.append("SE*END")

    return "~".join(segments) + "~"