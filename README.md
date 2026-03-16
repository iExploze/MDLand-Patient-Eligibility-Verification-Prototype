# MDLand Patient Eligibility Verification Prototype

## Overview

The prototype supports two paths:

1. A direct structured verification path where a client submits patient and insurance data as JSON.
2. A document-driven path where a user uploads a driver's license and insurance card images, the backend extracts fields using OCR, validates and normalizes those fields, then runs the same verification pipeline.

At a high level, the system does this:

- Accept intake data.
- Normalize it into a canonical request model.
- Apply a simple rule-based eligibility decision.
- Generate a mock 271-like response string.
- Parse that mock 271 back into a structured response for display.

The frontend surfaces an immediate UI notification when verification completes so front-desk staff receive results in real time within the prototype flow.

The result is a full demoable loop with a clean separation between API orchestration, OCR/extraction, validation, eligibility logic, and EDI formatting/parsing.

## System Architecture

The application is a single-process FastAPI service with file-based storage for uploaded documents.

### Major components

- `backend/app/main.py`
  - FastAPI app entry point.
  - Registers routes.
  - Serves the static frontend.
  - Exposes the direct `/eligibility/verify` API.

- `backend/app/documents.py`
  - Router for document upload and extraction workflows.
  - Saves uploaded files to disk.
  - Orchestrates OCR, validation, eligibility verification, and response assembly.

- `backend/app/schemas.py`
  - Shared Pydantic models for request/response contracts and OCR intermediate data.

- `backend/app/services/ocr_service.py`
  - Loads uploaded images/PDFs.
  - Converts PDFs to images.
  - Preprocesses images for OCR.
  - Runs Tesseract OCR.
  - Uses regex and heuristic extraction to infer patient and insurance fields.
  - Applies demo fallbacks when OCR misses key values.

- `backend/app/services/validation_service.py`
  - Normalizes OCR output.
  - Validates required fields.
  - Builds the canonical `EligibilityVerificationRequest`.

- `backend/app/services/eligibility_service.py`
  - Mock eligibility rule engine.
  - Produces a structured eligibility summary based on simple payer-driven logic.

- `backend/app/services/edi_generator.py`
  - Converts the structured eligibility result into a simplified mock 271 string.

- `backend/app/services/edi_parser.py`
  - Parses that mock 271 string back into a JSON-friendly summary.

- `backend/app/static/index.html`
  - Single-file frontend UI.
  - Handles file upload, extraction requests, and rendering results.

- `backend/storage/uploads/`
  - File-based persistence for uploaded intake document sets.
  - Each upload is stored under a generated `document_set_id`.

### Architecture diagram

```mermaid
flowchart TD
    U[User] --> F[Static Frontend<br/>backend/app/static/index.html]

    subgraph FastAPI App
        M[main.py]
        D[documents.py router]
        S[schemas.py]
    end

    F -->|GET /| M
    F -->|GET /health| M
    F -->|POST /documents/upload| D
    F -->|POST /documents/extract/{document_set_id}| D
    F -->|POST /eligibility/verify| M

    subgraph Document Pipeline
        UP[Upload Validation + Save]
        OCR[ocr_service.py<br/>OCR + heuristic extraction]
        VAL[validation_service.py<br/>normalize + validate]
    end

    subgraph Eligibility Pipeline
        ELIG[eligibility_service.py<br/>mock rule engine]
        EDI_GEN[edi_generator.py<br/>build mock 271]
        EDI_PARSE[edi_parser.py<br/>parse mock 271]
    end

    D --> UP
    UP --> FS[(backend/storage/uploads)]
    D --> OCR
    FS --> OCR
    OCR -->|OCRExtractionResult| VAL
    VAL -->|EligibilityVerificationRequest| ELIG
    ELIG -->|EligibilitySummary| EDI_GEN
    EDI_GEN -->|raw_271| EDI_PARSE
    EDI_PARSE -->|EligibilitySummary| D

    M -->|EligibilityVerificationRequest| ELIG
    M --> EDI_GEN
    M --> EDI_PARSE

    S -.shared models.-> M
    S -.shared models.-> D
    S -.shared models.-> OCR
    S -.shared models.-> VAL
    S -.shared models.-> ELIG
    S -.shared models.-> EDI_GEN
    S -.shared models.-> EDI_PARSE

    D -->|DocumentExtractionResponse| F
    M -->|EligibilityVerificationResponse| F
```

