import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.v1 import auth, chat
from app.core import security
from app.core.config import Settings
from app.core.security import AuthenticatedUser
from app.main import app


SECRET = "test-only-signing-secret-with-at-least-32-characters"


def create_token(subject="U1", secret=SECRET, **overrides):
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "sub": subject,
        "iss": "https://issuer.example.test",
        "aud": "aik01-api",
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)

    def encode(value):
        return base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()

    signing_input = f"{encode(header)}.{encode(claims)}"
    signature = base64.urlsafe_b64encode(
        hmac.new(
            secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
    ).rstrip(b"=").decode()
    return f"{signing_input}.{signature}"


def configure_auth(monkeypatch):
    monkeypatch.setattr(security.settings, "AUTH_JWT_SECRET", SECRET)
    monkeypatch.setattr(
        security.settings,
        "AUTH_JWT_ISSUER",
        "https://issuer.example.test",
    )
    monkeypatch.setattr(
        security.settings,
        "AUTH_JWT_AUDIENCE",
        "aik01-api",
    )
    monkeypatch.setattr(security.settings, "AUTH_JWT_MAX_TTL_SECONDS", 3600)


def credentials(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_authenticated_subject_uses_database_role(monkeypatch):
    configure_auth(monkeypatch)

    class Cursor:
        def execute(self, query, subject):
            assert "FROM dbo.NGUOI_DUNG" in query
            assert subject == "U1"

        def fetchone(self):
            return ("U1", "User One", "NguoiDung")

    class Connection:
        closed = False

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(
        security,
        "get_business_db_connection",
        lambda: connection,
    )
    token = create_token(role="QuanTriVien")

    user = security.get_current_user(credentials(token))

    assert user == AuthenticatedUser(
        ma_nd="U1",
        ho_ten="User One",
        vai_tro="NguoiDung",
    )
    assert connection.closed


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        "a" * 8193,
        create_token(secret="incorrect-signing-secret"),
        create_token(exp=int(time.time()) - 1),
        create_token(exp=float("nan")),
        create_token(iss="https://untrusted.example.test"),
        create_token(aud="different-api"),
        create_token(sub=""),
    ],
)
def test_invalid_bearer_tokens_are_rejected(monkeypatch, token):
    configure_auth(monkeypatch)
    monkeypatch.setattr(
        security,
        "get_business_db_connection",
        lambda: pytest.fail("Invalid token must not query SQL Server."),
    )

    with pytest.raises(HTTPException) as error:
        security.get_current_user(credentials(token))

    assert error.value.status_code == 401


def test_missing_auth_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(security.settings, "AUTH_JWT_SECRET", None)
    monkeypatch.setattr(security.settings, "AUTH_JWT_ISSUER", None)
    monkeypatch.setattr(security.settings, "AUTH_JWT_AUDIENCE", None)

    with pytest.raises(HTTPException) as error:
        security.get_current_user(credentials(create_token()))

    assert error.value.status_code == 503


def test_backend_env_file_is_independent_of_process_working_directory():
    expected_env_file = Path(__file__).resolve().parents[1] / ".env"

    assert Path(Settings.model_config["env_file"]) == expected_env_file


def test_login_returns_503_when_jwt_configuration_is_missing(monkeypatch):
    configure_auth(monkeypatch)
    monkeypatch.setattr(security.settings, "AUTH_JWT_SECRET", None)
    monkeypatch.setattr(security.settings, "AUTH_JWT_ISSUER", None)
    monkeypatch.setattr(security.settings, "AUTH_JWT_AUDIENCE", None)
    password_hash = security.hash_password("correct password")

    class Cursor:
        def execute(self, *_args):
            pass

        def fetchone(self):
            return ("U1", "Alice", "NguoiDung", password_hash)

    class Connection:
        closed = False

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(auth, "get_business_db_connection", lambda: connection)

    with pytest.raises(HTTPException) as error:
        auth.login(auth.LoginRequest(
            ten_dang_nhap="alice",
            mat_khau="correct password",
        ))

    assert error.value.status_code == 503
    assert error.value.detail == "Username/password authentication is not configured."
    assert connection.closed


