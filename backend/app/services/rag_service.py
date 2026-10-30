import json
import struct
from typing import Any

from app.core.database import get_business_db_connection
from app.services.embedding import generate_vector_embedding


EVIDENCE_THRESHOLD = 0.70
TOP_K = 5


def calculate_cosine_similarity(vec_a: bytes, vec_b: bytes) -> float:
    if not vec_a or not vec_b:
        return 0.0

    if len(vec_a) != len(vec_b) or len(vec_a) % 4 != 0:
        return 0.0

    count = len(vec_a) // 4

    floats_a = struct.unpack("<" + "f" * count, vec_a)
    floats_b = struct.unpack("<" + "f" * count, vec_b)

    dot = sum(a * b for a, b in zip(floats_a, floats_b))
    norm_a = sum(a * a for a in floats_a) ** 0.5
    norm_b = sum(b * b for b in floats_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def parse_metadata(raw_metadata: Any) -> dict:
    if not raw_metadata:
        return {}

    try:
        if isinstance(raw_metadata, dict):
            return raw_metadata

        return json.loads(raw_metadata)
    except (ValueError, TypeError):
        return {}


async def retrieve_evidence(question: str) -> dict:
    """
    Truy xuất bằng chứng từ các tài liệu đã được phê duyệt.

    Lọc tài liệu trước khi xếp hạng vector để tránh tài liệu
    Draft hoặc không còn hiệu lực chiếm vị trí Top K.
    """

    query_vector = await generate_vector_embedding(question)

    conn = None

    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()

        # Chỉ lấy vector thuộc các phiên bản Approved,
        # is_active = 1 thông qua view v_ActiveDoanVanBan.
        cursor.execute(
            """
            SELECT
                v.MaDoan,
                v.VectorData,
                v.IndexMetadata,
                a.NoiDung,
                a.DieuKhoan,
                a.SoTrang,
                a.MaPhienBan,
                a.SoPhienBan,
                a.TenTaiLieu,
                a.LinhVuc
            FROM Db_QuyChe_Vector.dbo.BANG_VECTOR_EMBEDDING v
            INNER JOIN dbo.v_ActiveDoanVanBan a
                ON a.MaDoan = v.MaDoan
            WHERE v.VectorData IS NOT NULL
            """
        )

        rows = cursor.fetchall()

        scored_chunks = []

        for row in rows:
            (
                ma_doan,
                vector_data,
                metadata_raw,
                noi_dung,
                dieu_khoan,
                so_trang,
                ma_phien_ban,
                so_phien_ban,
                ten_tai_lieu,
                linh_vuc
            ) = row

            if not vector_data:
                continue

            score = calculate_cosine_similarity(
                query_vector,
                bytes(vector_data)
            )

            metadata = parse_metadata(metadata_raw)

            scored_chunks.append({
                "ma_doan": ma_doan,
                "noi_dung": noi_dung,
                "dieu_khoan": dieu_khoan,
                "so_trang": so_trang,
                "ma_phien_ban": ma_phien_ban,
                "so_phien_ban": so_phien_ban,
                "ten_tai_lieu": ten_tai_lieu,
                "linh_vuc": linh_vuc,
                "metadata": metadata,
                "score": score
            })

        scored_chunks.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        top_chunks = scored_chunks[:TOP_K]

        best_score = (
            top_chunks[0]["score"] if top_chunks else 0.0
        )

        # Chỉ trả bằng chứng đạt ngưỡng.
        qualified_chunks = [
            item for item in top_chunks
            if item["score"] >= EVIDENCE_THRESHOLD
        ]

        return {
            "best_score": best_score,
            "qualified": bool(qualified_chunks),
            "chunks": qualified_chunks,
            "total_active_vectors": len(rows),
            "threshold": EVIDENCE_THRESHOLD
        }

    finally:
        if conn:
            conn.close()