## Request Flow

### 1. Direct structured verification

This flow is intended for callers that already have patient and insurance data in structured form.

1. Client sends `POST /eligibility/verify` with an `EligibilityVerificationRequest`.
2. The FastAPI app validates the payload using Pydantic models.
3. `verify_eligibility()` applies the mock business rules.
4. `generate_mock_271()` formats the decision into a simplified 271-like response.
5. `parse_mock_271()` converts that string back into a structured summary.
6. The API returns:
   - `raw_271`
   - `summary`

### 2. Document upload and extraction

This flow is the full intake demo.

1. User uploads three required files:
   - driver's license
   - insurance front
   - insurance back
2. `POST /documents/upload` validates file extensions and stores the files under a generated `document_set_id`.
3. User calls `POST /documents/extract/{document_set_id}`.
4. The backend:
   - locates the uploaded files
   - opens images or converts PDFs into images
   - preprocesses images
   - runs Tesseract OCR
   - extracts candidate fields using regex and heuristics
5. The validation layer normalizes names, dates, IDs, and required insurance fields.
6. The normalized request is sent through the same eligibility pipeline as the direct API.
7. The response includes:
   - source file metadata
   - extracted structured request
   - warnings
   - verification result

## FastAPI / Why Rule Engine / Why Tesseract

FastAPI is a good fit for this prototype for practical reasons:

- It is fast to build with.
- Pydantic models make request and response contracts explicit.
- It naturally supports JSON APIs plus file upload endpoints.
- Its routing style matches the small service-oriented structure of this codebase.
- It keeps the backend simple enough that the architecture remains easy to inspect.

In this project, FastAPI is doing exactly what it should do in a prototype:

- API definition
- input validation
- response modeling
- route composition
- lightweight orchestration

### rule engine

The eligibility logic is intentionally a small rule-based service instead of a database-backed workflow engine or an external payer integration.

- the purpose is to demonstrate control flow, not payer-specific correctness
- deterministic rules are easier to explain and test during a prototype phase
- the output is predictable, which helps when validating OCR and UI behavior
- it isolates the business decision point from OCR and transport concerns

The current `eligibility_service.py` is best understood as a placeholder decision engine. It gives the project a stable domain core without pretending to be a real adjudication or EDI eligibility system.

### Tesseract

Tesseract is used because it is local, accessible, and sufficient for a prototype OCR pipeline.

- it can run without an external paid OCR service
- it works on both images and PDFs once pages are rendered to images
- it allows basic preprocessing and OCR configuration tuning
- it is easy to integrate through `pytesseract`

In this prototype, Tesseract is paired with:

- image preprocessing through Pillow
- PDF page rendering through PyMuPDF
- heuristic field extraction through regex and line-based rules

This keeps the stack simple and transparent.

## Key Trade-offs

- Chose a modular monolith over microservices to keep the prototype easy to inspect, reason about, and run locally.
- Chose Tesseract over a managed OCR service to avoid external dependencies and keep the demo self-contained.
- Used a simplified mock 271 format instead of full ANSI X12 parsing to focus on end-to-end system flow and structured response handling.
- Used file-based storage instead of a database to reduce setup complexity and keep document workflow state obvious during evaluation.

## Security and Compliance Notes

This is a prototype, in a production setting, the system would require:

- encryption in transit and at rest
- access controls and authentication
- audit logging for document access and eligibility checks
- secure document retention and deletion policies

