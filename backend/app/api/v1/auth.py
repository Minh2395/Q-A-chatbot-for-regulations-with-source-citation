import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.database import get_business_db_connection
from app.core.security import (
    VALID_ROLES,
    AuthenticatedUser,
    get_current_user,
    is_supported_password_hash,
    issue_access_token,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger("AIK01.Authentication")


class LoginRequest(BaseModel):
    ten_dang_nhap: str = Field(..., min_length=1, max_length=50)
    mat_khau: str = Field(..., min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUser


def _burn_password_check(password: str) -> None:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"AIK-01-unknown-account-salt",
        600_000,
        dklen=32,
    )
    hmac.compare_digest(digest, bytes(32))


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    username = request.ten_dang_nhap.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    connection = None
    try:
        connection = get_business_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT MaND, HoTen, VaiTro, MatKhauHash
            FROM dbo.NGUOI_DUNG
            WHERE TenDangNhap = ?
            """,
            username,
        )
        row = cursor.fetchone()
    except Exception as error:
        logger.exception("Could not retrieve account for login.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        ) from error
    finally:
        if connection:
            connection.close()

    if not row:
        _burn_password_check(request.mat_khau)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stored_hash = row[3]
    valid_password = (
        isinstance(stored_hash, str)
        and verify_password(request.mat_khau, stored_hash)
    )
    if not valid_password:
        if not isinstance(stored_hash, str) or not is_supported_password_hash(
            stored_hash
        ):
            _burn_password_check(request.mat_khau)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = str(row[2] or "")
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The account does not have an authorized role.",
        )

    user = AuthenticatedUser(
        ma_nd=str(row[0]),
        ho_ten=str(row[1]) if row[1] is not None else None,
        vai_tro=role,
    )
    token, expires_in = issue_access_token(user.ma_nd)
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=user,
    )


@router.get("/me", response_model=AuthenticatedUser)
def get_authenticated_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    return current_user
