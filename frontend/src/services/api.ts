import axios, { isAxiosError } from "axios";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/+$/, "");

let accessToken: string | null = null;
const apiClient = axios.create();

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

export interface AuthenticatedUser {
  ma_nd: string;
  vai_tro: string;
  ho_ten: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthenticatedUser;
}

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

export interface DocumentCatalogItem {
  ma_tai_lieu: string;
  tieu_de: string;
  loai_van_ban: string;
  linh_vuc: string | null;
  co_quan_ban_hanh: string | null;
}

export interface DocumentCatalogInput {
  tieu_de: string;
  loai_van_ban: string;
  linh_vuc?: string;
  co_quan_ban_hanh?: string;
}

export interface DocumentVersionItem {
  ma_phien_ban: string;
  ma_tai_lieu: string;
  tieu_de: string;
  ma_nguoi_tai: string | null;
  ten_dang_nhap_nguoi_tai: string | null;
  so_phien_ban: string;
  trang_thai: string | null;
  is_active: boolean;
  duong_dan_file: string | null;
  ngay_hieu_luc: string | null;
}

export interface DocumentChunkItem {
  ma_doan: string;
  thu_tu: number | null;
  dieu_khoan: string | null;
  noi_dung: string;
  so_trang: number | null;
}

export interface ApproveResponse {
  message: string;
  ma_phien_ban: string;
  trang_thai: string;
  is_active: number;
  evaluation_status?: string;
}

export interface EvaluationPendingQuestion {
  id: string;
  question: string;
  status: string;
  reason: string;
  review_status?: string | null;
  review_note?: string | null;
  preliminary_match_status?: string | null;
  preliminary_note?: string | null;
  candidate_sources?: Array<{
    ma_doan_candidate?: string;
    article_candidate?: string;
    article_title_candidate?: string;
    ma_phien_ban?: string;
    document_id?: string;
    version?: string;
  }>;
  retrieval_diagnostics_not_verified?: Array<{
    ma_doan?: string;
    similarity_score?: number;
    dieu_khoan?: string;
  }>;
  missing_reference_fields?: string[];
}

export interface EvaluationReport {
  evaluation_id: string;
  document_version_id: string;
  started_at: string;
  completed_at: string | null;
  status:
    | "Pending"
    | "Running"
    | "Completed"
    | "Preliminary"
    | "NoActiveDocuments"
    | "Failed";
  official: boolean;
  dataset_question_count: number;
  active_document_count?: number;
  verified_question_count: number;
  pending_verification_questions: EvaluationPendingQuestion[];
  failed_questions: Array<{ id: string; question: string; error: string }>;
  metrics: {
    accuracy: number | null;
    faithfulness: number | null;
    citation_correctness: number | null;
    correct_refusal_rate?: number | null;
    accuracy_sample_count?: number;
    faithfulness_sample_count?: number;
    citation_sample_count?: number;
    correct_refusal_sample_count?: number;
    scored_questions: number;
  } | null;
  preliminary_metrics?: {
    questions_attempted: number;
    questions_completed: number;
    qualified_retrievals: number;
    retrieval_coverage: number | null;
    generated_answers: number;
    refusals: number;
    failed_questions: number;
  } | null;
  question_results?: Array<{
    id: string;
    question: string;
    status: string;
    response_status?: string | null;
    generated_answer?: string | null;
    retrieved_sources?: Citation[];
    retrieval?: {
      qualified: boolean;
      best_score: number;
      threshold: number | null;
      total_active_vectors: number;
    } | null;
    error?: string | null;
  }>;
  database_persistence: { status: string; reason?: string; ma_ket_qua?: string };
  errors: string[];
}

export interface EvaluationRunResponse {
  message: string;
  document_version_id: string;
  status: string;
}

export interface AdminUser {
  ma_nd: string;
  ten_dang_nhap: string;
  ho_ten: string | null;
  email: string | null;
  vai_tro: string | null;
}

export interface AdminUserInput {
  ten_dang_nhap: string;
  ho_ten: string;
  email: string;
  vai_tro: string;
  mat_khau?: string;
}

