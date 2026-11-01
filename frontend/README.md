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
  filtered with `?trang_thai=Draft`
- `GET /api/v1/documents/versions/{ma_phien_ban}/chunks` to review extracted
  source text before approval
- `PUT /api/v1/documents/approve/{ma_phien_ban}` for explicit approval
- `GET /api/v1/evaluation/latest` for the latest evaluation report
- `GET /api/v1/auth/me` to validate an upstream bearer token

New document versions remain in Draft until a specialist confirms approval.
The specialist workspace lets you create a catalog record, select it, upload a
file (maximum 25 MB), inspect the extracted chunks, and refresh the persistent
version list. The API validates the selected document ID against `TAI_LIEU`.
Only a different `ChuyenVienPhapChe` account can approve an uploader's Draft;
approval activates the version and schedules evaluation in the background.
Catalog creation, upload, and approval are written to the existing audit log.

To test the upload workflow, start SQL Server and the backend, ensure Ollama is
running with the configured embedding model, log in as `ChuyenVienPhapChe`, and
open **Tài liệu pháp chế**. Create a catalog record or select an existing one,
then upload a PDF, DOCX, HTML, or HTM file. Confirm extracted chunks in the
version list. Approval requires a second specialist account because
self-approval is intentionally rejected.

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
- `ChuyenVienPhapChe` may upload and approve documents; the uploader cannot
  approve their own version.
- `QuanTriVien` may access evaluation reports.

User CRUD and system-wide audit-log APIs remain unavailable. The admin screen
reads the latest evaluation report when the evaluation API is reachable.

The benchmark at `backend/data/evaluation_dataset.json` currently contains 50
draft questions pending legal review without expected answers or source chunk
references. Automatic evaluation therefore records a pending-verification
report and does not run RAG or publish official scores until the references
have been reviewed and verified against active approved documents. Reports are
written under `backend/reports/`.
