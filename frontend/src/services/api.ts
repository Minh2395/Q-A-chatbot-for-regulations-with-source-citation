import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

// Kiểu dữ liệu gửi câu hỏi RAG
export interface ChatQueryRequest {
  ma_phien: string;
  ma_nd: string;
  noi_dung_cau_hoi: string;
}

// Kiểu dữ liệu trích dẫn nguồn
export interface Citation {
  ten_tai_lieu: string;
  so_trang: number;
  dieu_khoan: string;
  noi_dung_trich: string;
}

// Kiểu dữ liệu phản hồi hỏi đáp
export interface ChatQueryResponse {
  noi_dung_tra_loi: string;
  trang_thai: string;
  do_tin_cay: number;
  trace_id: string;
  ly_do_tu_choi?: string | null;
  trich_dan?: Citation[];
}

// Kiểu dữ liệu phản hồi upload tài liệu
export interface UploadResponse {
  message: string;
  ma_phien_ban: string;
  so_phien_ban: string;
  trang_thai: string;
}

// Kiểu dữ liệu phản hồi phê duyệt
export interface ApproveResponse {
  message: string;
}

// API 1: Gửi câu hỏi RAG
export const sendChatQuery = async (
  maPhien: string,
  maNd: string,
  noiDungCauHoi: string,
): Promise<ChatQueryResponse> => {
  const response = await axios.post<ChatQueryResponse>(
    `${API_BASE_URL}/chat/query`,
    {
      ma_phien: maPhien,
      ma_nd: maNd,
      noi_dung_cau_hoi: noiDungCauHoi,
    } satisfies ChatQueryRequest,
  );

  return response.data;
};

// API 2: Upload tài liệu PDF/Word
export const uploadDocument = async (
  formData: FormData,
): Promise<UploadResponse> => {
  const response = await axios.post<UploadResponse>(
    `${API_BASE_URL}/documents/upload`,
    formData,
  );

  return response.data;
};

// API 3: Phê duyệt phiên bản tài liệu
export const approveDocumentVersion = async (
  maPhienBan: string,
): Promise<ApproveResponse> => {
  const response = await axios.put<ApproveResponse>(
    `${API_BASE_URL}/documents/approve/${encodeURIComponent(maPhienBan)}`,
  );

  return response.data;
};
