import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createAdminUser,
  deleteAdminUser,
  getAdminAuditLogs,
  getAdminUsers,
  getApiErrorMessage,
  updateAdminUser,
} from "../services/api";
import type {
  AdminUser,
  AdminUserInput,
  AuditLogRecord,
} from "../services/api";
import { BenchmarkReport } from "./Dashboard/BenchmarkReport";

const AUDIT_PAGE_SIZE = 25;

const emptyUserForm: AdminUserInput = {
  ten_dang_nhap: "",
  mat_khau: "",
  ho_ten: "",
  email: "",
  vai_tro: "NguoiDung",
};

export function AdminWorkspace() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [adminError, setAdminError] = useState("");
  const [loadingAdminData, setLoadingAdminData] = useState(true);
  const [savingUser, setSavingUser] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [userForm, setUserForm] = useState<AdminUserInput>(emptyUserForm);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(1);
  const [loadingAudit, setLoadingAudit] = useState(true);
  const [auditError, setAuditError] = useState("");

  const loadAdminData = useCallback(async () => {
    try {
      const loadedUsers = await getAdminUsers();
      setUsers(loadedUsers);
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

  const loadAuditPage = useCallback(async () => {
    setLoadingAudit(true);
    setAuditError("");
    try {
      const result = await getAdminAuditLogs(
        (auditPage - 1) * AUDIT_PAGE_SIZE,
        AUDIT_PAGE_SIZE,
      );
      setAuditLogs(result.items);
      setAuditTotal(result.total);
    } catch (error: unknown) {
      setAuditError(
        getApiErrorMessage(error, "Không thể tải nhật ký hệ thống."),
      );
    } finally {
      setLoadingAudit(false);
    }
  }, [auditPage]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAuditPage();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAuditPage]);

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
            {auditTotal === 0
              ? "0 bản ghi"
              : `${(auditPage - 1) * AUDIT_PAGE_SIZE + 1}–${Math.min(
                  auditPage * AUDIT_PAGE_SIZE,
                  auditTotal,
                )} / ${auditTotal} bản ghi`}
          </span>
        </div>
        <p className="muted">
          Nhật ký kiểm toán được tải mới nhất trước. Dữ liệu chi tiết được giới
          hạn theo quyền quản trị viên.
        </p>
        {auditError && (
          <div className="notice notice-error" role="alert">{auditError}</div>
        )}
        {loadingAudit ? (
          <p className="muted" role="status">Đang tải nhật ký…</p>
        ) : auditLogs.length === 0 ? (
          <p className="muted">
            Chưa có nhật ký.
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
        <div className="document-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={() => setAuditPage((page) => Math.max(1, page - 1))}
            disabled={loadingAudit || auditPage <= 1}
          >
            Trang trước
          </button>
          <span className="muted">
            Trang {auditPage} / {Math.max(1, Math.ceil(auditTotal / AUDIT_PAGE_SIZE))}
          </span>
          <button
            className="secondary-button"
            type="button"
            onClick={() => setAuditPage((page) => page + 1)}
            disabled={
              loadingAudit ||
              auditPage >= Math.ceil(auditTotal / AUDIT_PAGE_SIZE)
            }
          >
            Trang sau
          </button>
        </div>
      </section>

      <BenchmarkReport />
    </div>
  );
}
