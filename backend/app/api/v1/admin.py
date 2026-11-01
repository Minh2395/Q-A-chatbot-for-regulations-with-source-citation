import json
import logging
import uuid
from collections import deque
from pathlib import Path
from typing import Any

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.database import get_business_db_connection
from app.core.security import (
    VALID_ROLES,
    AuthenticatedUser,
    hash_password,
    require_roles,
)
from app.services.audit import AUDIT_FILE, write_audit_log


router = APIRouter(prefix="/admin", tags=["Administration"])
logger = logging.getLogger("AIK01.Administration")


class UserSummary(BaseModel):
    ma_nd: str
    ten_dang_nhap: str
    ho_ten: str | None
    email: str | None
    vai_tro: str | None


class UserCreate(BaseModel):
    ten_dang_nhap: str = Field(..., min_length=1, max_length=50)
    mat_khau: str = Field(..., min_length=12, max_length=1024)
    ho_ten: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=100)
    vai_tro: str = Field(..., min_length=1, max_length=50)


class UserUpdate(BaseModel):
    ten_dang_nhap: str | None = Field(default=None, min_length=1, max_length=50)
    mat_khau: str | None = Field(default=None, min_length=12, max_length=1024)
    ho_ten: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=100)
    vai_tro: str | None = Field(default=None, min_length=1, max_length=50)


class AuditLogPage(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


def _validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported user role.",
        )


def _user_summary(row: Any) -> UserSummary:
    return UserSummary(
        ma_nd=str(row[0]),
        ten_dang_nhap=str(row[1]),
        ho_ten=str(row[2]) if row[2] is not None else None,
        email=str(row[3]) if row[3] is not None else None,
        vai_tro=str(row[4]) if row[4] is not None else None,
    )


def _database_unavailable(error: Exception, operation: str) -> HTTPException:
    logger.error(
        "Admin database operation failed (%s): %s",
        operation,
        type(error).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The administration service is temporarily unavailable.",
    )


