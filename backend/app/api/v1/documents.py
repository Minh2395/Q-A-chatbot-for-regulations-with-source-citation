import logging
import uuid
from datetime import datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    UploadFile,
    File,
    Form,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
import pyodbc

from app.api.v1.evaluation import run_evaluation_for_document
from app.services.chunking import (
    extract_chunks_from_pdf,
    extract_chunks_from_docx,
    extract_chunks_from_html,
)
from app.services.embedding import generate_vector_embedding
from app.core.database import get_business_db_connection
from app.core.security import AuthenticatedUser, require_roles
from app.services.audit import write_audit_log


router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger("AIK01.Documents")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class DocumentCatalogCreate(BaseModel):
    tieu_de: str = Field(..., min_length=1, max_length=255)
    loai_van_ban: str = Field(..., min_length=1, max_length=25)
    linh_vuc: str | None = Field(default=None, max_length=100)
    co_quan_ban_hanh: str | None = Field(default=None, max_length=150)


class DocumentCatalogItem(BaseModel):
    ma_tai_lieu: str
    tieu_de: str
    loai_van_ban: str
    linh_vuc: str | None
    co_quan_ban_hanh: str | None


class DocumentVersionItem(BaseModel):
    ma_phien_ban: str
    ma_tai_lieu: str
    tieu_de: str
    ma_nguoi_tai: str | None
    ten_dang_nhap_nguoi_tai: str | None
    so_phien_ban: str
    trang_thai: str | None
    is_active: bool
    duong_dan_file: str | None
    ngay_hieu_luc: datetime | None


class DocumentChunkItem(BaseModel):
    ma_doan: str
    thu_tu: int | None
    dieu_khoan: str | None
    noi_dung: str
    so_trang: int | None


@router.get("/catalog", response_model=list[DocumentCatalogItem])
def list_document_catalog(
    _current_user: AuthenticatedUser = Depends(
        require_roles("ChuyenVienPhapChe")
    ),
) -> list[DocumentCatalogItem]:
    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT MaTaiLieu, TieuDe, LoaiVanBan, LinhVuc, CoQuanBanHanh
            FROM dbo.TAI_LIEU
            ORDER BY TieuDe, MaTaiLieu
            """
        )
        return [
            DocumentCatalogItem(
                ma_tai_lieu=str(row[0]),
                tieu_de=str(row[1]),
                loai_van_ban=str(row[2]),
                linh_vuc=str(row[3]) if row[3] is not None else None,
                co_quan_ban_hanh=str(row[4]) if row[4] is not None else None,
            )
            for row in cursor.fetchall()
        ]
    except Exception as error:
        logger.exception("Could not load legal document catalog.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tải danh mục tài liệu.",
        ) from error
    finally:
        if conn:
            conn.close()


@router.post(
    "/catalog",
    response_model=DocumentCatalogItem,
    status_code=status.HTTP_201_CREATED,
)
def create_document_catalog_item(
    request: DocumentCatalogCreate,
    current_user: AuthenticatedUser = Depends(
        require_roles("ChuyenVienPhapChe")
    ),
) -> DocumentCatalogItem:
    title = request.tieu_de.strip()
    document_type = request.loai_van_ban.strip().upper()
    if not title or not document_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tên và loại tài liệu không được để trống.",
        )
    document_id = f"TL{uuid.uuid4().hex[:18].upper()}"
    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO dbo.TAI_LIEU
                (MaTaiLieu, TieuDe, LoaiVanBan, LinhVuc, CoQuanBanHanh)
            VALUES (?, ?, ?, ?, ?)
            """,
            document_id,
            title,
            document_type,
            request.linh_vuc.strip() if request.linh_vuc and request.linh_vuc.strip() else None,
            (
                request.co_quan_ban_hanh.strip()
                if request.co_quan_ban_hanh and request.co_quan_ban_hanh.strip()
                else None
            ),
        )
        conn.commit()
        write_audit_log(
            event="DOCUMENT_CATALOG_CREATED",
            trace_id=str(uuid.uuid4()),
            ma_nd=current_user.ma_nd,
            status="Completed",
            details={"ma_tai_lieu": document_id, "loai_van_ban": document_type},
        )
        return DocumentCatalogItem(
            ma_tai_lieu=document_id,
            tieu_de=title,
            loai_van_ban=document_type,
            linh_vuc=request.linh_vuc.strip() if request.linh_vuc and request.linh_vuc.strip() else None,
            co_quan_ban_hanh=(
                request.co_quan_ban_hanh.strip()
                if request.co_quan_ban_hanh and request.co_quan_ban_hanh.strip()
                else None
            ),
        )
    except pyodbc.IntegrityError as error:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể tạo hồ sơ tài liệu do dữ liệu bị trùng.",
        ) from error
    except Exception as error:
        if conn:
            conn.rollback()
        logger.exception("Could not create legal document catalog item.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tạo hồ sơ tài liệu.",
        ) from error
    finally:
        if conn:
            conn.close()


