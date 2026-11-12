import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  createDocumentCatalogItem,
  getApiErrorMessage,
  getDocumentCatalog,
  uploadDocument,
} from "../../services/api";
import type { DocumentCatalogItem } from "../../services/api";
import VersionManager from "./VersionManager";

interface DocumentUploadProps {
  maNd: string;
  refreshKey: number;
  onSuccess?: () => void;
}

function getFileExtension(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? "";
}

export default function DocumentUpload({
  maNd,
  refreshKey,
  onSuccess,
}: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [catalog, setCatalog] = useState<DocumentCatalogItem[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [versionNumber, setVersionNumber] = useState("v1.0");
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [creatingCatalogItem, setCreatingCatalogItem] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState("LUAT");
  const [newField, setNewField] = useState("");
  const [newIssuer, setNewIssuer] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const refreshData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const documents = await getDocumentCatalog();
      setCatalog(documents);
      setSelectedDocumentId((current) =>
        documents.some((document) => document.ma_tai_lieu === current)
          ? current
          : documents[0]?.ma_tai_lieu ?? "",
      );
    } catch (loadError: unknown) {
      setError(
        getApiErrorMessage(loadError, "Không thể tải dữ liệu tài liệu."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshData]);

  const handleCreateCatalogItem = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    if (creatingCatalogItem) return;

    setCreatingCatalogItem(true);
    setError("");
    setSuccessMessage("");
    try {
      const item = await createDocumentCatalogItem({
        tieu_de: newTitle.trim(),
        loai_van_ban: newType,
        linh_vuc: newField.trim() || undefined,
        co_quan_ban_hanh: newIssuer.trim() || undefined,
      });
      setCatalog((previous) => [...previous, item]);
      setSelectedDocumentId(item.ma_tai_lieu);
      setNewTitle("");
      setNewField("");
      setNewIssuer("");
      setSuccessMessage(
        `Đã tạo hồ sơ "${item.tieu_de}" (${item.ma_tai_lieu}). Hãy tải phiên bản tài liệu lên.`,
      );
    } catch (createError: unknown) {
      setError(
        getApiErrorMessage(createError, "Không thể tạo hồ sơ tài liệu."),
      );
    } finally {
      setCreatingCatalogItem(false);
    }
  };

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || uploading) return;

    const extension = getFileExtension(file.name);
    if (!["pdf", "docx", "html", "htm"].includes(extension)) {
      setError("Backend hỗ trợ file PDF, DOCX, HTML và HTM.");
      return;
    }
    if (!selectedDocumentId || !versionNumber.trim()) {
      setError("Vui lòng chọn hồ sơ tài liệu và nhập số phiên bản.");
      return;
    }

    setUploading(true);
    setError("");
    setSuccessMessage("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("ma_tai_lieu", selectedDocumentId);
      formData.append("so_phien_ban", versionNumber.trim());
      formData.append("ma_nd", maNd);

      const result = await uploadDocument(formData);
      setSuccessMessage(
        `${result.message} Phiên bản ${result.ma_phien_ban} đang ở trạng thái Draft; cần chuyên viên khác rà soát và phê duyệt.`,
      );
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await refreshData();
      onSuccess?.();
    } catch (uploadError: unknown) {
      setError(
        getApiErrorMessage(uploadError, "Không thể tải lên tài liệu."),
      );
    } finally {
      setUploading(false);
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
          Tạo hoặc chọn hồ sơ tài liệu, tải PDF/DOCX/HTML lên để trích xuất đoạn
          văn bản. Phiên bản mới luôn ở trạng thái Draft và chỉ được kích hoạt
          sau khi một chuyên viên khác phê duyệt.
        </p>

        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {successMessage && (
          <div className="notice notice-success" role="status">{successMessage}</div>
        )}

        <details className="catalog-create">
          <summary>Tạo hồ sơ cho tài liệu mới</summary>
          <form onSubmit={handleCreateCatalogItem} className="document-form">
            <div className="form-grid">
              <label>
                Tên tài liệu
                <input
                  value={newTitle}
                  onChange={(event) => setNewTitle(event.target.value)}
                  maxLength={255}
                  required
                  disabled={creatingCatalogItem || uploading}
                />
              </label>
              <label>
                Loại văn bản
                <select
                  value={newType}
                  onChange={(event) => setNewType(event.target.value)}
                  disabled={creatingCatalogItem || uploading}
                >
                  <option value="LUAT">Luật</option>
                  <option value="NGHI_DINH">Nghị định</option>
                  <option value="THONG_TU">Thông tư</option>
                  <option value="QUYET_DINH">Quyết định</option>
                  <option value="VAN_BAN_KHAC">Văn bản khác</option>
                </select>
              </label>
              <label>
                Lĩnh vực (không bắt buộc)
                <input
                  value={newField}
                  onChange={(event) => setNewField(event.target.value)}
                  maxLength={100}
                  disabled={creatingCatalogItem || uploading}
                />
              </label>
              <label>
                Cơ quan ban hành (không bắt buộc)
                <input
                  value={newIssuer}
                  onChange={(event) => setNewIssuer(event.target.value)}
                  maxLength={150}
                  disabled={creatingCatalogItem || uploading}
                />
              </label>
            </div>
            <button
              className="secondary-button"
              type="submit"
              disabled={creatingCatalogItem || uploading}
            >
              {creatingCatalogItem ? "Đang tạo hồ sơ…" : "Tạo hồ sơ tài liệu"}
            </button>
          </form>
        </details>

        <form onSubmit={handleUpload} className="document-form">
          <label>
            Hồ sơ tài liệu
            <select
              value={selectedDocumentId}
              onChange={(event) => setSelectedDocumentId(event.target.value)}
              required
              disabled={loading || uploading}
            >
              <option value="">-- Chọn tài liệu --</option>
              {catalog.map((document) => (
                <option key={document.ma_tai_lieu} value={document.ma_tai_lieu}>
                  {document.tieu_de} · {document.ma_tai_lieu}
                </option>
              ))}
            </select>
          </label>
          {selectedDocumentId && (
            <p className="field-hint">
              {catalog.find(
                (document) => document.ma_tai_lieu === selectedDocumentId,
              )?.loai_van_ban}
              {catalog.find(
                (document) => document.ma_tai_lieu === selectedDocumentId,
              )?.linh_vuc
                ? ` · ${catalog.find((document) => document.ma_tai_lieu === selectedDocumentId)?.linh_vuc}`
                : ""}
            </p>
          )}

          <div className="form-grid">
            <label>
              Số phiên bản
              <input
                value={versionNumber}
                onChange={(event) => setVersionNumber(event.target.value)}
                maxLength={50}
                placeholder="v1.0"
                required
                disabled={uploading}
              />
            </label>
            <label className="file-picker">
              Tệp pháp quy hoặc tài liệu tham khảo
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.html,.htm,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                disabled={uploading}
                required
              />
              <span className="field-hint">
                Chỉ hỗ trợ PDF, DOCX, HTML và HTM; giới hạn 25 MB.
              </span>
            </label>
          </div>

          <button
            className="primary-button"
            type="submit"
            disabled={!file || !selectedDocumentId || uploading}
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

      <VersionManager refreshKey={refreshKey} />
    </div>
  );
}
