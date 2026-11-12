import { useEffect, useRef } from "react";
import type { Citation } from "../../services/api";

interface RegulationViewerProps {
  citation: Citation;
  onClose: () => void;
}

export function RegulationViewer({ citation, onClose }: RegulationViewerProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className="regulation-dialog"
      aria-labelledby="regulation-title"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <article className="regulation-viewer">
        <header className="regulation-viewer-header">
          <div>
            <p className="eyebrow">NỘI DUNG CĂN CỨ</p>
            <h2 id="regulation-title">
              {citation.ten_tai_lieu || "Tài liệu pháp quy"}
            </h2>
          </div>
          <button
            type="button"
            className="regulation-close"
            onClick={onClose}
            aria-label="Đóng nội dung căn cứ"
          >
            ×
          </button>
        </header>

        <dl className="regulation-metadata">
          <div>
            <dt>Điều khoản</dt>
            <dd>{citation.dieu_khoan || "Chưa có thông tin điều khoản"}</dd>
          </div>
          <div>
            <dt>Trang</dt>
            <dd>{citation.so_trang ?? "Không rõ"}</dd>
          </div>
          {citation.so_phien_ban && (
            <div>
              <dt>Phiên bản</dt>
              <dd>{citation.so_phien_ban}</dd>
            </div>
          )}
        </dl>

        <section className="regulation-content" aria-label="Đoạn nội dung quy định">
          <h3>Đoạn nội dung được trích dẫn</h3>
          <p>{citation.noi_dung_trich}</p>
        </section>

        {citation.source_url && (
          <a
            className="regulation-source"
            href={citation.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Mở nguồn tài liệu
          </a>
        )}
      </article>
    </dialog>
  );
}
