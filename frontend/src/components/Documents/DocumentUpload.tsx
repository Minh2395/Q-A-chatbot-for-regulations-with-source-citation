import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  approveDocumentVersion,
  getApiErrorMessage,
  uploadDocument,
} from "../../services/api";
import type { UploadResponse } from "../../services/api";

interface DocumentUploadProps {
  maNd: string;
  onSuccess?: () => void;
}

interface ProcessedDocument {
  result: UploadResponse;
  filename: string;
  maTaiLieu: string;
  previewUrl: string;
}

function getFileExtension(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? "";
}

export default function DocumentUpload({
  maNd,
  onSuccess,
}: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const documentPreviewUrls = useRef(new Set<string>());
  const [maTaiLieu, setMaTaiLieu] = useState("");
  const [soPhienBan, setSoPhienBan] = useState("v1.0");
  const [uploading, setUploading] = useState(false);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<ProcessedDocument[]>([]);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(
    () => () => {
      documentPreviewUrls.current.forEach((url) => URL.revokeObjectURL(url));
    },
    [],
  );

  const handleFileChange = (selectedFile: File | null) => {
    setFile(selectedFile);
    setError("");
    setSuccessMessage("");
  };

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || uploading || approvingId) return;

    const extension = getFileExtension(file.name);
    if (!["pdf", "docx", "html", "htm"].includes(extension)) {
      setError("Backend hỗ trợ file PDF, DOCX, HTML và HTM.");
      return;
    }

    if (!maTaiLieu.trim() || !soPhienBan.trim()) {
      setError("Vui lòng nhập mã tài liệu và số phiên bản.");
      return;
    }

    setUploading(true);
    setError("");
    setSuccessMessage("");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("ma_tai_lieu", maTaiLieu.trim());
      formData.append("so_phien_ban", soPhienBan.trim());
      formData.append("ma_nd", maNd);

      const data = await uploadDocument(formData);
      const documentPreviewUrl = URL.createObjectURL(file);
      documentPreviewUrls.current.add(documentPreviewUrl);
      setDocuments((previous) => [
        {
          result: data,
          filename: file.name,
          maTaiLieu: maTaiLieu.trim(),
          previewUrl: documentPreviewUrl,
        },
        ...previous,
      ]);
      setSuccessMessage(data.message || "Tải lên và xử lý tài liệu thành công.");
      onSuccess?.();
    } catch (uploadError: unknown) {
      setError(
        getApiErrorMessage(uploadError, "Không thể tải lên tài liệu."),
      );
    } finally {
      setUploading(false);
    }
  };

  const handleApprove = async (document: ProcessedDocument) => {
    const maPhienBan = document.result.ma_phien_ban;
    if (!maPhienBan || approvingId) return;

    const confirmed = window.confirm(
      `Xác nhận đã rà soát và phê duyệt phiên bản ${maPhienBan}?`,
    );
    if (!confirmed) return;

    setApprovingId(maPhienBan);
    setError("");
    setSuccessMessage("");

    try {
      const data = await approveDocumentVersion(maPhienBan);
      setDocuments((previous) =>
        previous.map((item) =>
          item.result.ma_phien_ban === maPhienBan
            ? {
                ...item,
                result: {
                  ...item.result,
                  trang_thai: data.trang_thai || "Approved",
                },
              }
            : item,
        ),
      );
      setSuccessMessage(data.message || "Đã phê duyệt tài liệu.");
    } catch (approvalError: unknown) {
      setError(
        getApiErrorMessage(approvalError, "Không thể phê duyệt tài liệu."),
      );
    } finally {
      setApprovingId(null);
    }
  };

  const fileExtension = file ? getFileExtension(file.name) : "";

  return (
    <div className="document-workspace">
      <section className="surface-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">QUẢN LÝ TRI THỨC</p>
            <h2>Nạp tài liệu pháp quy</h2>
          </div>
          <span className="info-chip">Người nạp: {maNd}</span>
        </div>

        <p className="muted">
          Tài liệu được xử lý thành các đoạn và lưu ở trạng thái Draft. Chỉ thao
          tác phê duyệt bên dưới mới kích hoạt phiên bản.
        </p>

        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {successMessage && (
          <div className="notice notice-success" role="status">{successMessage}</div>
        )}

        <form onSubmit={handleUpload} className="document-form">
          <label className="file-picker">
            <span className="field-label">Tệp pháp quy hoặc tài liệu tham khảo</span>
            <input
              type="file"
              accept=".pdf,.docx,.html,.htm,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html"
              onChange={(event) =>
                handleFileChange(event.target.files?.[0] ?? null)
              }
              disabled={uploading || Boolean(approvingId)}
              required
            />
            <span className="field-hint">Định dạng được backend hỗ trợ: PDF, DOCX, HTML, HTM.</span>
          </label>

          <div className="form-grid">
            <label>
              Mã tài liệu
              <input
                value={maTaiLieu}
                onChange={(event) => setMaTaiLieu(event.target.value)}
                placeholder="TL_DATDAI_2026"
                required
                disabled={uploading || Boolean(approvingId)}
              />
            </label>
            <label>
              Số phiên bản
              <input
                value={soPhienBan}
                onChange={(event) => setSoPhienBan(event.target.value)}
                placeholder="v1.0"
                required
                disabled={uploading || Boolean(approvingId)}
              />
            </label>
          </div>

          <button
            className="primary-button"
            type="submit"
            disabled={!file || uploading || Boolean(approvingId)}
          >
            {uploading ? "Đang tải lên và xử lý…" : "Tải lên và xử lý"}
          </button>
        </form>

        {file && (
          <div className="file-summary">
            <span className="file-type-icon" aria-hidden="true">▤</span>
            <div>
              <strong>{file.name}</strong>
              <span>{(file.size / 1024).toFixed(1)} KB · {fileExtension.toUpperCase()}</span>
            </div>
          </div>
        )}
      </section>

      {documents.map((document) => {
        const { result: processed } = document;
        const documentExtension = getFileExtension(document.filename);
        const isApproving = approvingId === processed.ma_phien_ban;

        return (
          <section
            className="surface-card review-card"
            key={processed.ma_phien_ban}
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">RÀ SOÁT TRƯỚC KHI KÍCH HOẠT</p>
                <h2>{document.filename}</h2>
              </div>
              <span
                className={`status-pill ${processed.trang_thai === "Approved" ? "status-approved" : "status-draft"}`}
              >
                {processed.trang_thai}
              </span>
            </div>

            <dl className="document-details">
              <div><dt>Mã tài liệu</dt><dd>{document.maTaiLieu}</dd></div>
              <div><dt>Mã phiên bản</dt><dd>{processed.ma_phien_ban}</dd></div>
              <div><dt>Số phiên bản</dt><dd>{processed.so_phien_ban}</dd></div>
              <div><dt>Số đoạn đã xử lý</dt><dd>{processed.so_doan}</dd></div>
              <div><dt>Trạng thái hiện tại</dt><dd>{processed.trang_thai}</dd></div>
            </dl>

            {["pdf", "html", "htm"].includes(documentExtension) ? (
              <div className="document-preview">
                <p className="field-label">Bản gốc để đối chiếu</p>
                <iframe
                  title={`Bản xem trước ${document.filename}`}
                  src={document.previewUrl}
                  sandbox=""
                />
                <p className="field-hint">
                  Đây là bản gốc trong trình duyệt. Backend hiện chỉ trả mã phiên
                  bản và số đoạn, chưa có API trả nội dung từng đoạn đã trích xuất.
                </p>
              </div>
            ) : (
              <div className="notice notice-info">
                Trình duyệt không xem trực tiếp DOCX.{" "}
                <a href={document.previewUrl} download={document.filename}>
                  Tải bản gốc để rà soát
                </a>
                . Backend chưa cung cấp nội dung các đoạn đã trích xuất.
              </div>
            )}

            {processed.trang_thai === "Draft" && (
              <button
                type="button"
                onClick={() => handleApprove(document)}
                disabled={uploading || Boolean(approvingId)}
                className="approve-button"
              >
                {isApproving
                  ? "Đang phê duyệt…"
                  : "Tôi đã rà soát — Phê duyệt"}
              </button>
            )}
          </section>
        );
      })}
    </div>
  );
}
