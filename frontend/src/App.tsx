import { useState } from "react";
import type { FormEvent } from "react";
import { ChatWindow } from "./components/chat/ChatWindow";
import DocumentUpload from "./components/Documents/DocumentUpload";
import { AdminWorkspace } from "./components/AdminWorkspace";
import {
  loginWithCredentials,
  clearAccessToken,
  getApiErrorMessage,
} from "./services/api";

type UserRole = "ChuyenVienPhapChe" | "QuanTriVien" | "NguoiDung";
type Page = "chat" | "documents" | "admin";

interface WorkspaceUser {
  maNd: string;
  vaiTro: UserRole;
}

const roleLabels: Record<UserRole, string> = {
  ChuyenVienPhapChe: "Chuyên viên pháp chế",
  QuanTriVien: "Quản trị viên",
  NguoiDung: "Người dùng",
};

function isUserRole(value: string): value is UserRole {
  return (
    value === "ChuyenVienPhapChe" ||
    value === "QuanTriVien" ||
    value === "NguoiDung"
  );
}

function createSessionId(): string {
  return `S${crypto.randomUUID().replaceAll("-", "").slice(0, 19)}`;
}

export default function App() {
  const [user, setUser] = useState<WorkspaceUser | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [authenticating, setAuthenticating] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [activePage, setActivePage] = useState<Page>("chat");
  const [processedCount, setProcessedCount] = useState(0);

  const handleEnterWorkspace = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (authenticating || !username.trim() || !password) return;

    setAuthenticating(true);
    setLoginError("");
    try {
      const authenticatedUser = await loginWithCredentials(
        username.trim(),
        password,
      );
      if (!isUserRole(authenticatedUser.vai_tro)) {
        clearAccessToken();
        throw new Error("Tài khoản không có vai trò được hỗ trợ.");
      }

      setUser({
        maNd: authenticatedUser.ma_nd,
        vaiTro: authenticatedUser.vai_tro,
      });
      setSessionId(createSessionId());
      setActivePage("chat");
      setProcessedCount(0);
      setPassword("");
    } catch (error: unknown) {
      clearAccessToken();
      setLoginError(getApiErrorMessage(error, "Không thể xác thực tài khoản."));
      setPassword("");
    } finally {
      setAuthenticating(false);
    }
  };

  const handleSignOut = () => {
    clearAccessToken();
    setUser(null);
    setSessionId("");
    setUsername("");
    setPassword("");
    setActivePage("chat");
  };

  if (!user) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <div className="brand-mark" aria-hidden="true">
            PL
          </div>
          <p className="eyebrow">AIK-01 · TRỢ LÝ PHÁP QUY</p>
          <h1>Không gian làm việc</h1>
          <p className="muted">
            Đăng nhập bằng tài khoản hiện có. Vai trò được đọc từ hồ sơ backend,
            không thể chọn hoặc tự sửa tại giao diện.
          </p>

          <form onSubmit={handleEnterWorkspace} className="login-form">
            <label>
              Tên đăng nhập
              <input
                autoComplete="username"
                maxLength={50}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Tên đăng nhập"
                required
              />
            </label>

            <label>
              Mật khẩu
              <input
                type="password"
                autoComplete="current-password"
                maxLength={1024}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Mật khẩu tài khoản"
                required
              />
            </label>

            {loginError && (
              <div className="notice notice-error" role="alert">
                {loginError}
              </div>
            )}

            <button
              className="primary-button"
              type="submit"
              disabled={authenticating || !username.trim() || !password}
            >
              {authenticating ? "Đang đăng nhập…" : "Đăng nhập"}
            </button>
          </form>

          <div className="notice notice-warning" role="note">
            Mật khẩu được xác minh với <code>MatKhauHash</code> trong backend.
            Phiên đăng nhập chỉ giữ token trong bộ nhớ tab và hết hạn sau tối đa
            một giờ.
          </div>
        </section>
      </main>
    );
  }

  const pages: { id: Page; label: string; icon: string }[] = [
    { id: "chat", label: "Hỏi đáp AI", icon: "✦" },
    ...(user.vaiTro === "ChuyenVienPhapChe"
      ? [{ id: "documents" as const, label: "Tài liệu pháp chế", icon: "▤" }]
      : []),
    ...(user.vaiTro === "QuanTriVien"
      ? [{ id: "admin" as const, label: "Quản trị hệ thống", icon: "⚙" }]
      : []),
  ];

  const navigate = (page: Page) => {
    if (pages.some((item) => item.id === page)) setActivePage(page);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            PL
          </div>
          <div>
            <strong>Pháp Luật AI</strong>
            <span>Trợ lý quy chế</span>
          </div>
        </div>

        <div className="workspace-label">KHÔNG GIAN LÀM VIỆC</div>
        <nav className="main-nav" aria-label="Điều hướng chính">
          {pages.map((page) => (
            <button
              key={page.id}
              type="button"
              onClick={() => navigate(page.id)}
              className={`nav-item ${activePage === page.id ? "is-active" : ""}`}
              aria-current={activePage === page.id ? "page" : undefined}
            >
              <span className="nav-icon" aria-hidden="true">
                {page.icon}
              </span>
              {page.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="profile-card">
            <div className="avatar" aria-hidden="true">
              {user.maNd.slice(0, 1).toUpperCase()}
            </div>
            <div className="profile-copy">
              <strong>{user.maNd}</strong>
              <span>{roleLabels[user.vaiTro]}</span>
            </div>
          </div>
          <button
            type="button"
            className="signout-button"
            onClick={handleSignOut}
          >
            Đổi hồ sơ / thoát
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">AIK-01 · HỆ THỐNG HỎI ĐÁP QUY CHẾ</p>
            <h1>{pages.find((page) => page.id === activePage)?.label}</h1>
          </div>
          <div className="role-pill">
            <span className="status-dot" />
            {roleLabels[user.vaiTro]}
          </div>
        </header>

        <div className="role-notice" role="note">
          Vai trò được đọc từ tài khoản backend đã xác thực; API kiểm tra quyền
          trên từng thao tác.
        </div>

        <section className="page-section" hidden={activePage !== "chat"}>
          <div className="page-intro">
            <div>
              <h2>Tra cứu quy định pháp luật</h2>
              <p>
                Đặt câu hỏi và xem câu trả lời cùng căn cứ được truy xuất từ tài
                liệu đã phê duyệt.
              </p>
            </div>
            <span className="info-chip">Tài liệu đã duyệt · RAG</span>
          </div>
          <ChatWindow maNd={user.maNd} maPhien={sessionId} />
        </section>

        {user.vaiTro === "ChuyenVienPhapChe" && (
          <section className="page-section" hidden={activePage !== "documents"}>
            <div className="page-intro">
              <div>
                <h2>Tiếp nhận và duyệt tài liệu</h2>
                <p>
                  Tài liệu mới luôn ở trạng thái nháp cho đến khi chuyên viên
                  chủ động phê duyệt.
                </p>
              </div>
              <span className="info-chip">
                {processedCount} tài liệu trong phiên
              </span>
            </div>
            <DocumentUpload
              maNd={user.maNd}
              onSuccess={() => setProcessedCount((count) => count + 1)}
            />
          </section>
        )}

        {user.vaiTro === "QuanTriVien" && (
          <section className="page-section" hidden={activePage !== "admin"}>
            <div className="page-intro">
              <div>
                <h2>Trung tâm quản trị</h2>
                <p>Theo dõi tài khoản, hoạt động và chất lượng hệ thống.</p>
              </div>
              <span className="info-chip">Dữ liệu backend</span>
            </div>
            <AdminWorkspace />
          </section>
        )}
      </main>
    </div>
  );
}