@router.get("/versions", response_model=list[DocumentVersionItem])
def list_document_versions(
    trang_thai: str | None = None,
    _current_user: AuthenticatedUser = Depends(
        require_roles("ChuyenVienPhapChe")
    ),
) -> list[DocumentVersionItem]:
    if trang_thai is not None and trang_thai not in {
        "Draft",
        "Approved",
        "Rejected",
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Trạng thái phiên bản không hợp lệ.",
        )
    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT
                p.MaPhienBan,
                p.MaTaiLieu,
                d.TieuDe,
                p.MaND,
                u.TenDangNhap,
                p.SoPhienBan,
                p.TrangThai,
                p.is_active,
                p.DuongDanFile,
                p.NgayHieuLuc
            FROM dbo.PHIEN_BAN_TAI_LIEU p
            INNER JOIN dbo.TAI_LIEU d ON d.MaTaiLieu = p.MaTaiLieu
            LEFT JOIN dbo.NGUOI_DUNG u ON u.MaND = p.MaND
        """
        parameters: tuple[str, ...] = ()
        if trang_thai is not None:
            query += " WHERE p.TrangThai = ?"
            parameters = (trang_thai,)
        query += " ORDER BY p.MaPhienBan DESC"
        cursor.execute(query, *parameters)
        return [
            DocumentVersionItem(
                ma_phien_ban=str(row[0]),
                ma_tai_lieu=str(row[1]),
                tieu_de=str(row[2]),
                ma_nguoi_tai=str(row[3]) if row[3] is not None else None,
                ten_dang_nhap_nguoi_tai=(
                    str(row[4]) if row[4] is not None else None
                ),
                so_phien_ban=str(row[5]),
                trang_thai=str(row[6]) if row[6] is not None else None,
                is_active=bool(row[7]),
                duong_dan_file=str(row[8]) if row[8] is not None else None,
                ngay_hieu_luc=row[9],
            )
            for row in cursor.fetchall()
        ]
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Could not load document versions.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tải danh sách phiên bản tài liệu.",
        ) from error
    finally:
        if conn:
            conn.close()


@router.get(
    "/versions/{ma_phien_ban}/chunks",
    response_model=list[DocumentChunkItem],
)
def get_document_version_chunks(
    ma_phien_ban: str,
    _current_user: AuthenticatedUser = Depends(
        require_roles("ChuyenVienPhapChe")
    ),
) -> list[DocumentChunkItem]:
    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM dbo.PHIEN_BAN_TAI_LIEU WHERE MaPhienBan = ?",
            ma_phien_ban,
        )
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phiên bản tài liệu.",
            )
        cursor.execute(
            """
            SELECT MaDoan, ThuTu, DieuKhoan, NoiDung, SoTrang
            FROM dbo.DOAN_VAN_BAN
            WHERE MaPhienBan = ?
            ORDER BY ThuTu, MaDoan
            """,
            ma_phien_ban,
        )
        return [
            DocumentChunkItem(
                ma_doan=str(row[0]),
                thu_tu=int(row[1]) if row[1] is not None else None,
                dieu_khoan=str(row[2]) if row[2] is not None else None,
                noi_dung=str(row[3]),
                so_trang=int(row[4]) if row[4] is not None else None,
            )
            for row in cursor.fetchall()
        ]
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(
            "Could not load chunks for document version %s.",
            ma_phien_ban,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tải nội dung đã trích xuất.",
        ) from error
    finally:
        if conn:
            conn.close()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    ma_tai_lieu: str = Form(...),
    so_phien_ban: str = Form(...),
    ma_nd: str = Form(...),
    current_user: AuthenticatedUser = Depends(
        require_roles("ChuyenVienPhapChe")
    ),
):
    """
    Upload tài liệu PDF, DOCX, HTML hoặc HTM.

    Quy trình:
    1. Trích xuất nội dung thành các chunk.
    2. Tạo embedding bằng Ollama.
    3. Lưu phiên bản ở trạng thái Draft.
    4. Lưu chunk và vector qua Stored Procedure.
    """

    if ma_nd != current_user.ma_nd:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The upload user must match the authenticated account.",
        )

    filename = (file.filename or "").lower()

    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên file không hợp lệ.",
        )

    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File tải lên đang rỗng.",
        )
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Kích thước tệp tối đa là 25 MB.",
        )

    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM dbo.TAI_LIEU WHERE MaTaiLieu = ?",
            ma_tai_lieu,
        )
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mã tài liệu không tồn tại. Hãy tạo hồ sơ tài liệu trước.",
            )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Could not validate document catalog reference.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kiểm tra hồ sơ tài liệu.",
        ) from error
    finally:
        if conn:
            conn.close()

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

    except Exception:
        logger.exception("Could not extract uploaded legal document.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể đọc nội dung file. Hãy kiểm tra định dạng và tính toàn vẹn.",
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
        write_audit_log(
            event="DOCUMENT_VERSION_UPLOADED",
            trace_id=str(uuid.uuid4()),
            ma_nd=current_user.ma_nd,
            status="Draft",
            details={
                "ma_tai_lieu": ma_tai_lieu,
                "ma_phien_ban": ma_phien_ban,
                "so_doan": len(chunks),
                "ten_file": file.filename,
            },
        )

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

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception:
        if conn:
            conn.rollback()

        logger.exception("Could not persist uploaded legal document.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể lưu tài liệu; vui lòng kiểm tra dịch vụ cơ sở dữ liệu và Ollama.",
        )

    finally:
        if conn:
            conn.close()


@router.put("/approve/{ma_phien_ban}")
async def approve_document_version(
    ma_phien_ban: str,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(
        require_roles("ChuyenVienPhapChe")
    ),
):
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
              AND MaND <> ?
            """,
            (ma_phien_ban, current_user.ma_nd),
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
        write_audit_log(
            event="DOCUMENT_VERSION_APPROVED",
            trace_id=str(uuid.uuid4()),
            ma_nd=current_user.ma_nd,
            status="Approved",
            details={"ma_phien_ban": ma_phien_ban},
        )

        background_tasks.add_task(
            run_evaluation_for_document,
            ma_phien_ban,
        )

        return {
            "message": f"Đã phê duyệt phiên bản {ma_phien_ban}.",
            "ma_phien_ban": ma_phien_ban,
            "trang_thai": "Approved",
            "is_active": 1,
            "evaluation_status": "Pending",
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
