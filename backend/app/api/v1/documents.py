import uuid

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status

from app.services.chunking import (
    extract_chunks_from_pdf,
    extract_chunks_from_docx,
    extract_chunks_from_html,
)
from app.services.embedding import generate_vector_embedding
from app.core.database import get_business_db_connection


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    ma_tai_lieu: str = Form(...),
    so_phien_ban: str = Form(...),
    ma_nd: str = Form(...),
):
    """
    Upload tài liệu PDF, DOCX, HTML hoặc HTM.

    Quy trình:
    1. Trích xuất nội dung thành các chunk.
    2. Tạo embedding bằng Ollama.
    3. Lưu phiên bản ở trạng thái Draft.
    4. Lưu chunk và vector qua Stored Procedure.
    """

    filename = (file.filename or "").lower()

    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên file không hợp lệ.",
        )

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File tải lên đang rỗng.",
        )

    # 1. Trích xuất nội dung theo định dạng file
    try:
        if filename.endswith(".pdf"):
            chunks = extract_chunks_from_pdf(file_bytes)

        elif filename.endswith(".docx"):
            chunks = extract_chunks_from_docx(file_bytes)

        elif filename.endswith((".html", ".htm")):
            chunks = extract_chunks_from_html(file_bytes)

        elif filename.endswith(".doc"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Định dạng .doc chưa được hỗ trợ trực tiếp. "
                    "Vui lòng chuyển sang .docx."
                ),
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Hệ thống chỉ hỗ trợ file .pdf, .docx, .html và .htm."
                ),
            )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể đọc nội dung file: {str(e)}",
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể bóc tách nội dung từ file tải lên.",
        )

    # 2. Tạo mã phiên bản
    ma_phien_ban = f"PB_{uuid.uuid4().hex[:8].upper()}"

    conn = None

    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()

        # 3. Tạo phiên bản ở trạng thái Draft
        cursor.execute(
            """
            INSERT INTO PHIEN_BAN_TAI_LIEU
                (
                    MaPhienBan,
                    MaTaiLieu,
                    MaND,
                    SoPhienBan,
                    TrangThai,
                    DuongDanFile,
                    is_active
                )
            VALUES (?, ?, ?, ?, 'Draft', ?, 0)
            """,
            (
                ma_phien_ban,
                ma_tai_lieu,
                ma_nd,
                so_phien_ban,
                file.filename,
            ),
        )

        # 4. Tạo embedding và lưu chunk/vector
        for chunk in chunks:
            ma_doan = f"D_{uuid.uuid4().hex[:10].upper()}"

            vector_bytes = await generate_vector_embedding(
                chunk["noi_dung"]
            )

            cursor.execute(
                """
                EXEC sp_InsertChunkAndVector
                    @MaDoan = ?,
                    @MaPhienBan = ?,
                    @ThuTu = ?,
                    @DieuKhoan = ?,
                    @NoiDung = ?,
                    @SoTrang = ?,
                    @VectorData = ?
                """,
                (
                    ma_doan,
                    ma_phien_ban,
                    chunk["thu_tu"],
                    chunk["dieu_khoan"],
                    chunk["noi_dung"],
                    chunk["so_trang"],
                    vector_bytes,
                ),
            )

        conn.commit()

        return {
            "message": (
                f"Nạp thành công {len(chunks)} đoạn văn bản "
                f"từ file {file.filename}."
            ),
            "ma_phien_ban": ma_phien_ban,
            "so_phien_ban": so_phien_ban,
            "so_doan": len(chunks),
            "trang_thai": "Draft",
        }

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống khi lưu CSDL: {str(e)}",
        )

    finally:
        if conn:
            conn.close()


@router.put("/approve/{ma_phien_ban}")
async def approve_document_version(ma_phien_ban: str):
    """
    Phê duyệt phiên bản tài liệu.

    Trigger trg_AutoDeactivateOldVersions chịu trách nhiệm
    xử lý các phiên bản cũ theo cấu hình SQL Server.
    """

    conn = None

    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE PHIEN_BAN_TAI_LIEU
            SET TrangThai = 'Approved',
                is_active = 1,
                NgayHieuLuc = GETDATE()
            WHERE MaPhienBan = ?
              AND TrangThai = 'Draft'
            """,
            (ma_phien_ban,),
        )

        if cursor.rowcount == 0:
            conn.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Không tìm thấy phiên bản hoặc phiên bản "
                    "không ở trạng thái Draft."
                ),
            )

        conn.commit()

        return {
            "message": f"Đã phê duyệt phiên bản {ma_phien_ban}.",
            "ma_phien_ban": ma_phien_ban,
            "trang_thai": "Approved",
            "is_active": 1,
        }

    except HTTPException:
        raise

    except Exception as e:
        if conn:
            conn.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi duyệt phiên bản: {str(e)}",
        )

    finally:
        if conn:
            conn.close()
