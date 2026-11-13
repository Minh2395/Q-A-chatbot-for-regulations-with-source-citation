import type { Citation } from "../../services/api";

interface CitationDetailPageProps {
  citation: Citation;
  onBack: () => void;
}

export function CitationDetailPage({
  citation,
  onBack,
}: CitationDetailPageProps) {
  return (
    <article className="citation-detail-page surface-card">
      <header className="citation-detail-header">
        <div>
          <p className="eyebrow">NỘI DUNG CĂN CỨ</p>
          <h2>{citation.ten_tai_lieu || "Tài liệu pháp quy"}</h2>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={onBack}
        >
          ← Quay lại cuộc trò chuyện
        </button>
      </header>

      <dl className="citation-detail-metadata">
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
        {citation.ma_phien_ban && (
          <div>
            <dt>Mã phiên bản</dt>
            <dd>{citation.ma_phien_ban}</dd>
          </div>
        )}
        {citation.ma_doan && (
          <div>
            <dt>Mã đoạn căn cứ</dt>
            <dd>{citation.ma_doan}</dd>
          </div>
        )}
        {citation.do_tuong_dong !== undefined && (
          <div>
            <dt>Độ tương đồng</dt>
            <dd>{(citation.do_tuong_dong * 100).toFixed(1)}%</dd>
          </div>
        )}
      </dl>

      <section
        className="citation-detail-content"
        aria-label="Toàn văn nội dung căn cứ được trích dẫn"
      >
        <h3>Nội dung căn cứ</h3>
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
  );
}
