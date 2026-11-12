import json

from fastapi.testclient import TestClient

from app.api.v1 import admin
from app.core import security
from app.core.security import AuthenticatedUser
from app.main import app


def set_admin_user():
    app.dependency_overrides[security.get_current_user] = lambda: (
        AuthenticatedUser(ma_nd="ADMIN_01", vai_tro="QuanTriVien")
    )


def clear_overrides():
    app.dependency_overrides.pop(security.get_current_user, None)


def test_admin_user_listing_returns_no_password_hash(monkeypatch):
    class Cursor:
        def execute(self, query):
            assert "FROM dbo.NGUOI_DUNG" in query
            assert "MatKhauHash" not in query

        def fetchall(self):
            return [("U1", "alice", "Alice", None, "NguoiDung")]

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(admin, "get_business_db_connection", Connection)
    set_admin_user()
    try:
        response = TestClient(app).get("/api/v1/admin/users")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == [{
        "ma_nd": "U1",
        "ten_dang_nhap": "alice",
        "ho_ten": "Alice",
        "email": None,
        "vai_tro": "NguoiDung",
    }]
    assert "MatKhauHash" not in response.text


def test_admin_can_create_user_with_hashed_password_only(monkeypatch):
    statements = []
    committed = []
    monkeypatch.setattr(admin, "write_audit_log", lambda **_kwargs: None)

    class Cursor:
        def execute(self, query, *params):
            statements.append((query, params))

        def fetchone(self):
            insert_params = statements[0][1]
            return (insert_params[0], insert_params[1], "Alice", None, "NguoiDung")

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            committed.append(True)

        def rollback(self):
            raise AssertionError("Successful creation must not roll back.")

        def close(self):
            pass

    monkeypatch.setattr(admin, "get_business_db_connection", Connection)
    set_admin_user()
    try:
        response = TestClient(app).post(
            "/api/v1/admin/users",
            json={
                "ten_dang_nhap": "alice",
                "mat_khau": "long-enough-password",
                "ho_ten": "Alice",
                "vai_tro": "NguoiDung",
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 201
    assert len(committed) == 1
    assert len(statements[0][1][2]) > 50
    assert security.verify_password(
        "long-enough-password",
        statements[0][1][2],
    )
    assert "long-enough-password" not in response.text
    assert "MatKhauHash" not in response.text


def test_admin_audit_log_pagination_filters_and_orders_newest_first(
    monkeypatch,
    tmp_path,
):
    audit_path = tmp_path / "audit.jsonl"
    records = [
        {"event": "CHAT_RESULT", "ma_nd": "U1", "timestamp": "2025-01-01"},
        {"event": "CHAT_RESULT", "ma_nd": "U2", "timestamp": "2025-01-02"},
        {"event": "LOGIN", "ma_nd": "U1", "timestamp": "2025-01-03"},
    ]
    audit_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(admin, "AUDIT_FILE", audit_path)
    set_admin_user()
    try:
        response = TestClient(app).get(
            "/api/v1/admin/audit-logs?user_id=U1&limit=1"
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"] == [records[2]]


def test_non_admin_cannot_access_admin_endpoints():
    app.dependency_overrides[security.get_current_user] = lambda: (
        AuthenticatedUser(ma_nd="U1", vai_tro="NguoiDung")
    )
    try:
        response = TestClient(app).get("/api/v1/admin/users")
    finally:
        clear_overrides()

    assert response.status_code == 403
