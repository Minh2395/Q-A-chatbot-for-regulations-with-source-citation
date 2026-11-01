import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createAdminUser,
  deleteAdminUser,
  getAdminAuditLogs,
  getAdminUsers,
  getApiErrorMessage,
  getLatestEvaluationReport,
  updateAdminUser,
} from "../services/api";
import type {
  AdminUser,
  AdminUserInput,
  AuditLogRecord,
  EvaluationReport,
} from "../services/api";

const emptyUserForm: AdminUserInput = {
  ten_dang_nhap: "",
  mat_khau: "",
  ho_ten: "",
  email: "",
  vai_tro: "NguoiDung",
};

const evaluationCriteria = [
  {
    name: "Độ chính xác",
    description:
      "Tỷ lệ câu trả lời đúng trên bộ câu hỏi có đáp án chuẩn được chuyên viên xác nhận.",
    value: "Chưa có dữ liệu",
  },
  {
    name: "Tính trung thành",
    description:
      "Mức độ câu trả lời được hỗ trợ bởi các đoạn bằng chứng đã truy xuất, không thêm nội dung ngoài nguồn.",
    value: "Chưa có dữ liệu",
  },
  {
    name: "Độ chính xác trích dẫn",
    description:
      "Tỷ lệ trích dẫn đúng tài liệu, điều khoản và đoạn nội dung thực sự hỗ trợ câu trả lời.",
    value: "Chưa có dữ liệu",
  },
];

