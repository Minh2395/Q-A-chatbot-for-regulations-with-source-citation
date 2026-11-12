# Frontend

React, TypeScript, and Vite frontend for the AIK-01 legal-regulations assistant.

## Run locally

From this directory:

```powershell
npm install
npm run dev
```

By default, the frontend calls `http://127.0.0.1:8000/api/v1`. Set
`VITE_API_BASE_URL` when the backend is hosted elsewhere.

## Current backend integration

The frontend uses the APIs currently exposed by `backend/app/main.py`:

- `POST /api/v1` for chat
- `GET /api/v1/documents/catalog` and `POST /api/v1/documents/catalog` to list
  and create legal-document metadata records
- `POST /api/v1/documents/upload` for PDF, DOCX, HTML, and HTM uploads
- `GET /api/v1/documents/versions` to list uploaded versions, optionally
  filtered with `?trang_thai=Draft`, `Approved`, `Rejected`, or `Expired`
- `GET /api/v1/documents/versions/{ma_phien_ban}/chunks` to review extracted
  source text before approval
- `PUT /api/v1/documents/approve/{ma_phien_ban}` for explicit approval
- `GET /api/v1/evaluation/latest` for the latest evaluation report
- `DELETE /api/v1/evaluation/latest` to clear the latest dashboard report
  without deleting per-version reports; this is blocked while an evaluation
  is running
- `POST /api/v1/evaluation/run-latest` to schedule a benchmark for the newest
  active, approved document version (runs an unscored preliminary pass when
  legal references are still pending)
- `GET /api/v1/auth/me` to validate an upstream bearer token

New document versions remain in Draft until a specialist confirms approval.
The specialist workspace lets you create a catalog record, select it, upload a
file (maximum 25 MB), inspect the extracted chunks, and refresh the persistent
version list. The API validates the selected document ID against `TAI_LIEU`.
Any `ChuyenVienPhapChe` account can review extracted text and approve a Draft,
including the account that uploaded it. Approval activates the version, marks
the replaced active version `Expired`, and schedules evaluation in the
background.
Catalog creation, upload, and approval are written to the existing audit log.

To test the upload workflow, start SQL Server and the backend, ensure Ollama is
running with the configured embedding model, log in as `ChuyenVienPhapChe`, and
open **Tài liệu pháp chế**. Create a catalog record or select an existing one,
then upload a PDF, DOCX, HTML, or HTM file. Confirm extracted chunks in the
version list. The specialist who uploaded a version can review and approve it.

## Login and roles

The login form sends `TenDangNhap` and the raw password to
`POST /api/v1/auth/login`. The backend verifies the password against
`NGUOI_DUNG.MatKhauHash` and returns a short-lived HS256 bearer token. Password
hashes must use
`pbkdf2_sha256$<iterations>$<base64url-salt>$<base64url-digest>` with at least
600,000 PBKDF2-HMAC-SHA256 iterations. Configure `AUTH_JWT_SECRET` (at least
32 characters), `AUTH_JWT_ISSUER`, `AUTH_JWT_AUDIENCE`, and optionally
`AUTH_JWT_MAX_TTL_SECONDS` in the backend environment. The backend loads
`VaiTro` from SQL Server and never trusts a client-selected role. The frontend
keeps the token in tab memory only. Unsupported existing password-hash formats
are rejected and must be migrated through the authorized account process.

- All authenticated roles may use chat and their own conversation history.
- `ChuyenVienPhapChe` may upload, review, and approve documents, including
  versions they uploaded themselves.
- `QuanTriVien` may manage accounts, view audit logs with server-side
  pagination, view evaluation reports, and trigger a benchmark for the newest
  active approved version.

The evaluator reads `backend/data/evaluation_dataset_preliminary_matched.json`.
Its 50 questions are preliminary only: candidate matches are not verified legal
references, and expected answers, keywords, and review metadata still require
legal-officer completion. Questions without a suitable current source must be
matched to an approved document or removed/replaced during review. Evaluation
therefore records pending questions and does not publish official scores until
the benchmark references have been reviewed and verified against active
approved documents. Administrators may still run an unscored preliminary
retrieval/answer pass, which reports retrieval coverage and generated answers
without presenting them as official metrics. In a mixed dataset, only legally
verified questions are scored; pending questions remain unscored. Operational
benchmark counts (attempted/completed questions, qualified retrievals,
generated answers, refusals, and failures) are separate from quality scores.
An empty quality-score sample is reported as “Chưa có dữ liệu”, not zero.

The current rule-based score implementation compares an answer with verified
keywords and token-level F1, checks each punctuation-delimited claim against
retrieved source text, and validates each citation against the verified chunk,
article, version, and claim support. These are conservative lexical checks,
not an independent legal or natural-language entailment judgment: paraphrases
may be missed, and lexical overlap alone cannot establish legal equivalence.
Reports are written under `backend/reports/`.