export interface AuditLogRecord {
  timestamp?: string;
  event?: string;
  trace_id?: string;
  ma_nd?: string | null;
  ma_phien?: string | null;
  ma_cau_hoi?: string | null;
  status?: string | null;
  confidence?: number | null;
  details?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface AuditLogPage {
  items: AuditLogRecord[];
  total: number;
  limit: number;
  offset: number;
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  const response = await apiClient.get<AdminUser[]>(`${API_BASE_URL}/admin/users`);
  return response.data;
}

export async function createAdminUser(
  user: AdminUserInput & { mat_khau: string },
): Promise<AdminUser> {
  const response = await apiClient.post<AdminUser>(
    `${API_BASE_URL}/admin/users`,
    user,
  );
  return response.data;
}

export async function updateAdminUser(
  userId: string,
  user: Partial<AdminUserInput>,
): Promise<AdminUser> {
  const response = await apiClient.patch<AdminUser>(
    `${API_BASE_URL}/admin/users/${encodeURIComponent(userId)}`,
    user,
  );
  return response.data;
}

export async function deleteAdminUser(userId: string): Promise<void> {
  await apiClient.delete(
    `${API_BASE_URL}/admin/users/${encodeURIComponent(userId)}`,
  );
}

export async function getAdminAuditLogs(
  offset = 0,
  limit = 50,
): Promise<AuditLogPage> {
  const response = await apiClient.get<AuditLogPage>(
    `${API_BASE_URL}/admin/audit-logs`,
    { params: { offset, limit } },
  );
  return response.data;
}

export async function loginWithCredentials(
  tenDangNhap: string,
  matKhau: string,
): Promise<AuthenticatedUser> {
  const response = await axios.post<LoginResponse>(
    `${API_BASE_URL}/auth/login`,
    {
      ten_dang_nhap: tenDangNhap,
      mat_khau: matKhau,
    },
  );
  if (response.data.token_type !== "bearer" || !response.data.access_token) {
    throw new Error("Máy chủ trả về thông tin xác thực không hợp lệ.");
  }
  accessToken = response.data.access_token;
  return response.data.user;
}

export function clearAccessToken(): void {
  accessToken = null;
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
  const response = await apiClient.post<ChatQueryResponse>(
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
  const response = await apiClient.post<UploadResponse>(
    `${API_BASE_URL}/documents/upload`,
    formData,
  );

  return response.data;
};

export const approveDocumentVersion = async (
  maPhienBan: string,
): Promise<ApproveResponse> => {
  const response = await apiClient.put<ApproveResponse>(
    `${API_BASE_URL}/documents/approve/${encodeURIComponent(maPhienBan)}`,
  );

  return response.data;
};

export const getDocumentCatalog = async (): Promise<DocumentCatalogItem[]> => {
  const response = await apiClient.get<DocumentCatalogItem[]>(
    `${API_BASE_URL}/documents/catalog`,
  );
  return response.data;
};

export const createDocumentCatalogItem = async (
  item: DocumentCatalogInput,
): Promise<DocumentCatalogItem> => {
  const response = await apiClient.post<DocumentCatalogItem>(
    `${API_BASE_URL}/documents/catalog`,
    item,
  );
  return response.data;
};

export const getDocumentVersions = async (
  status?: string,
): Promise<DocumentVersionItem[]> => {
  const response = await apiClient.get<DocumentVersionItem[]>(
    `${API_BASE_URL}/documents/versions`,
    { params: status ? { trang_thai: status } : undefined },
  );
  return response.data;
};

export const getDocumentVersionChunks = async (
  versionId: string,
): Promise<DocumentChunkItem[]> => {
  const response = await apiClient.get<DocumentChunkItem[]>(
    `${API_BASE_URL}/documents/versions/${encodeURIComponent(versionId)}/chunks`,
  );
  return response.data;
};

export const getLatestEvaluationReport =
  async (): Promise<EvaluationReport | null> => {
    try {
      const response = await apiClient.get<EvaluationReport>(
        `${API_BASE_URL}/evaluation/latest`,
      );
      return response.data;
    } catch (error: unknown) {
      if (isAxiosError(error) && error.response?.status === 404) return null;
      throw error;
    }
};

export const clearLatestEvaluationReport = async (): Promise<void> => {
  await apiClient.delete(`${API_BASE_URL}/evaluation/latest`);
};

export const runLatestEvaluation = async (): Promise<EvaluationRunResponse> => {
  const response = await apiClient.post<EvaluationRunResponse>(
    `${API_BASE_URL}/evaluation/run-latest`,
  );
  return response.data;
};
