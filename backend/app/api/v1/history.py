
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.core.database import get_business_db_connection
from app.core.security import AuthenticatedUser, get_current_user

router = APIRouter(
    prefix="/history",
    tags=["History"]
)


def row_to_dict(cursor, row):
    """Chuyển một dòng SQL thành dictionary."""
    if row is None:
        return None

    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


@router.get("/sessions")
def get_chat_sessions(
    ma_nd: Optional[str] = Query(None, description="Mã người dùng"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lấy danh sách phiên hội thoại của một người dùng.
    Mỗi phiên có thời gian bắt đầu, số câu hỏi và câu hỏi gần nhất.
    """

    if ma_nd and ma_nd != current_user.ma_nd:
        raise HTTPException(
            status_code=403,
            detail="The requested user does not match the authenticated account.",
        )

    conn = None

    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                p.MaPhien,
                p.MaND,
                p.ThoiGianBatDau,
                p.ThoiGianKetThuc,
                COUNT(q.MaCauHoi) AS TongSoCauHoi,
                MAX(q.ThoiDiem) AS ThoiDiemCauHoiGanNhat
            FROM PHIEN_HOI_DAP p
            LEFT JOIN CAU_HOI q
                ON p.MaPhien = q.MaPhien
            WHERE p.MaND = ?
            GROUP BY
                p.MaPhien,
                p.MaND,
                p.ThoiGianBatDau,
                p.ThoiGianKetThuc
            ORDER BY
                COALESCE(MAX(q.ThoiDiem), p.ThoiGianBatDau) DESC
            """,
            current_user.ma_nd
        )

        rows = cursor.fetchall()
        sessions = [
            row_to_dict(cursor, row)
            for row in rows
        ]

        return {
            "ma_nd": current_user.ma_nd,
            "tong_so_phien": len(sessions),
            "danh_sach_phien": sessions
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Không thể lấy lịch sử hội thoại: {str(e)}"
        )

    finally:
        if conn:
            conn.close()


@router.get("/sessions/{ma_phien}")
def get_chat_session_detail(
    ma_phien: str,
    ma_nd: Optional[str] = Query(None, description="Mã người dùng"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Lấy toàn bộ câu hỏi, câu trả lời và trích dẫn
    của một phiên hội thoại thuộc người dùng.
    """

    if ma_nd and ma_nd != current_user.ma_nd:
        raise HTTPException(
            status_code=403,
            detail="The requested user does not match the authenticated account.",
        )

    conn = None

    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()

        # 1. Kiểm tra phiên hội thoại và quyền sở hữu
        cursor.execute(
            """
            SELECT
                MaPhien,
                MaND,
                ThoiGianBatDau,
                ThoiGianKetThuc
            FROM PHIEN_HOI_DAP
            WHERE MaPhien = ?
              AND MaND = ?
            """,
            ma_phien,
            current_user.ma_nd
        )

        session_row = cursor.fetchone()

        if not session_row:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy phiên hội thoại."
            )

        session = row_to_dict(cursor, session_row)

        # 2. Lấy câu hỏi và câu trả lời
        cursor.execute(
            """
            SELECT
                q.MaCauHoi,
                q.NoiDung AS NoiDungCauHoi,
                q.ThoiDiem,
                a.MaCauTraLoi,
                a.NoiDung AS NoiDungTraLoi,
                a.TrangThai,
                a.DoTinCay,
                a.LyDoTuChoi,
                a.TraceId
            FROM CAU_HOI q
            LEFT JOIN CAU_TRA_LOI a
                ON q.MaCauHoi = a.MaCauHoi
            WHERE q.MaPhien = ?
            ORDER BY q.ThoiDiem ASC
            """,
            ma_phien
        )

        message_rows = cursor.fetchall()

        messages = [
            row_to_dict(cursor, row)
            for row in message_rows
        ]

        # 3. Lấy trích dẫn cho từng câu trả lời
        for message in messages:
            message["trich_dan"] = []

            ma_cau_tra_loi = message.get("MaCauTraLoi")

            if not ma_cau_tra_loi:
                continue

            cursor.execute(
                """
                SELECT
                    td.MaTrichDan,
                    td.ThuTu,
                    td.DoanTrich,
                    d.MaDoan,
                    d.DieuKhoan,
                    d.SoTrang,
                    p.MaPhienBan,
                    p.SoPhienBan,
                    t.TieuDe AS TenTaiLieu
                FROM TRICH_DAN td
                INNER JOIN DOAN_VAN_BAN d
                    ON td.MaDoan = d.MaDoan
                INNER JOIN PHIEN_BAN_TAI_LIEU p
                    ON d.MaPhienBan = p.MaPhienBan
                INNER JOIN TAI_LIEU t
                    ON p.MaTaiLieu = t.MaTaiLieu
                WHERE td.MaCauTraLoi = ?
                ORDER BY td.ThuTu ASC
                """,
                ma_cau_tra_loi
            )

            citation_rows = cursor.fetchall()

            message["trich_dan"] = [
                row_to_dict(cursor, row)
                for row in citation_rows
            ]

        return {
            "phien": session,
            "tong_so_tin_nhan": len(messages),
            "lich_su": messages
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Không thể lấy chi tiết lịch sử: {str(e)}"
        )

    finally:
        if conn:
            conn.close()
