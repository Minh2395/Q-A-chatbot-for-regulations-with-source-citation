import uuid
import httpx
import math

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_business_db_connection
from app.services.rag_service import retrieve_evidence
from app.services.audit import generate_trace_id, audit_rag_step, audit_chat_result
from app.core.security import AuthenticatedUser, get_current_user


router = APIRouter()

# =========================================================
# CONFIGURATION
# =========================================================

REFUSAL_MESSAGE = (
    "Tôi chưa tìm thấy đủ bằng chứng từ các tài liệu đã được "
    "phê duyệt để trả lời câu hỏi này. Vui lòng thử diễn đạt "
    "lại câu hỏi hoặc liên hệ chuyên viên pháp chế."
)


# =========================================================
# REQUEST / RESPONSE SCHEMAS
# =========================================================

class ChatRequest(BaseModel):
    ma_phien: str = Field(..., min_length=1, max_length=20)
    ma_nd: str = Field(..., min_length=1, max_length=20)
    noi_dung_cau_hoi: str = Field(..., min_length=1)


class CitationSchema(BaseModel):
    ma_doan: str
    ten_tai_lieu: Optional[str] = None
    ma_phien_ban: Optional[str] = None
    so_phien_ban: Optional[str] = None
    dieu_khoan: Optional[str] = None
    so_trang: Optional[int] = None
    noi_dung_trich: str
    source_url: Optional[str] = None
    do_tuong_dong: float


class ChatResponse(BaseModel):
    ma_cau_tra_loi: str
    trace_id: str
    trang_thai: str
    do_tin_cay: float
    noi_dung_tra_loi: str
    ly_do_tu_choi: Optional[str] = None
    trich_dan: List[CitationSchema] = []


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def generate_id(prefix: str) -> str:
    """
    Sinh mã có độ dài tối đa 20 ký tự.
    """
    return prefix + uuid.uuid4().hex[:19]


def get_metadata_value(metadata: dict, *keys):
    """
    Lấy giá trị metadata theo nhiều tên khóa có thể gặp.
    """
    for key in keys:
        value = metadata.get(key)

        if value is not None and value != "":
            return value

    return None


async def generate_answer(
    question: str,
    evidence_chunks: list
) -> str:
    """
    Gọi Ollama LLM để sinh câu trả lời dựa trên bằng chứng.
    """

    context_parts = []

    for index, chunk in enumerate(evidence_chunks, start=1):
        context_parts.append(
            f"""
[BẰNG CHỨNG {index}]
Tài liệu: {chunk.get('ten_tai_lieu')}
Phiên bản: {chunk.get('so_phien_ban')}
Điều khoản: {chunk.get('dieu_khoan')}
Trang: {chunk.get('so_trang')}

Nội dung:
{chunk.get('noi_dung')}
"""
        )

    context = "\n".join(context_parts)

    prompt = f"""
Bạn là trợ lý hỏi đáp quy chế về nhà ở và đất đai.

NGUYÊN TẮC BẮT BUỘC:
1. Chỉ sử dụng thông tin trong phần BẰNG CHỨNG.
2. Không tự suy diễn hoặc bổ sung kiến thức bên ngoài.
3. Không tự tạo số điều, khoản, văn bản hoặc thời hạn pháp lý.
4. Nếu bằng chứng không đủ để kết luận, phải nói rõ giới hạn.
5. Trả lời bằng tiếng Việt, rõ ràng và trực tiếp.
6. Không tự tạo danh sách nguồn trích dẫn. Hệ thống sẽ cung cấp
   trích dẫn dựa trên các đoạn văn bản đã truy xuất.

BẰNG CHỨNG:
{context}

CÂU HỎI:
{question}

CÂU TRẢ LỜI:
"""

    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": settings.OLLAMA_LLM_MODEL,
        "prompt": prompt,
        "stream": False
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

        data = response.json()

    answer = data.get("response", "").strip()

    if not answer:
        raise ValueError("Ollama không trả về nội dung câu trả lời.")

    return answer


