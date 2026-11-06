import { useCallback, useEffect, useState } from "react";
import {
  approveDocumentVersion,
  getApiErrorMessage,
  getDocumentVersionChunks,
  getDocumentVersions,
} from "../../services/api";
import type {
  DocumentChunkItem,
  DocumentVersionItem,
} from "../../services/api";

interface VersionManagerProps {
  refreshKey: number;
}

interface ChunkPreview {
  chunks: DocumentChunkItem[];
  error: string;
  loading: boolean;
}

export default function VersionManager({ refreshKey }: VersionManagerProps) {
  const [versions, setVersions] = useState<DocumentVersionItem[]>([]);
  const [chunkPreviews, setChunkPreviews] = useState<
    Record<string, ChunkPreview>
  >({});
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const refreshVersions = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setVersions(await getDocumentVersions());
    } catch (loadError: unknown) {
      setError(
        getApiErrorMessage(loadError, "Không thể tải danh sách phiên bản."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshVersions();
  }, [refreshKey, refreshVersions]);

  const handleApprove = async (version: DocumentVersionItem) => {
    if (approvingId) return;
    if (
      !window.confirm(
        `Xác nhận đã rà soát và chấp nhận phiên bản ${version.ma_phien_ban}?`,
      )
    ) {
      return;
    }

    setApprovingId(version.ma_phien_ban);
    setError("");
    setSuccessMessage("");
    try {
      const result = await approveDocumentVersion(version.ma_phien_ban);
      setSuccessMessage(
        result.message || "Đã chấp nhận tài liệu và kích hoạt phiên bản.",
      );
      await refreshVersions();
    } catch (approvalError: unknown) {
      setError(
        getApiErrorMessage(approvalError, "Không thể chấp nhận tài liệu."),
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

  return (
    <section className="surface-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">THEO DÕI VÀ RÀ SOÁT</p>
          <h2>Phiên bản tài liệu</h2>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={() => void refreshVersions()}
          disabled={loading || Boolean(approvingId)}
        >
          {loading ? "Đang tải…" : "Làm mới"}
        </button>
      </div>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {successMessage && (
        <div className="notice notice-success" role="status">
          {successMessage}
        </div>
      )}
      {loading && <p className="muted" role="status">Đang tải phiên bản…</p>}
      {!loading && versions.length === 0 && (
        <p className="muted">Chưa có phiên bản tài liệu nào.</p>
      )}
      {versions.map((version) => {
        const preview = chunkPreviews[version.ma_phien_ban];
        const canApprove = version.trang_thai === "Draft";
        const statusClass =
          version.trang_thai === "Approved"
            ? "status-approved"
            : version.trang_thai === "Draft"
              ? "status-draft"
              : "status-unavailable";

        return (
          <article className="review-card" key={version.ma_phien_ban}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">{version.tieu_de}</p>
                <h3>{version.so_phien_ban} · {version.ma_phien_ban}</h3>
              </div>
              <span className={`status-pill ${statusClass}`}>
                {version.trang_thai || "Không rõ trạng thái"}
              </span>
            </div>
            <dl className="document-details">
              <div><dt>Mã tài liệu</dt><dd>{version.ma_tai_lieu}</dd></div>
              <div>
                <dt>Người tải lên</dt>
                <dd>
                  {version.ten_dang_nhap_nguoi_tai ||
                    version.ma_nguoi_tai ||
                    "Không rõ"}
                </dd>
              </div>
              <div>
                <dt>Tệp gốc</dt>
                <dd>{version.duong_dan_file || "Không có tên tệp"}</dd>
              </div>
              <div>
                <dt>Đang kích hoạt</dt>
                <dd>{version.is_active ? "Có" : "Không"}</dd>
              </div>
            </dl>
            <div className="document-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => void toggleChunkPreview(version.ma_phien_ban)}
              >
                {preview
                  ? "Ẩn nội dung đã trích xuất"
                  : "Xem nội dung đã trích xuất"}
              </button>
              {canApprove && (
                <button
                  type="button"
                  onClick={() => void handleApprove(version)}
                  disabled={Boolean(approvingId)}
                  className="approve-button"
                >
                  {approvingId === version.ma_phien_ban
                    ? "Đang chấp nhận…"
                    : "Chấp nhận"}
                </button>
              )}
            </div>
            {preview && (
              <div className="chunk-preview">
                {preview.loading && (
                  <p className="muted">Đang tải nội dung…</p>
                )}
                {preview.error && (
                  <div className="notice notice-error" role="alert">
                    {preview.error}
                  </div>
                )}
                {!preview.loading &&
                  !preview.error &&
                  preview.chunks.length === 0 && (
                    <p className="muted">
                      Phiên bản chưa có đoạn văn bản được trích xuất.
                    </p>
                  )}
                {preview.chunks.map((chunk) => (
                  <section className="chunk-card" key={chunk.ma_doan}>
                    <div>
                      <strong>Đoạn {chunk.thu_tu ?? "—"}</strong>
                      <span>
                        {chunk.dieu_khoan || "Không xác định điều khoản"}
                      </span>
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
  );
}