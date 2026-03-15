from fastapi import FastAPI
from .schemas import (
    EligibilityVerificationRequest,
    EligibilityVerificationResponse,
)
from .services.eligibility_service import verify_eligibility
from .services.edi_generator import generate_mock_271
from .services.edi_parser import parse_mock_271

app = FastAPI(
    title="MDLand Eligibility Verification Prototype",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post(
    "/eligibility/verify",
    response_model=EligibilityVerificationResponse,
)
def eligibility_verify(request: EligibilityVerificationRequest):
    summary = verify_eligibility(request)
    raw_271 = generate_mock_271(request, summary)
    parsed_summary = parse_mock_271(raw_271)

    return EligibilityVerificationResponse(
        raw_271=raw_271,
        summary=parsed_summary,
    )