def test_login_returns_503_when_database_connection_fails(monkeypatch):
    configure_auth(monkeypatch)

    def fail_connection():
        raise RuntimeError("SQL Server is unavailable.")

    monkeypatch.setattr(auth, "get_business_db_connection", fail_connection)

    with pytest.raises(HTTPException) as error:
        auth.login(auth.LoginRequest(
            ten_dang_nhap="alice",
            mat_khau="correct password",
        ))

    assert error.value.status_code == 503
    assert error.value.detail == "Authentication is temporarily unavailable."


def test_auth_me_validates_bearer_token_and_returns_database_user(monkeypatch):
    configure_auth(monkeypatch)

    class Cursor:
        def execute(self, query, subject):
            assert "FROM dbo.NGUOI_DUNG" in query
            assert subject == "U1"

        def fetchone(self):
            return ("U1", "User One", "NguoiDung")

    class Connection:
        closed = False

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(
        security,
        "get_business_db_connection",
        lambda: connection,
    )
    from fastapi.testclient import TestClient

    response = TestClient(app).get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {create_token()}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ma_nd": "U1",
        "vai_tro": "NguoiDung",
        "ho_ten": "User One",
    }
    assert connection.closed


def test_login_and_auth_me_http_endpoints_work_together(monkeypatch):
    configure_auth(monkeypatch)
    password_hash = security.hash_password("correct password")

    class Cursor:
        query = ""

        def execute(self, query, *_params):
            self.query = query

        def fetchone(self):
            if "MatKhauHash" in self.query:
                return ("U1", "User One", "NguoiDung", password_hash)
            return ("U1", "User One", "NguoiDung")

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(auth, "get_business_db_connection", Connection)
    monkeypatch.setattr(security, "get_business_db_connection", Connection)

    from fastapi.testclient import TestClient

    client = TestClient(app)
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "ten_dang_nhap": "alice",
            "mat_khau": "correct password",
        },
    )

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["token_type"] == "bearer"
    assert login_data["user"]["ma_nd"] == "U1"
    assert login_data["user"]["vai_tro"] == "NguoiDung"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json() == {
        "ma_nd": "U1",
        "vai_tro": "NguoiDung",
        "ho_ten": "User One",
    }


def test_session_owner_mismatch_is_rejected_before_inserts(monkeypatch):
    class Cursor:
        calls = 0

        def execute(self, *_args):
            self.calls += 1

        def fetchone(self):
            return ("U1",) if self.calls == 1 else ("U2",)

    class Connection:
        def __init__(self):
            self.database_cursor = Cursor()
            self.rolled_back = False
            self.closed = False

        def cursor(self):
            return self.database_cursor

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(
        chat,
        "get_business_db_connection",
        lambda: connection,
    )

    with pytest.raises(HTTPException) as error:
        chat.save_chat_result(
            request=chat.ChatRequest(
                ma_phien="S1",
                ma_nd="U1",
                noi_dung_cau_hoi="Question",
            ),
            ma_cau_hoi="Q1",
            ma_cau_tra_loi="A1",
            trace_id="trace",
            answer="Answer",
            status="ThanhCong",
            confidence=0.9,
            refusal_reason=None,
            chunks=[],
        )

    assert error.value.status_code == 403
    assert connection.database_cursor.calls == 2
    assert connection.rolled_back
    assert connection.closed


def test_protected_routes_reject_requests_without_tokens():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1", json={
        "ma_phien": "S1",
        "ma_nd": "U1",
        "noi_dung_cau_hoi": "Question",
    }).status_code == 401
    assert client.get("/api/v1/history/sessions?ma_nd=U1").status_code == 401
    assert client.put("/api/v1/documents/approve/PB1").status_code == 401
    assert client.get("/api/v1/evaluation/latest").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_route_roles_and_history_identity_are_server_enforced():
    from fastapi.testclient import TestClient

    app.dependency_overrides[security.get_current_user] = lambda: (
        AuthenticatedUser(ma_nd="U1", vai_tro="NguoiDung")
    )
    try:
        client = TestClient(app)
        assert client.put("/api/v1/documents/approve/PB1").status_code == 403
        assert client.get("/api/v1/evaluation/latest").status_code == 403
        assert client.get(
            "/api/v1/history/sessions?ma_nd=U2"
        ).status_code == 403
    finally:
        app.dependency_overrides.pop(security.get_current_user, None)


