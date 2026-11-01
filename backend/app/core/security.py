import base64
import binascii
import hashlib
import hmac
import json
import logging
import math
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_business_db_connection


logger = logging.getLogger("AIK01.Security")
bearer_scheme = HTTPBearer(auto_error=False)
VALID_ROLES = {
    "ChuyenVienPhapChe",
    "QuanTriVien",
    "NguoiDung",
}
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_HASH_MIN_ITERATIONS = 600_000
PASSWORD_HASH_MAX_ITERATIONS = 2_000_000
PASSWORD_HASH_SALT_BYTES = 16
PASSWORD_HASH_DIGEST_BYTES = 32


def _encode_base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_base64(value: str) -> bytes:
    if not value or any(char.isspace() for char in value):
        raise ValueError("Invalid base64 value.")
    padded_value = value + "=" * (-len(value) % 4)
    return base64.b64decode(
        padded_value,
        altchars=b"-_",
        validate=True,
    )


def hash_password(password: str) -> str:
    """Create the versioned PBKDF2 format required by the login endpoint."""
    salt = secrets.token_bytes(PASSWORD_HASH_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
        dklen=PASSWORD_HASH_DIGEST_BYTES,
    )
    return "$".join((
        PASSWORD_HASH_ALGORITHM,
        str(PASSWORD_HASH_ITERATIONS),
        _encode_base64(salt),
        _encode_base64(digest),
    ))


def _parse_password_hash(stored_hash: str) -> tuple[int, bytes, bytes] | None:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = stored_hash.split("$")
        if algorithm != PASSWORD_HASH_ALGORITHM:
            return None
        iterations = int(raw_iterations)
        if not PASSWORD_HASH_MIN_ITERATIONS <= iterations <= PASSWORD_HASH_MAX_ITERATIONS:
            return None
        salt = _decode_base64(raw_salt)
        expected_digest = _decode_base64(raw_digest)
        if (
            not PASSWORD_HASH_SALT_BYTES <= len(salt) <= 64
            or len(expected_digest) != PASSWORD_HASH_DIGEST_BYTES
        ):
            return None
    except (ValueError, TypeError, UnicodeEncodeError, binascii.Error):
        return None
    return iterations, salt, expected_digest


def is_supported_password_hash(stored_hash: str) -> bool:
    return _parse_password_hash(stored_hash) is not None


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify only the documented PBKDF2 encoding; reject unknown formats."""
    parsed_hash = _parse_password_hash(stored_hash)
    if parsed_hash is None:
        return False
    iterations, salt, expected_digest = parsed_hash
    try:
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=PASSWORD_HASH_DIGEST_BYTES,
        )
    except (TypeError, UnicodeEncodeError):
        return False
    return hmac.compare_digest(actual_digest, expected_digest)


class AuthenticatedUser(BaseModel):
    ma_nd: str
    vai_tro: str
    ho_ten: str | None = None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_segment(segment: str) -> dict[str, Any]:
    try:
        padded_segment = segment + "=" * (-len(segment) % 4)
        decoded = base64.b64decode(
            padded_segment,
            altchars=b"-_",
            validate=True,
        )
        value = json.loads(decoded)
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
    ) as error:
        raise ValueError("Malformed token segment.") from error

    if not isinstance(value, dict):
        raise ValueError("Token segment must be a JSON object.")
    return value


def _numeric_claim(claims: dict[str, Any], name: str) -> float:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid {name} claim.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Invalid {name} claim.")
    return number


def _verify_token(token: str) -> dict[str, Any]:
    secret = settings.AUTH_JWT_SECRET
    issuer = settings.AUTH_JWT_ISSUER
    audience = settings.AUTH_JWT_AUDIENCE
    if (
        not secret
        or len(secret.encode("utf-8")) < 32
        or not issuer
        or not audience
        or settings.AUTH_JWT_MAX_TTL_SECONDS < 1
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bearer-token authentication is not configured.",
        )

    if len(token) > 8192:
        raise _unauthorized()


    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise _unauthorized()

    try:
        header = _decode_segment(parts[0])
        claims = _decode_segment(parts[1])
        signature = parts[2]
        if header.get("alg") != "HS256" or header.get("crit"):
            raise ValueError("Unsupported token algorithm.")

        signed_content = f"{parts[0]}.{parts[1]}".encode("ascii")
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(
                secret.encode("utf-8"),
                signed_content,
                hashlib.sha256,
            ).digest()
        ).rstrip(b"=").decode("ascii")
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature.")

        now = time.time()
        issued_at = _numeric_claim(claims, "iat")
        expires_at = _numeric_claim(claims, "exp")
        not_before = claims.get("nbf")
        if not_before is not None:
            if _numeric_claim(claims, "nbf") > now + 30:
                raise ValueError("Token is not active.")

        if (
            issued_at > now + 30
            or expires_at <= now
            or expires_at <= issued_at
            or expires_at - issued_at > settings.AUTH_JWT_MAX_TTL_SECONDS
            or claims.get("iss") != issuer
        ):
            raise ValueError("Token claims are invalid.")

        token_audience = claims.get("aud")
        valid_audience = (
            token_audience == audience
            if isinstance(token_audience, str)
            else isinstance(token_audience, list) and audience in token_audience
        )
        subject = claims.get("sub")
        if (
            not valid_audience
            or not isinstance(subject, str)
            or not subject.strip()
            or not subject.isascii()
            or len(subject) > 20
        ):
            raise ValueError("Token identity claims are invalid.")
        return claims
    except (ValueError, TypeError, UnicodeEncodeError, OverflowError):
        raise _unauthorized()


def issue_access_token(subject: str) -> tuple[str, int]:
    """Issue a short-lived access token after successful password verification."""
    if (
        not settings.AUTH_JWT_SECRET
        or len(settings.AUTH_JWT_SECRET.encode("utf-8")) < 32
        or not settings.AUTH_JWT_ISSUER
        or not settings.AUTH_JWT_AUDIENCE
        or settings.AUTH_JWT_MAX_TTL_SECONDS < 1
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Username/password authentication is not configured.",
        )

    issued_at = int(time.time())
    expires_in = min(settings.AUTH_JWT_MAX_TTL_SECONDS, 3600)
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "sub": subject,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
        "iat": issued_at,
        "exp": issued_at + expires_in,
        "jti": secrets.token_urlsafe(16),
    }

    def encode_json(value: dict[str, Any]) -> str:
        return _encode_base64(
            json.dumps(
                value,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        )

    signing_input = f"{encode_json(header)}.{encode_json(claims)}"
    signature = hmac.new(
        settings.AUTH_JWT_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_encode_base64(signature)}", expires_in


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    claims = _verify_token(credentials.credentials)
    connection = None
    try:
        connection = get_business_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT MaND, HoTen, VaiTro
            FROM dbo.NGUOI_DUNG
            WHERE MaND = ?
            """,
            claims["sub"],
        )
        row = cursor.fetchone()
        if not row:
            raise _unauthorized()

        role = str(row[2] or "")
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The account does not have an authorized role.",
            )
        return AuthenticatedUser(
            ma_nd=str(row[0]),
            ho_ten=str(row[1]) if row[1] is not None else None,
            vai_tro=role,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Could not resolve authenticated database user.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User authorization is temporarily unavailable.",
        ) from error
    finally:
        if connection:
            connection.close()


def require_roles(*allowed_roles: str):
    def check_role(
        current_user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if current_user.vai_tro not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is not authorized for this operation.",
            )
        return current_user

    return check_role