export function AdminWorkspace() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [adminError, setAdminError] = useState("");
  const [loadingAdminData, setLoadingAdminData] = useState(true);
  const [savingUser, setSavingUser] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [userForm, setUserForm] = useState<AdminUserInput>(emptyUserForm);
  const [auditTotal, setAuditTotal] = useState(0);
  const [evaluationReport, setEvaluationReport] =
    useState<EvaluationReport | null>(null);
  const [evaluationError, setEvaluationError] = useState("");
  const [loadingEvaluation, setLoadingEvaluation] = useState(true);

  const loadAdminData = useCallback(async () => {
    try {
      const [loadedUsers, loadedAudit] = await Promise.all([
        getAdminUsers(),
        getAdminAuditLogs(),
      ]);
      setUsers(loadedUsers);
      setAuditLogs(loadedAudit.items);
      setAuditTotal(loadedAudit.total);
      setAdminError("");
    } catch (error: unknown) {
      setAdminError(
        getApiErrorMessage(error, "Không thể tải dữ liệu quản trị."),
      );
    } finally {
      setLoadingAdminData(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAdminData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAdminData]);

  const refreshAdminData = () => {
    setLoadingAdminData(true);
    void loadAdminData();
  };

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const loadReport = async () => {
      let isRunning = false;
      try {
        const report = await getLatestEvaluationReport();
        if (active) {
          setEvaluationReport(report);
          setEvaluationError("");
          isRunning = report?.status === "Running";
        }
      } catch (error: unknown) {
        if (active) {
          setEvaluationError(
            getApiErrorMessage(error, "Không thể tải báo cáo đánh giá."),
          );
        }
      } finally {
        if (active) {
          setLoadingEvaluation(false);
          timer = window.setTimeout(loadReport, isRunning ? 2500 : 10000);
        }
      }
    };
    void loadReport();

    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  const formatScore = (score: number | null | undefined) =>
    score == null ? "Chưa có dữ liệu" : `${(score * 100).toFixed(1)}%`;
  const evaluationStatus = loadingEvaluation
    ? "Đang tải"
    : evaluationReport?.status === "Completed"
      ? "Đã hoàn tất"
      : evaluationReport?.status === "Running"
        ? "Đang chạy"
        : evaluationReport?.status === "Pending"
          ? "Chờ xác minh"
          : evaluationReport?.status === "Failed"
            ? "Thất bại"
            : "Chưa có báo cáo";

  const resetUserForm = () => {
    setEditingUserId(null);
    setUserForm({ ...emptyUserForm });
  };

  const handleUserSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSavingUser(true);
    setAdminError("");
    try {
      if (editingUserId) {
        const { mat_khau, ...profile } = userForm;
        await updateAdminUser(editingUserId, {
          ...profile,
          ...(mat_khau ? { mat_khau } : {}),
          email: profile.email || "",
        });
      } else if (userForm.mat_khau) {
        await createAdminUser({
          ...userForm,
          email: userForm.email || "",
          mat_khau: userForm.mat_khau,
        });
      }
      resetUserForm();
      await loadAdminData();
    } catch (error: unknown) {
      setAdminError(
        getApiErrorMessage(error, "Không thể lưu tài khoản người dùng."),
      );
    } finally {
      setSavingUser(false);
    }
  };

  const editUser = (user: AdminUser) => {
    setEditingUserId(user.ma_nd);
    setUserForm({
      ten_dang_nhap: user.ten_dang_nhap,
      mat_khau: "",
      ho_ten: user.ho_ten ?? "",
      email: user.email ?? "",
      vai_tro: user.vai_tro ?? "NguoiDung",
    });
    setAdminError("");
  };

  const removeUser = async (user: AdminUser) => {
    if (!window.confirm(`Xóa tài khoản "${user.ten_dang_nhap}"?`)) return;
    setAdminError("");
    try {
      await deleteAdminUser(user.ma_nd);
      if (editingUserId === user.ma_nd) resetUserForm();
      await loadAdminData();
    } catch (error: unknown) {
      setAdminError(
        getApiErrorMessage(error, "Không thể xóa tài khoản người dùng."),
      );
    }
  };

  const loadMoreAuditLogs = async () => {
    try {
      const nextPage = await getAdminAuditLogs(auditLogs.length);
      setAuditLogs((current) => [...current, ...nextPage.items]);
    } catch (error: unknown) {
      setAdminError(
        getApiErrorMessage(error, "Không thể tải thêm nhật ký."),
      );
    }
  };

  const auditValue = (value: unknown) =>
    typeof value === "string" || typeof value === "number"
      ? String(value)
      : value == null
        ? "—"
        : JSON.stringify(value);

  return (
    <div className="admin-workspace">
      <section className="surface-card admin-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">QUẢN LÝ DANH TÍNH</p>
            <h2>Tài khoản người dùng</h2>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={refreshAdminData}
            disabled={loadingAdminData}
          >
            Làm mới
          </button>
        </div>
        <p className="muted">
          Tạo tài khoản, cập nhật hồ sơ/vai trò hoặc đặt lại mật khẩu. Mật khẩu
          được băm trước khi lưu. Cơ sở dữ liệu hiện không có trường khóa tài
          khoản; xóa bị từ chối nếu hồ sơ đã được dữ liệu khác tham chiếu.
        </p>
        {adminError && (
          <div className="notice notice-error" role="alert">{adminError}</div>
        )}
        <form className="document-form" onSubmit={handleUserSubmit}>
          <div className="form-grid">
            <label>
              Tên đăng nhập
              <input
                maxLength={50}
                required
                value={userForm.ten_dang_nhap}
                onChange={(event) =>
                  setUserForm({ ...userForm, ten_dang_nhap: event.target.value })
                }
              />
            </label>
            <label>
              Họ tên
              <input
                maxLength={200}
                value={userForm.ho_ten}
                onChange={(event) =>
                  setUserForm({ ...userForm, ho_ten: event.target.value })
                }
              />
            </label>
            <label>
              Email
              <input
                maxLength={100}
                type="email"
                value={userForm.email}
                onChange={(event) =>
                  setUserForm({ ...userForm, email: event.target.value })
                }
              />
            </label>
            <label>
              Vai trò
              <select
                value={userForm.vai_tro}
                onChange={(event) =>
                  setUserForm({ ...userForm, vai_tro: event.target.value })
                }
              >
                <option value="NguoiDung">Người dùng</option>
                <option value="ChuyenVienPhapChe">Chuyên viên pháp chế</option>
                <option value="QuanTriVien">Quản trị viên</option>
              </select>
            </label>
            <label>
              {editingUserId ? "Mật khẩu mới (để trống nếu không đổi)" : "Mật khẩu"}
              <input
                autoComplete="new-password"
                maxLength={1024}
                minLength={12}
                required={!editingUserId}
                type="password"
                value={userForm.mat_khau ?? ""}
                onChange={(event) =>
                  setUserForm({ ...userForm, mat_khau: event.target.value })
                }
              />
            </label>
          </div>
          <div className="capability-list">
            <button className="primary-button" disabled={savingUser} type="submit">
              {savingUser
                ? "Đang lưu…"
                : editingUserId
                  ? "Cập nhật tài khoản"
                  : "Tạo tài khoản"}
            </button>
            {editingUserId && (
              <button
                className="approve-button"
                type="button"
                onClick={resetUserForm}
              >
                Hủy chỉnh sửa
              </button>
            )}
          </div>
        </form>

        {loadingAdminData ? (
          <p className="muted" role="status">Đang tải tài khoản…</p>
        ) : users.length === 0 ? (
          <p className="muted">Chưa có tài khoản để hiển thị.</p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Tên đăng nhập</th>
                  <th>Họ tên</th>
                  <th>Email</th>
                  <th>Vai trò</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.ma_nd}>
                    <td>{user.ma_nd}</td>
                    <td>{user.ten_dang_nhap}</td>
                    <td>{user.ho_ten || "—"}</td>
                    <td>{user.email || "—"}</td>
                    <td>{user.vai_tro || "—"}</td>
                    <td className="admin-actions">
                      <button type="button" onClick={() => editUser(user)}>
                        Sửa
                      </button>
                      <button
                        type="button"
                        onClick={() => void removeUser(user)}
                      >
                        Xóa
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="surface-card admin-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">GIÁM SÁT VẬN HÀNH</p>
            <h2>Nhật ký hệ thống</h2>
          </div>
          <span className="status-pill status-approved">
            {auditLogs.length} / {auditTotal} bản ghi
          </span>
        </div>
        <p className="muted">
          Nhật ký kiểm toán được tải mới nhất trước. Dữ liệu chi tiết được giới
          hạn theo quyền quản trị viên.
        </p>
        {auditLogs.length === 0 ? (
          <p className="muted">
            {loadingAdminData ? "Đang tải nhật ký…" : "Chưa có nhật ký."}
          </p>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Thời điểm</th>
                  <th>Sự kiện</th>
                  <th>Mã người dùng</th>
                  <th>Trạng thái</th>
                  <th>Trace</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((record, index) => (
                  <tr key={`${record.trace_id ?? record.timestamp}-${index}`}>
                    <td>{auditValue(record.timestamp)}</td>
                    <td>{auditValue(record.event)}</td>
                    <td>{auditValue(record.ma_nd)}</td>
                    <td>{auditValue(record.status)}</td>
                    <td>{auditValue(record.trace_id)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {auditLogs.length < auditTotal && (
          <button
            className="primary-button"
            type="button"
            onClick={() => void loadMoreAuditLogs()}
          >
            Tải thêm nhật ký
          </button>
        )}
      </section>

      <section className="surface-card admin-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">CHẤT LƯỢNG MÔ HÌNH</p>
            <h2>Đánh giá hiệu năng AI</h2>
          </div>
          <span className="status-pill status-unavailable">
            {evaluationStatus}
          </span>
        </div>
        <p className="muted">
          Đánh giá được lên lịch sau khi phê duyệt phiên bản tài liệu. Bộ câu hỏi
          chỉ được chấm khi đáp án và nguồn pháp lý đã được xác minh.
        </p>
        <div className="evaluation-grid">
          {evaluationCriteria.map((criterion) => (
            <article key={criterion.name} className="metric-card">
              <span className="metric-value">
                {evaluationReport?.official && evaluationReport.metrics
                  ? criterion.name === "Độ chính xác"
                    ? formatScore(evaluationReport.metrics.accuracy)
                    : criterion.name === "Tính trung thành"
                      ? formatScore(evaluationReport.metrics.faithfulness)
                      : formatScore(
                          evaluationReport.metrics.citation_correctness,
                        )
                  : criterion.value}
              </span>
              <h3>{criterion.name}</h3>
              <p>{criterion.description}</p>
            </article>
          ))}
        </div>
        {evaluationError && (
          <div className="notice notice-error" role="alert">
            {evaluationError}
          </div>
        )}
        {evaluationReport && (
          <>
            <p className="muted" role="status">
              Bộ dữ liệu: {evaluationReport.dataset_question_count} câu hỏi;
              {" "}đã xác minh: {evaluationReport.verified_question_count};
              {" "}được chấm: {evaluationReport.metrics?.scored_questions ?? 0}.
              {" "}Phiên bản tài liệu:{" "}
              <code>{evaluationReport.document_version_id}</code>
            </p>
            {evaluationReport.pending_verification_questions.length > 0 && (
              <details className="notice notice-info">
                <summary>
                  Câu hỏi đang chờ xác minh (
                  {evaluationReport.pending_verification_questions.length})
                </summary>
                <ul>
                  {evaluationReport.pending_verification_questions.map(
                    (question) => (
                      <li key={question.id}>
                        <strong>{question.id}</strong>: {question.question}
                        {" — "}
                        {question.reason}
                      </li>
                    ),
                  )}
                </ul>
              </details>
            )}
            {evaluationReport.errors.map((error) => (
              <div className="notice notice-warning" key={error}>
                {error}
              </div>
            ))}
          </>
        )}
      </section>
    </div>
  );
}
