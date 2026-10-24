import uuid
import struct
import httpx

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import (
    get_business_db_connection,
    get_vector_db_connection
)
from app.services.embedding import generate_vector_embedding


router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


# Threshold an toàn cho Cổng Bằng Chứng (0.0 đến 1.0)
EVIDENCE_THRESHOLD = 0.70


class ChatRequest(BaseModel):
    ma_phien: str
    ma_nd: str
    noi_dung_cau_hoi: str


class CitationSchema(BaseModel):
    ten_tai_lieu: str
    dieu_khoan: str
    so_trang: int
    noi_dung_trich: str


class ChatResponse(BaseModel):
    ma_cau_tra_loi: str
    trace_id: str
    trang_thai: str  # "ThanhCong" hoặc "TuChoi"
    do_tin_cay: float
    noi_dung_tra_loi: str
    ly_do_tu_choi: Optional[str] = None
    trich_dan: List[CitationSchema] = []


def calculate_cosine_similarity(vec_a: bytes, vec_b: bytes) -> float:
    """
    Tính độ tương đồng Cosine giữa 2 chuỗi nhị phân Vector
    """
    floats_a = struct.unpack(f'{len(vec_a) // 4}f', vec_a)
    floats_b = struct.unpack(f'{len(vec_b) // 4}f', vec_b)

    dot_product = sum(a * b for a, b in zip(floats_a, floats_b))
    norm_a = sum(a * a for a in floats_a) ** 0.5
    norm_b = sum(b * b for b in floats_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


@router.post("/query", response_model=ChatResponse)
async def process_chat_query(request: ChatRequest):
    trace_id = f"TRC_{uuid.uuid4().hex[:12].upper()}"
    ma_cau_hoi = f"Q_{uuid.uuid4().hex[:8].upper()}"
    ma_cau_tra_loi = f"A_{uuid.uuid4().hex[:8].upper()}"

    # 1. Tạo Vector cho câu hỏi người dùng
    query_vector_bytes = await generate_vector_embedding(
        request.noi_dung_cau_hoi
    )

    # 2. Quét Vector Search trong Db_QuyChe_Vector
    conn_vector = get_vector_db_connection()
    cursor_vector = conn_vector.cursor()

    cursor_vector.execute(
        "SELECT MaDoan, VectorData FROM BANG_VECTOR_EMBEDDING"
    )

    all_vectors = cursor_vector.fetchall()
    conn_vector.close()

    scored_chunks = []

    for ma_doan, vector_data in all_vectors:
        score = calculate_cosine_similarity(
            query_vector_bytes,
            vector_data
        )
        scored_chunks.append((ma_doan, score))

    # Sắp xếp lấy Top 5 đoạn tương đồng nhất
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    top_chunks = scored_chunks[:5]

    conn_biz = get_business_db_connection()
    cursor_biz = conn_biz.cursor()

    try:
        # Ghi nhận bản ghi câu hỏi vào DB Business
        cursor_biz.execute(
            """
            INSERT INTO CAU_HOI (MaCauHoi, MaPhien, NoiDungCauHoi)
            VALUES (?, ?, ?)
            """,
            (
                ma_cau_hoi,
                request.ma_phien,
                request.noi_dung_cau_hoi
            )
        )

        if not top_chunks:
            best_score = 0.0
        else:
            best_score = top_chunks[0][1]

        # 3. KÍCH HOẠT CỔNG BẰNG CHỨNG (EVIDENCE GATE)
        if best_score < EVIDENCE_THRESHOLD:
            # SHIELD: TỪ CHỐI KHI THIẾU BẰNG CHỨNG
            ly_do = (
                f"Điểm tương đồng ({best_score:.2f}) "
                f"dưới ngưỡng an toàn ({EVIDENCE_THRESHOLD})"
            )

            noi_dung_tu_choi = (
                "Chưa đủ dữ liệu quy định trong kho quy chế đền bù "
                "& đất đai để trả lời câu hỏi này. Vui lòng liên hệ "
                "Chuyên viên Pháp chế để được hỗ trợ."
            )

            cursor_biz.execute(
                """
                EXEC sp_SaveChatResponse
                    @MaCauTraLoi = ?,
                    @MaCauHoi = ?,
                    @NoiDung = ?,
                    @TrangThai = 'TuChoi',
                    @DoTinCay = ?,
                    @LyDoTuChoi = ?,
                    @TraceId = ?
                """,
                (
                    ma_cau_tra_loi,
                    ma_cau_hoi,
                    noi_dung_tu_choi,
                    best_score,
                    ly_do,
                    trace_id
                )
            )

            conn_biz.commit()

            return ChatResponse(
                ma_cau_tra_loi=ma_cau_tra_loi,
                trace_id=trace_id,
                trang_thai="TuChoi",
                do_tin_cay=round(best_score, 4),
                noi_dung_tra_loi=noi_dung_tu_choi,
                ly_do_tu_choi=ly_do,
                trich_dan=[]
            )

        # 4. PRE-FILTERING: Lọc các đoạn thuộc văn bản còn hiệu lực (is_active = 1)
        top_ids_str = ",".join([item[0] for item in top_chunks])

        cursor_biz.execute(
            """
            EXEC sp_FilterActiveChunksByVectorIds
                @ListMaDoan = ?
            """,
            (top_ids_str,)
        )

        active_chunks = cursor_biz.fetchall()

        if not active_chunks:
            # Các đoạn tìm thấy đều thuộc văn bản đã hết hiệu lực!
            ly_do = (
                "Các đoạn văn bản liên quan đều đã HẾT HIỆU LỰC thi hành."
            )

            noi_dung_tu_choi = (
                "Quy định liên khoản này đã hết hiệu lực thi hành "
                "theo các quyết định mới nhất."
            )

            cursor_biz.execute(
                """
                EXEC sp_SaveChatResponse
                    @MaCauTraLoi = ?,
                    @MaCauHoi = ?,
                    @NoiDung = ?,
                    @TrangThai = 'TuChoi',
                    @DoTinCay = ?,
                    @LyDoTuChoi = ?,
                    @TraceId = ?
                """,
                (
                    ma_cau_tra_loi,
                    ma_cau_hoi,
                    noi_dung_tu_choi,
                    best_score,
                    ly_do,
                    trace_id
                )
            )

            conn_biz.commit()

            return ChatResponse(
                ma_cau_tra_loi=ma_cau_tra_loi,
                trace_id=trace_id,
                trang_thai="TuChoi",
                do_tin_cay=round(best_score, 4),
                noi_dung_tra_loi=noi_dung_tu_choi,
                ly_do_tu_choi=ly_do,
                trich_dan=[]
            )

        # 5. ĐÓNG GÓI PROMPT & GỌI OLLAMA LLAMA 3.1 8B
        context_str = ""
        trich_dan_list = []

        for idx, row in enumerate(active_chunks, start=1):
            (
                ma_doan,
                noi_dung,
                dieu_khoan,
                so_trang,
                ten_tai_lieu,
                so_phien_ban
            ) = row

            context_str += (
                f"\n--- [Nguồn {idx}: {ten_tai_lieu} ({so_phien_ban}) "
                f"| {dieu_khoan} | Trang {so_trang}] ---\n"
                f"{noi_dung}\n"
            )

            trich_dan_list.append(
                CitationSchema(
                    ten_tai_lieu=ten_tai_lieu,
                    dieu_khoan=dieu_khoan or "N/A",
                    so_trang=so_trang or 1,
                    noi_dung_trich=noi_dung[:150] + "..."
                )
            )

        system_prompt = (
            "Bạn là Trợ lý AI Pháp luật Đất đai & Nhà ở chuyên nghiệp.\n"
            "Chỉ sử dụng ngữ cảnh quy chế dưới đây để trả lời câu hỏi. "
            "Bắt buộc trích dẫn rõ Tên văn bản, Điều khoản và Số trang "
            "khi đưa ra câu trả lời.\n"
            f"NGỮ CẢNH:\n{context_str}"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            ollama_resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_LLM_MODEL,
                    "prompt": (
                        f"{system_prompt}\n\n"
                        f"CÂU HỎI: {request.noi_dung_cau_hoi}\n"
                        "TRẢ LỜI:"
                    ),
                    "stream": False
                }
            )

        llm_answer = ollama_resp.json().get(
            "response",
            "Không thể sinh câu trả lời."
        )

        # 6. LƯU CÂU TRẢ LỜI VÀ TRÍCH DẪN VÀO CSDL
        cursor_biz.execute(
            """
            EXEC sp_SaveChatResponse
                @MaCauTraLoi = ?,
                @MaCauHoi = ?,
                @NoiDung = ?,
                @TrangThai = 'ThanhCong',
                @DoTinCay = ?,
                @LyDoTuChoi = NULL,
                @TraceId = ?
            """,
            (
                ma_cau_tra_loi,
                ma_cau_hoi,
                llm_answer,
                best_score,
                trace_id
            )
        )

        for idx, item in enumerate(active_chunks, start=1):
            ma_doan = item[0]

            cursor_biz.execute(
                """
                INSERT INTO TRICH_DAN
                    (MaCauTraLoi, MaDoan, ThuTu, DoanTrich)
                VALUES (?, ?, ?, ?)
                """,
                (
                    ma_cau_tra_loi,
                    ma_doan,
                    idx,
                    item[1][:500]
                )
            )

        conn_biz.commit()

        return ChatResponse(
            ma_cau_tra_loi=ma_cau_tra_loi,
            trace_id=trace_id,
            trang_thai="ThanhCong",
            do_tin_cay=round(best_score, 4),
            noi_dung_tra_loi=llm_answer,
            trich_dan=trich_dan_list
        )

    except Exception as e:
        conn_biz.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xử lý RAG Chat: {str(e)}"
        )

    finally:
        conn_biz.close()