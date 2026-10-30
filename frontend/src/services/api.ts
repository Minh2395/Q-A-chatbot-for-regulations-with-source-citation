import axios, { isAxiosError } from "axios";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/+$/, "");

export interface Citation {
  ma_doan?: string;
  ten_tai_lieu?: string | null;
  ma_phien_ban?: string | null;
  so_phien_ban?: string | null;
  dieu_khoan?: string | null;
  so_trang?: number | null;
  noi_dung_trich: string;
  source_url?: string | null;
  do_tuong_dong?: number;
}

export interface ChatQueryRequest {
  ma_phien: string;
  ma_nd: string;
  noi_dung_cau_hoi: string;
}

export interface ChatQueryResponse {
  ma_cau_tra_loi: string;
  noi_dung_tra_loi: string;
  trang_thai: string;
  do_tin_cay: number;
  trace_id: string;
  ly_do_tu_choi?: string | null;
  trich_dan?: Citation[];
}

export interface UploadResponse {
  message: string;
  ma_phien_ban: string;
  so_phien_ban: string;
  so_doan: number;
  trang_thai: string;
}

export interface ApproveResponse {
  message: string;
  ma_phien_ban: string;
  trang_thai: string;
  is_active: number;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) {
    return error instanceof Error ? error.message : fallback;
  }

  const detail: unknown = error.response?.data?.detail;
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: string }) => item.msg)
      .filter((message): message is string => Boolean(message))
      .join(", ");
  }

  return error.message || fallback;
}

export const sendChatQuery = async (
  maPhien: string,
  maNd: string,
  noiDungCauHoi: string,
): Promise<ChatQueryResponse> => {
  const response = await axios.post<ChatQueryResponse>(
    API_BASE_URL,
    {
      ma_phien: maPhien,
      ma_nd: maNd,
      noi_dung_cau_hoi: noiDungCauHoi,
    } satisfies ChatQueryRequest,
  );

  return response.data;
};

export const uploadDocument = async (
  formData: FormData,
): Promise<UploadResponse> => {
  const response = await axios.post<UploadResponse>(
    `${API_BASE_URL}/documents/upload`,
    formData,
  );

  return response.data;
};

export const approveDocumentVersion = async (
  maPhienBan: string,
): Promise<ApproveResponse> => {
  const response = await axios.put<ApproveResponse>(
    `${API_BASE_URL}/documents/approve/${encodeURIComponent(maPhienBan)}`,
  );

  return response.data;
};
