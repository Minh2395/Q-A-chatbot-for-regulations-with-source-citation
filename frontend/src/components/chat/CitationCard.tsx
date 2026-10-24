import React from "react";

interface Citation {
  ten_tai_lieu: string;
  so_trang: number;
  dieu_khoan: string;
  noi_dung_trich: string;
}

interface CitationCardProps {
  citation: Citation;
}

export const CitationCard: React.FC<CitationCardProps> = ({ citation }) => {
  return (
    <div className="bg-blue-50 border-l-4 border-blue-600 p-3 my-2 rounded text-sm text-slate-800 shadow-sm">
      <div className="flex items-center justify-between font-semibold text-blue-900 mb-1">
        <span>📄 {citation.ten_tai_lieu}</span>

        <span className="bg-blue-200 text-blue-800 px-2 py-0.5 rounded text-xs">
          Trang {citation.so_trang}
        </span>
      </div>

      <div className="font-medium text-slate-700 text-xs mb-1">
        📌 {citation.dieu_khoan}
      </div>

      <p className="text-slate-600 italic text-xs bg-white p-2 rounded border border-blue-100">
        "{citation.noi_dung_trich}"
      </p>
    </div>
  );
};
