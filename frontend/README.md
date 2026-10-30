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
- `POST /api/v1/documents/upload` for PDF, DOCX, HTML, and HTM uploads
- `PUT /api/v1/documents/approve/{ma_phien_ban}` for explicit approval

New document versions remain in Draft until a specialist confirms approval.
The current upload response includes the version ID, status, and processed
chunk count, but there is no endpoint to list saved documents or read extracted
chunk content. The specialist screen therefore previews the selected original
file locally and identifies this backend limitation; it does not claim that a
local preview is the extracted content.

## Roles and backend limitations

The navigation is filtered by the selected `VaiTro` value:

- `NguoiDung`: chat
- `ChuyenVienPhapChe`: chat and document upload/approval
- `QuanTriVien`: chat and administration status

This repository's backend does not currently expose authentication or role
verification. The role chooser is only a frontend workspace/demo selector and
must not be treated as secure authorization. Likewise, user CRUD, system-wide
audit logs, and model evaluation APIs are not registered by the backend, so the
admin screen reports those capabilities as unavailable rather than showing
fabricated data.

The backend also does not currently expose evaluation results or a labeled
evaluation dataset. Accuracy, faithfulness, and citation correctness cannot be
calculated reliably until those data and APIs exist.