def test_chat_rejects_a_caller_supplied_identity_mismatch():
    with pytest.raises(HTTPException) as error:
        import asyncio

        asyncio.run(chat.chat_with_rag(
            chat.ChatRequest(
                ma_phien="S1",
                ma_nd="U2",
                noi_dung_cau_hoi="Question",
            ),
            AuthenticatedUser(ma_nd="U1", vai_tro="NguoiDung"),
        ))

    assert error.value.status_code == 403


def test_login_uses_database_username_and_persisted_password_hash(monkeypatch):
    configure_auth(monkeypatch)
    password_hash = security.hash_password("correct horse battery staple")

    class Cursor:
        def execute(self, query, username):
            assert "TenDangNhap = ?" in query
            assert "MatKhauHash" in query
            assert username == "alice"

        def fetchone(self):
            return ("U1", "Alice", "NguoiDung", password_hash)

    class Connection:
        closed = False

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(
        auth,
        "get_business_db_connection",
        lambda: connection,
    )

    response = auth.login(auth.LoginRequest(
        ten_dang_nhap=" alice ",
        mat_khau="correct horse battery staple",
    ))

    claims = security._verify_token(response.access_token)
    assert response.token_type == "bearer"
    assert response.expires_in == 3600
    assert response.user.ma_nd == "U1"
    assert response.user.vai_tro == "NguoiDung"
    assert claims["sub"] == "U1"
    assert connection.closed


def test_login_rejects_wrong_password_and_unsupported_legacy_hash(monkeypatch):
    configure_auth(monkeypatch)

    class Cursor:
        def __init__(self, stored_hash):
            self.stored_hash = stored_hash

        def execute(self, *_args):
            pass

        def fetchone(self):
            return ("U1", "Alice", "NguoiDung", self.stored_hash)

    class Connection:
        def __init__(self, stored_hash):
            self.stored_hash = stored_hash

        def cursor(self):
            return Cursor(self.stored_hash)

        def close(self):
            pass

    valid_hash = security.hash_password("correct password")
    for stored_hash, password in (
        (valid_hash, "incorrect password"),
        ("legacy-plaintext-or-unknown", "correct password"),
    ):
        monkeypatch.setattr(
            auth,
            "get_business_db_connection",
            lambda stored_hash=stored_hash: Connection(stored_hash),
        )
        with pytest.raises(HTTPException) as error:
            auth.login(auth.LoginRequest(
                ten_dang_nhap="alice",
                mat_khau=password,
            ))
        assert error.value.status_code == 401
        assert error.value.detail == "Invalid username or password."


def test_login_rejects_unknown_username_with_generic_error(monkeypatch):
    configure_auth(monkeypatch)

    class Cursor:
        def execute(self, query, username):
            assert "WHERE TenDangNhap = ?" in query
            assert username == "unknown-user"

        def fetchone(self):
            return None

    class Connection:
        closed = False

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr(
        auth,
        "get_business_db_connection",
        lambda: connection,
    )

    with pytest.raises(HTTPException) as error:
        auth.login(auth.LoginRequest(
            ten_dang_nhap="unknown-user",
            mat_khau="any password",
        ))

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid username or password."
    assert error.value.headers["WWW-Authenticate"] == "Bearer"
    assert connection.closed


def test_password_hash_round_trip_and_rejects_unrecognized_formats():
    stored_hash = security.hash_password("example password")

    assert security.verify_password("example password", stored_hash)
    assert not security.verify_password("wrong password", stored_hash)
    assert not security.verify_password("example password", "plain-text")
    assert not security.verify_password("123", "123")
    assert not security.verify_password(
        "any password",
        "DEMO_ONLY_NOT_FOR_LOGIN",
    )


def test_password_hash_uses_a_unique_salt_for_each_password():
    first_hash = security.hash_password("same password")
    second_hash = security.hash_password("same password")

    assert first_hash != second_hash
    assert security.verify_password("same password", first_hash)
    assert security.verify_password("same password", second_hash)
