import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  approveDocumentVersion,
  createDocumentCatalogItem,
  getApiErrorMessage,
  getDocumentCatalog,
  getDocumentVersionChunks,
  getDocumentVersions,
  uploadDocument,
} from "../../services/api";
import type {
  DocumentCatalogItem,
  DocumentChunkItem,
  DocumentVersionItem,
} from "../../services/api";

interface DocumentUploadProps {
  maNd: string;
  onSuccess?: () => void;
}

interface ChunkPreview {
  chunks: DocumentChunkItem[];
  error: string;
  loading: boolean;
}

function getFileExtension(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? "";
}

export default function DocumentUpload({
  maNd,
  onSuccess,
}: DocumentUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [catalog, setCatalog] = useState<DocumentCatalogItem[]>([]);
  const [versions, setVersions] = useState<DocumentVersionItem[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [versionNumber, setVersionNumber] = useState("v1.0");
  const [uploading, setUploading] = useState(false);
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingCatalogItem, setCreatingCatalogItem] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState("LUAT");
  const [newField, setNewField] = useState("");
  const [newIssuer, setNewIssuer] = useState("");
  const [chunkPreviews, setChunkPreviews] = useState<
    Record<string, ChunkPreview>
  >({});
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const refreshData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [documents, documentVersions] = await Promise.all([
        getDocumentCatalog(),
        getDocumentVersions(),
      ]);
      setCatalog(documents);
      setVersions(documentVersions);
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
    void refreshData();
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
    if (!file || uploading || approvingId) return;

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

  const handleApprove = async (version: DocumentVersionItem) => {
    if (approvingId) return;
    const confirmed = window.confirm(
      `Xác nhận đã rà soát các đoạn trích và phê duyệt phiên bản ${version.ma_phien_ban}?`,
    );
    if (!confirmed) return;

    setApprovingId(version.ma_phien_ban);
    setError("");
    setSuccessMessage("");
    try {
      const result = await approveDocumentVersion(version.ma_phien_ban);
      setSuccessMessage(
        result.message || "Đã phê duyệt tài liệu và kích hoạt phiên bản.",
      );
      await refreshData();
    } catch (approvalError: unknown) {
      setError(
        getApiErrorMessage(approvalError, "Không thể phê duyệt tài liệu."),
      );
    } finally {
      setApprovingId(null);
    }
  };

  const toggleChunkPreview = async (versionId: string) => {
    if (chunkPreviews[versionId]) {
      setChunkPreviews((previous) => {
        const next = { ...previous };
        delete next[versionId];
        return next;
      });
      return;
    }

    setChunkPreviews((previous) => ({
      ...previous,
      [versionId]: { chunks: [], error: "", loading: true },
    }));
    try {
      const chunks = await getDocumentVersionChunks(versionId);
      setChunkPreviews((previous) => ({
        ...previous,
        [versionId]: { chunks, error: "", loading: false },
      }));
    } catch (previewError: unknown) {
      setChunkPreviews((previous) => ({
        ...previous,
        [versionId]: {
          chunks: [],
          error: getApiErrorMessage(
            previewError,
            "Không thể tải nội dung đã trích xuất.",
          ),
          loading: false,
        },
      }));
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
              disabled={loading || uploading || Boolean(approvingId)}
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
                disabled={uploading || Boolean(approvingId)}
              />
            </label>
            <label className="file-picker">
              Tệp pháp quy hoặc tài liệu tham khảo
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.html,.htm,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                disabled={uploading || Boolean(approvingId)}
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
            disabled={!file || !selectedDocumentId || uploading || Boolean(approvingId)}
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

      <section className="surface-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">THEO DÕI VÀ RÀ SOÁT</p>
            <h2>Phiên bản tài liệu</h2>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void refreshData()}
            disabled={loading || uploading || Boolean(approvingId)}
          >
            {loading ? "Đang tải…" : "Làm mới"}
          </button>
        </div>

        {versions.length === 0 && !loading && (
          <p className="muted">Chưa có phiên bản tài liệu nào.</p>
        )}

        {versions.map((version) => {
          const preview = chunkPreviews[version.ma_phien_ban];
          const canApprove =
            version.trang_thai === "Draft" &&
            Boolean(version.ma_nguoi_tai) &&
            version.ma_nguoi_tai !== maNd;

          return (
            <article className="review-card" key={version.ma_phien_ban}>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">{version.tieu_de}</p>
                  <h3>{version.so_phien_ban} · {version.ma_phien_ban}</h3>
                </div>
                <span
                  className={`status-pill ${version.trang_thai === "Approved" ? "status-approved" : "status-draft"}`}
                >
                  {version.trang_thai || "Không rõ trạng thái"}
                </span>
              </div>
              <dl className="document-details">
                <div><dt>Mã tài liệu</dt><dd>{version.ma_tai_lieu}</dd></div>
                <div>
                  <dt>Người tải lên</dt>
                  <dd>{version.ten_dang_nhap_nguoi_tai || version.ma_nguoi_tai || "Không rõ"}</dd>
                </div>
                <div><dt>Tệp gốc</dt><dd>{version.duong_dan_file || "Không có tên tệp"}</dd></div>
                <div><dt>Đang kích hoạt</dt><dd>{version.is_active ? "Có" : "Không"}</dd></div>
              </dl>

              <div className="document-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void toggleChunkPreview(version.ma_phien_ban)}
                >
                  {preview ? "Ẩn nội dung đã trích xuất" : "Xem nội dung đã trích xuất"}
                </button>
                {canApprove && (
                  <button
                    type="button"
                    onClick={() => void handleApprove(version)}
                    disabled={uploading || Boolean(approvingId)}
                    className="approve-button"
                  >
                    {approvingId === version.ma_phien_ban
                      ? "Đang phê duyệt…"
                      : "Rà soát và phê duyệt"}
                  </button>
                )}
              </div>

              {version.trang_thai === "Draft" &&
                version.ma_nguoi_tai === maNd && (
                  <p className="field-hint">
                    Người tải lên không thể tự phê duyệt phiên bản này. Cần một
                    chuyên viên pháp chế khác rà soát.
                  </p>
                )}

              {preview && (
                <div className="chunk-preview">
                  {preview.loading && <p className="muted">Đang tải nội dung…</p>}
                  {preview.error && (
                    <div className="notice notice-error" role="alert">
                      {preview.error}
                    </div>
                  )}
                  {!preview.loading && !preview.error && preview.chunks.length === 0 && (
                    <p className="muted">Phiên bản chưa có đoạn văn bản được trích xuất.</p>
                  )}
                  {preview.chunks.map((chunk) => (
                    <section className="chunk-card" key={chunk.ma_doan}>
                      <div>
                        <strong>Đoạn {chunk.thu_tu ?? "—"}</strong>
                        <span>{chunk.dieu_khoan || "Không xác định điều khoản"}</span>
                        {chunk.so_trang !== null && (
                          <span>Trang {chunk.so_trang}</span>
                        )}
                      </div>
                      <p>{chunk.noi_dung}</p>
                    </section>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </section>
    </div>
  );
}
