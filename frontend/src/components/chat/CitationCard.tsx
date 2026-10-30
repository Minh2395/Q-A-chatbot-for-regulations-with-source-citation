import type { Citation } from "../../services/api";

interface CitationCardProps {
  citation: Citation;
}

export function CitationCard({ citation }: CitationCardProps) {
  return (
    <article className="citation-card">
      <div className="citation-heading">
        <strong>{citation.ten_tai_lieu || "Tài liệu pháp quy"}</strong>
        <span>
          {citation.so_trang ? `Trang ${citation.so_trang}` : "Không rõ trang"}
        </span>
      </div>
      <p className="citation-clause">
        {citation.dieu_khoan || "Chưa có thông tin điều khoản"}
      </p>
      <blockquote>{citation.noi_dung_trich}</blockquote>
      {citation.do_tuong_dong !== undefined && (
        <small>Độ tương đồng: {(citation.do_tuong_dong * 100).toFixed(1)}%</small>
      )}
    </article>
  );
}
