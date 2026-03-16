from typing import Optional, Literal
from pydantic import BaseModel, Field


class Patient(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    dob: str = Field(..., description="YYYY-MM-DD")
    address: Optional[str] = None
    license_number: Optional[str] = None


class InsuranceInfo(BaseModel):
    payer_name: str = Field(..., min_length=1)
    member_id: str = Field(..., min_length=1)
    group_number: Optional[str] = None
    plan_name: Optional[str] = None
    rx_bin: Optional[str] = None
    rx_pcn: Optional[str] = None
    rx_group: Optional[str] = None


class EligibilityVerificationRequest(BaseModel):
    patient: Patient
    insurance: InsuranceInfo


class PharmacyInfo(BaseModel):
    bin: Optional[str] = None
    pcn: Optional[str] = None
    group: Optional[str] = None


class EligibilitySummary(BaseModel):
    coverage_status: Literal["active", "inactive", "manual_review"]
    copay_amount: Optional[int] = None
    pharmacy: Optional[PharmacyInfo] = None
    notes: list[str] = []


class EligibilityVerificationResponse(BaseModel):
    raw_271: str
    summary: EligibilitySummary


class UploadedDocumentInfo(BaseModel):
    role: str
    original_filename: str
    saved_filename: str
    relative_path: str


class DocumentUploadResponse(BaseModel):
    document_set_id: str
    files: list[UploadedDocumentInfo]
    message: str


class DocumentExtractionResponse(BaseModel):
    document_set_id: str
    source_files: list[UploadedDocumentInfo]
    extracted_request: EligibilityVerificationRequest
    warnings: list[str] = []
    verification_result: EligibilityVerificationResponse