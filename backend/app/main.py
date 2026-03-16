from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path

from .documents import router as documents_router
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

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app.include_router(documents_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


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