## Error Handling + Validation

The project has two main validation boundaries: API input validation and OCR-derived field validation.

### API validation

Pydantic models in `backend/app/schemas.py` validate:

- required patient fields
- required insurance fields
- response shape consistency

For the direct `/eligibility/verify` endpoint, FastAPI and Pydantic handle malformed payloads before business logic runs.

### Upload validation

The document upload route checks:

- each required file is present
- each file has a filename
- the extension is one of:
  - `.png`
  - `.jpg`
  - `.jpeg`
  - `.pdf`

If upload fails mid-operation, the partially created target directory is deleted.

### OCR and extraction validation

The OCR service handles:

- missing document sets
- missing required document roles
- missing local Tesseract installation
- low OCR output quality warnings

The validation service handles:

- string cleanup
- date normalization
- ID normalization
- missing required extracted fields
- warnings for suspicious values

If extracted data cannot be normalized into a valid eligibility request, the route returns a `400`.

### HTTP error behavior

Current error mapping is straightforward:

- `404`
  - missing document set
  - missing required document file

- `400`
  - invalid upload file type
  - OCR-related validation failures
  - extracted fields missing required data
  - Tesseract not installed or configured

- `500`
  - unexpected failures while saving uploaded files

### Warning behavior

Not all issues are treated as hard failures. Some conditions are surfaced as warnings instead:

- very little OCR text extracted
- normalized DOB differs from raw OCR text
- unusually short member ID
- heuristic extraction uncertainty
- demo fallback values used

That split is intentional. In a prototype, preserving visibility into uncertain extraction is more useful than aggressively rejecting every imperfect result.

## Known Limitations

This repository is a prototype, and the constraints are important.

### Domain limitations

- The eligibility decision logic is not connected to real payers.
- The 271 output is not real ANSI X12 271.
- The parser only understands the simplified mock format produced by this project.

### OCR limitations

- OCR quality depends heavily on image quality and orientation.
- Field extraction is heuristic and regex-based, not model-driven.
- Name and address extraction can be fragile on real-world IDs and cards.
- Tesseract output can vary significantly across machines and document types.

### Architecture limitations

- No database
- No authentication
- No audit logging
- No background jobs
- No queue for OCR workloads
- No retry or idempotency handling
- No test suite in the repository at this time

### Prototype-specific behavior

- The OCR pipeline can inject demo fallback values for missing critical fields.
- That makes the application more demoable, but less trustworthy as a real extraction workflow.
- The frontend is a single static file and is not structured as a larger client application.

## How to Run Locally

### Prerequisites

- Python 3.11+ recommended
- Tesseract OCR installed locally
- Optional: set `TESSERACT_CMD` if Tesseract is not on your `PATH`

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Tesseract if needed

If `tesseract` is already on your `PATH`, you can skip this.

Otherwise set:

```powershell
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 4. Run the app

From the repository root:

```powershell
python -m uvicorn backend.app.main:app --reload
```

### 5. Open the UI

Visit:

```text
http://127.0.0.1:8000/
```

### 6. Health check

You can verify the backend is running at:

```text
http://127.0.0.1:8000/health
```

## API Summary

### `GET /`

Serves the static frontend.

### `GET /health`

Returns:

```json
{ "status": "ok" }
```

### `POST /eligibility/verify`

Accepts structured patient and insurance data and returns:

- `raw_271`
- parsed `summary`

### `POST /documents/upload`

Accepts multipart form-data with:

- `driver_license`
- `insurance_front`
- `insurance_back`

Returns a generated `document_set_id`.

### `POST /documents/extract/{document_set_id}`

Runs OCR, validation, verification, and mock 271 generation/parsing for an uploaded document set.

## Next Steps

- replace demo fallbacks with explicit manual review handling
- add automated tests around OCR normalization and rule outputs
- move from heuristic parsing toward document-specific extraction templates