def build_citations(chunks: list) -> list:
    """
    Chuyển các đoạn bằng chứng thành danh sách trích dẫn.
    """

    citations = []

    for chunk in chunks:
        metadata = chunk.get("metadata") or {}

        source_url = get_metadata_value(
            metadata,
            "source_url",
            "sourceUrl",
            "url",
            "SourceUrl"
        )

        citations.append({
            "ma_doan": chunk.get("ma_doan"),
            "ten_tai_lieu": chunk.get("ten_tai_lieu"),
            "ma_phien_ban": chunk.get("ma_phien_ban"),
            "so_phien_ban": chunk.get("so_phien_ban"),
            "dieu_khoan": chunk.get("dieu_khoan"),
            "so_trang": chunk.get("so_trang"),
            "noi_dung_trich": chunk.get("noi_dung"),
            "source_url": source_url,
            "do_tuong_dong": round(
                float(chunk.get("score", 0.0)), 4
            )
        })

    return citations


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def save_chat_result(
    request: ChatRequest,
    ma_cau_hoi: str,
    ma_cau_tra_loi: str,
    trace_id: str,
    answer: str,
    status: str,
    confidence: float,
    refusal_reason: Optional[str],
    chunks: list
):
    """
    Lưu câu hỏi, câu trả lời, trích dẫn và lịch sử truy xuất.

    Sử dụng trực tiếp các bảng:
    - PHIEN_HOI_DAP
    - CAU_HOI
    - CAU_TRA_LOI
    - TRICH_DAN
    - CHI_TIET_TRUY_XUAT
    """

    conn = None

    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()

        # 1. Kiểm tra người dùng có tồn tại không.
        cursor.execute(
            """
            SELECT MaND
            FROM NGUOI_DUNG
            WHERE MaND = ?
            """,
            request.ma_nd
        )

        user = cursor.fetchone()

        if not user:
            raise ValueError(
                f"Không tìm thấy người dùng: {request.ma_nd}"
            )

        # 2. Kiểm tra phiên hội thoại.
        cursor.execute(
            """
            SELECT MaND
            FROM PHIEN_HOI_DAP
            WHERE MaPhien = ?
            """,
            request.ma_phien
        )

        session = cursor.fetchone()
        if session and str(session[0]) != request.ma_nd:
            raise HTTPException(
                status_code=403,
                detail="The chat session belongs to another account.",
            )

        # Nếu chưa có phiên thì tạo mới.
        if not session:
            cursor.execute(
                """
                INSERT INTO PHIEN_HOI_DAP (
                    MaPhien,
                    MaND
                )
                VALUES (?, ?)
                """,
                request.ma_phien,
                request.ma_nd
            )

        # 3. Lưu câu hỏi.
        cursor.execute(
            """
            INSERT INTO CAU_HOI (
                MaCauHoi,
                MaPhien,
                NoiDung
            )
            VALUES (?, ?, ?)
            """,
            ma_cau_hoi,
            request.ma_phien,
            request.noi_dung_cau_hoi
        )

        # 4. Lưu câu trả lời.
        cursor.execute(
            """
            INSERT INTO CAU_TRA_LOI (
                MaCauTraLoi,
                MaCauHoi,
                NoiDung,
                TrangThai,
                DoTinCay,
                LyDoTuChoi,
                TraceId
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ma_cau_tra_loi,
            ma_cau_hoi,
            answer,
            status,
            confidence,
            refusal_reason,
            trace_id
        )

        # 5. Lưu chi tiết truy xuất và trích dẫn.
        for index, chunk in enumerate(chunks, start=1):

            ma_doan = chunk.get("ma_doan")

            # Lưu lịch sử truy xuất.
            cursor.execute(
                """
                INSERT INTO CHI_TIET_TRUY_XUAT (
                    MaCauHoi,
                    MaDoan,
                    ThuHang,
                    DiemTuongDong
                )
                VALUES (?, ?, ?, ?)
                """,
                ma_cau_hoi,
                ma_doan,
                index,
                float(chunk.get("score", 0.0))
            )

            # Chỉ lưu trích dẫn cho câu trả lời thành công.
            if status == "ThanhCong":
                cursor.execute(
                    """
                    INSERT INTO TRICH_DAN (
                        MaCauTraLoi,
                        MaDoan,
                        ThuTu,
                        DoanTrich
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    ma_cau_tra_loi,
                    ma_doan,
                    index,
                    chunk.get("noi_dung", "")
                )

        conn.commit()

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if conn:
            conn.close()


# =========================================================
# CHAT API
# =========================================================

@router.post("", response_model=ChatResponse)
async def chat_with_rag(
    request: ChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    if request.ma_nd != current_user.ma_nd:
        raise HTTPException(
            status_code=403,
            detail="The chat user must match the authenticated account.",
        )

    ma_cau_hoi = generate_id("Q")
    ma_cau_tra_loi = generate_id("A")
    trace_id = generate_trace_id()

    audit_rag_step(
        trace_id=trace_id,
        step="CHAT_RECEIVED",
        ma_nd=request.ma_nd,
        ma_phien=request.ma_phien,
        ma_cau_hoi=ma_cau_hoi
    )

    question = request.noi_dung_cau_hoi.strip()

    if not question:
        audit_rag_step(
            trace_id=trace_id,
            step="CHAT_REJECTED",
            details={"reason": "empty_question"},
            ma_nd=request.ma_nd,
            ma_phien=request.ma_phien,
            ma_cau_hoi=ma_cau_hoi
        )
        raise HTTPException(
            status_code=400,
            detail="Nội dung câu hỏi không được để trống."
        )

    # -----------------------------------------------------
    # 1. RETRIEVAL - Truy xuất bằng chứng
    # -----------------------------------------------------

    try:
        retrieval = await retrieve_evidence(question)

    except HTTPException:
        raise

    except Exception as error:
        audit_rag_step(
            trace_id=trace_id,
            step="RETRIEVAL_FAILED",
            details={"error_type": type(error).__name__},
            ma_nd=request.ma_nd,
            ma_phien=request.ma_phien,
            ma_cau_hoi=ma_cau_hoi
        )
        raise HTTPException(
            status_code=503,
            detail=f"Lỗi truy xuất dữ liệu: {str(error)}"
        )

    best_score = float(retrieval.get("best_score", 0.0))
    threshold = float(retrieval.get("threshold", 0.70))

    chunks = retrieval.get("chunks", [])

    audit_rag_step(
        trace_id=trace_id,
        step="VECTOR_SEARCH",
        ma_nd=request.ma_nd,
        ma_phien=request.ma_phien,
        ma_cau_hoi=ma_cau_hoi,
        details={
            "best_score": best_score,
            "threshold": threshold,
            "retrieved_count": len(chunks),
            "qualified": retrieval.get("qualified"),
            "total_active_vectors": retrieval.get(
                "total_active_vectors", 0
            )
        }
    )

    # -----------------------------------------------------
    # 2. EVIDENCE GATE - Kiểm tra bằng chứng
    # -----------------------------------------------------
    audit_rag_step(
        trace_id=trace_id,
        step="EVIDENCE_GATE",
        ma_nd=request.ma_nd,
        ma_phien=request.ma_phien,
        ma_cau_hoi=ma_cau_hoi,
        details={
            "confidence": best_score,
            "threshold": threshold,
            "passed": bool(
                retrieval.get("qualified") and chunks
            )
        }
    )

    evidence_gate_passed = (
        retrieval.get("qualified") is True
        and bool(chunks)
        and math.isfinite(best_score)
        and math.isfinite(threshold)
        and best_score >= threshold
    )
    if not evidence_gate_passed:

        refusal_reason = (
            "Không tìm thấy bằng chứng từ tài liệu đã được "
            f"phê duyệt đạt ngưỡng {threshold:.2f}. "
            f"Số vector đang hoạt động: "
            f"{retrieval.get('total_active_vectors', 0)}."
        )

        try:
            save_chat_result(
                request=request,
                ma_cau_hoi=ma_cau_hoi,
                ma_cau_tra_loi=ma_cau_tra_loi,
                trace_id=trace_id,
                answer=REFUSAL_MESSAGE,
                status="TuChoi",
                confidence=best_score,
                refusal_reason=refusal_reason,
                chunks=[]
            )

        except HTTPException:
            raise

        except Exception as error:
            audit_rag_step(
                trace_id=trace_id,
                step="PERSISTENCE_FAILED",
                details={
                    "result_status": "TuChoi",
                    "error_type": type(error).__name__
                },
                ma_nd=request.ma_nd,
                ma_phien=request.ma_phien,
                ma_cau_hoi=ma_cau_hoi
            )
            raise HTTPException(
                status_code=500,
                detail=f"Không thể lưu kết quả từ chối: {str(error)}"
            )

        audit_chat_result(
            trace_id=trace_id,
            ma_nd=request.ma_nd,
            ma_phien=request.ma_phien,
            ma_cau_hoi=ma_cau_hoi,
            status="TuChoi",
            confidence=best_score,
            reason=refusal_reason,
            citation_count=0
        )

        return ChatResponse(
            ma_cau_tra_loi=ma_cau_tra_loi,
            trace_id=trace_id,
            trang_thai="TuChoi",
            do_tin_cay=round(best_score, 4),
            noi_dung_tra_loi=REFUSAL_MESSAGE,
            ly_do_tu_choi=refusal_reason,
            trich_dan=[]
        )

    # -----------------------------------------------------
    # 3. GENERATION - Sinh câu trả lời
    # -----------------------------------------------------

    try:
        answer = await generate_answer(
            question=question,
            evidence_chunks=chunks
        )

        audit_rag_step(
            trace_id=trace_id,
            step="GENERATION_COMPLETED",
            ma_nd=request.ma_nd,
            ma_phien=request.ma_phien,
            ma_cau_hoi=ma_cau_hoi,
            details={
                "answer_length": len(answer)
            }
        )

    except Exception as error:
        audit_rag_step(
            trace_id=trace_id,
            step="GENERATION_FAILED",
            details={"error_type": type(error).__name__},
            ma_nd=request.ma_nd,
            ma_phien=request.ma_phien,
            ma_cau_hoi=ma_cau_hoi
        )
        raise HTTPException(
            status_code=503,
            detail=f"Lỗi sinh câu trả lời từ Ollama: {str(error)}"
        )

    # -----------------------------------------------------
    # 4. CITATION - Xây dựng trích dẫn
    # -----------------------------------------------------

    citations = build_citations(chunks)

    audit_rag_step(
        trace_id=trace_id,
        step="CITATION_BUILT",
        ma_nd=request.ma_nd,
        ma_phien=request.ma_phien,
        ma_cau_hoi=ma_cau_hoi,
        details={
            "citation_count": len(citations)
        }
    )
    # -----------------------------------------------------
    # 5. PERSISTENCE - Lưu kết quả
    # -----------------------------------------------------

    try:
        save_chat_result(
            request=request,
            ma_cau_hoi=ma_cau_hoi,
            ma_cau_tra_loi=ma_cau_tra_loi,
            trace_id=trace_id,
            answer=answer,
            status="ThanhCong",
            confidence=best_score,
            refusal_reason=None,
            chunks=chunks
        )

    except HTTPException:
        raise

    except Exception as error:
        audit_rag_step(
            trace_id=trace_id,
            step="PERSISTENCE_FAILED",
            details={
                "result_status": "ThanhCong",
                "error_type": type(error).__name__
            },
            ma_nd=request.ma_nd,
            ma_phien=request.ma_phien,
            ma_cau_hoi=ma_cau_hoi
        )
        raise HTTPException(
            status_code=500,
            detail=f"Không thể lưu câu trả lời: {str(error)}"
        )

    # -----------------------------------------------------
    # 6. RESPONSE
    # -----------------------------------------------------
    audit_chat_result(
        trace_id=trace_id,
        ma_nd=request.ma_nd,
        ma_phien=request.ma_phien,
        ma_cau_hoi=ma_cau_hoi,
        status="ThanhCong",
        confidence=best_score,
        citation_count=len(citations)
    )

    return ChatResponse(
        ma_cau_tra_loi=ma_cau_tra_loi,
        trace_id=trace_id,
        trang_thai="ThanhCong",
        do_tin_cay=round(best_score, 4),
        noi_dung_tra_loi=answer,
        ly_do_tu_choi=None,
        trich_dan=citations
    )