@router.get("/users", response_model=list[UserSummary])
def list_users(
    _current_user: AuthenticatedUser = Depends(require_roles("QuanTriVien")),
) -> list[UserSummary]:
    connection = None
    try:
        connection = get_business_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT MaND, TenDangNhap, HoTen, Email, VaiTro
            FROM dbo.NGUOI_DUNG
            ORDER BY TenDangNhap
            """
        )
        return [_user_summary(row) for row in cursor.fetchall()]
    except Exception as error:
        raise _database_unavailable(error, "list users") from error
    finally:
        if connection:
            connection.close()


@router.post(
    "/users",
    response_model=UserSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: UserCreate,
    current_user: AuthenticatedUser = Depends(require_roles("QuanTriVien")),
) -> UserSummary:
    _validate_role(request.vai_tro)
    username = request.ten_dang_nhap.strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username must not be blank.",
        )
    user_id = "U" + uuid.uuid4().hex[:19]
    password_hash = hash_password(request.mat_khau)
    connection = None
    try:
        connection = get_business_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO dbo.NGUOI_DUNG
                (MaND, TenDangNhap, MatKhauHash, HoTen, Email, VaiTro)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            user_id,
            username,
            password_hash,
            request.ho_ten,
            request.email,
            request.vai_tro,
        )
        cursor.execute(
            """
            SELECT MaND, TenDangNhap, HoTen, Email, VaiTro
            FROM dbo.NGUOI_DUNG
            WHERE MaND = ?
            """,
            user_id,
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Inserted account could not be reloaded.")
        connection.commit()
        write_audit_log(
            event="ADMIN_USER_CREATED",
            trace_id=str(uuid.uuid4()),
            ma_nd=current_user.ma_nd,
            status="Completed",
            details={"target_user_id": user_id, "role": request.vai_tro},
        )
        return _user_summary(row)
    except pyodbc.IntegrityError as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or generated account ID already exists.",
        ) from error
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as error:
        if connection:
            connection.rollback()
        raise _database_unavailable(error, "create user") from error
    finally:
        if connection:
            connection.close()


@router.patch("/users/{user_id}", response_model=UserSummary)
def update_user(
    user_id: str,
    request: UserUpdate,
    current_user: AuthenticatedUser = Depends(require_roles("QuanTriVien")),
) -> UserSummary:
    changes = request.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one account field must be provided.",
        )
    if any(
        field in changes and changes[field] is None
        for field in ("ten_dang_nhap", "mat_khau", "vai_tro")
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username, password, and role cannot be null.",
        )
    if user_id == current_user.ma_nd and "vai_tro" in changes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot change your own role.",
        )
    if "vai_tro" in changes and changes["vai_tro"] is not None:
        _validate_role(changes["vai_tro"])

    column_names = {
        "ten_dang_nhap": "TenDangNhap",
        "ho_ten": "HoTen",
        "email": "Email",
        "vai_tro": "VaiTro",
    }
    assignments: list[str] = []
    parameters: list[Any] = []
    for field, column in column_names.items():
        if field in changes:
            assignments.append(f"{column} = ?")
            value = changes[field]
            if field == "ten_dang_nhap":
                value = value.strip()
                if not value:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Username must not be blank.",
                    )
            parameters.append(value)
    if "mat_khau" in changes:
        assignments.append("MatKhauHash = ?")
        parameters.append(hash_password(changes["mat_khau"]))
    parameters.append(user_id)

    connection = None
    try:
        connection = get_business_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            f"UPDATE dbo.NGUOI_DUNG SET {', '.join(assignments)} WHERE MaND = ?",
            *parameters,
        )
        if cursor.rowcount == 0:
            connection.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account was not found.",
            )
        cursor.execute(
            """
            SELECT MaND, TenDangNhap, HoTen, Email, VaiTro
            FROM dbo.NGUOI_DUNG
            WHERE MaND = ?
            """,
            user_id,
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Updated account could not be reloaded.")
        connection.commit()
        write_audit_log(
            event="ADMIN_USER_UPDATED",
            trace_id=str(uuid.uuid4()),
            ma_nd=current_user.ma_nd,
            status="Completed",
            details={
                "target_user_id": user_id,
                "updated_fields": sorted(changes),
            },
        )
        return _user_summary(row)
    except pyodbc.IntegrityError as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username conflicts with an existing account.",
        ) from error
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as error:
        if connection:
            connection.rollback()
        raise _database_unavailable(error, "update user") from error
    finally:
        if connection:
            connection.close()


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current_user: AuthenticatedUser = Depends(require_roles("QuanTriVien")),
) -> None:
    if user_id == current_user.ma_nd:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot delete your own account.",
        )

    connection = None
    try:
        connection = get_business_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM dbo.NGUOI_DUNG WHERE MaND = ?",
            user_id,
        )
        if cursor.rowcount == 0:
            connection.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account was not found.",
            )
        connection.commit()
        write_audit_log(
            event="ADMIN_USER_DELETED",
            trace_id=str(uuid.uuid4()),
            ma_nd=current_user.ma_nd,
            status="Completed",
            details={"target_user_id": user_id},
        )
    except pyodbc.IntegrityError as error:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is referenced by existing records and cannot be deleted.",
        ) from error
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as error:
        if connection:
            connection.rollback()
        raise _database_unavailable(error, "delete user") from error
    finally:
        if connection:
            connection.close()


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    event: str | None = Query(default=None, max_length=100),
    user_id: str | None = Query(default=None, max_length=20),
    _current_user: AuthenticatedUser = Depends(require_roles("QuanTriVien")),
) -> AuditLogPage:
    retained: deque[dict[str, Any]] = deque(maxlen=offset + limit + 1)
    total = 0
    try:
        if Path(AUDIT_FILE).exists():
            with Path(AUDIT_FILE).open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Audit log contains invalid JSON at line {line_number}.",
                        ) from error
                    if not isinstance(record, dict):
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Audit log contains an invalid record at line {line_number}.",
                        )
                    if event and record.get("event") != event:
                        continue
                    if user_id and record.get("ma_nd") != user_id:
                        continue
                    total += 1
                    retained.append(record)
    except HTTPException:
        raise
    except OSError as error:
        logger.error("Could not read audit log: %s", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The audit log is temporarily unavailable.",
        ) from error

    newest_first = list(reversed(retained))
    items = newest_first[offset : offset + limit]
    return AuditLogPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
