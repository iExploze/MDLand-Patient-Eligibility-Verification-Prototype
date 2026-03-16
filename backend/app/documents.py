from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from .schemas import (
    DocumentExtractionResponse,
    DocumentUploadResponse,
    EligibilityVerificationResponse,
    UploadedDocumentInfo,
)
from .services.edi_generator import generate_mock_271
from .services.edi_parser import parse_mock_271
from .services.eligibility_service import verify_eligibility
from .services.ocr_service import extract_raw_document_data
from .services.validation_service import validate_and_build_request

router = APIRouter(prefix="/documents", tags=["documents"])

BACKEND_DIR = Path(__file__).resolve().parents[1]
UPLOADS_ROOT = BACKEND_DIR / "storage" / "uploads"

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}


def _validate_upload(upload: UploadFile, role: str) -> str:
    if not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{role} file is missing a filename.",
        )

    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{role} has unsupported file type '{ext}'. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )
    return ext


def _save_upload_file(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    driver_license: UploadFile = File(...),
    insurance_front: UploadFile = File(...),
    insurance_back: UploadFile = File(...),
):
    document_set_id = str(uuid4())
    target_dir = UPLOADS_ROOT / document_set_id

    uploads = [
        ("driver_license", driver_license),
        ("insurance_front", insurance_front),
        ("insurance_back", insurance_back),
    ]

    saved_files: list[UploadedDocumentInfo] = []

    try:
        for role, upload in uploads:
            ext = _validate_upload(upload, role)
            saved_filename = f"{role}{ext}"
            destination = target_dir / saved_filename

            _save_upload_file(upload, destination)

            relative_path = destination.relative_to(BACKEND_DIR).as_posix()

            saved_files.append(
                UploadedDocumentInfo(
                    role=role,
                    original_filename=upload.filename,
                    saved_filename=saved_filename,
                    relative_path=relative_path,
                )
            )

    except Exception as exc:
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)

        if isinstance(exc, HTTPException):
            raise exc

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded documents.",
        ) from exc

    finally:
        for _, upload in uploads:
            upload.file.close()

    return DocumentUploadResponse(
        document_set_id=document_set_id,
        files=saved_files,
        message="Documents uploaded successfully.",
    )


@router.post("/extract/{document_set_id}", response_model=DocumentExtractionResponse)
async def extract_documents(document_set_id: str):
    try:
        raw_result = extract_raw_document_data(document_set_id)
        extracted_request, warnings = validate_and_build_request(raw_result)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    summary = verify_eligibility(extracted_request)
    raw_271 = generate_mock_271(extracted_request, summary)
    parsed_summary = parse_mock_271(raw_271)

    verification_result = EligibilityVerificationResponse(
        raw_271=raw_271,
        summary=parsed_summary,
    )

    return DocumentExtractionResponse(
        document_set_id=document_set_id,
        source_files=raw_result.source_files,
        extracted_request=extracted_request,
        warnings=warnings,
        verification_result=verification_result,
    )
