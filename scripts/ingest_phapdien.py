import asyncio
import hashlib
import json
import os
import struct
from pathlib import Path

import httpx
import pyodbc


# ============================================================
# 1. CẤU HÌNH
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / "backend" / ".env"
DATA_FILE = ROOT_DIR / "data_phapdien" / "phapdien_housing_land.json"

VERSION_ID = "PB_PHAPDIEN_2026"
DOCUMENT_ID = "PD_PHAPDIEN"
TOPIC = "Xây dựng, nhà ở, đô thị"

OLLAMA_URL = "http://127.0.0.1:11434"
EMBED_MODEL = "nomic-embed-text"


def load_env(path: Path) -> dict:
    """Đọc file .env mà không cần phụ thuộc python-dotenv."""
    config = {}

    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file cấu hình: {path}")

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        config[key.strip()] = value.strip().strip("\"'")

    return config


CONFIG = load_env(ENV_FILE)


def _escape_odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"



def get_connection():
    server = CONFIG.get(
        "DB_SERVER", r"localhost\SQLEXPRESS"
    ).strip().replace("\\\\", "\\")

    driver = CONFIG.get(
        "DB_DRIVER", "ODBC Driver 17 for SQL Server"
    ).strip()

    database = CONFIG.get(
        "DB_BUSINESS", "Db_QuyChe_Business"
    ).strip()

    encrypt = CONFIG.get("DB_ENCRYPT", "yes").strip()
    trust_cert = CONFIG.get(
        "DB_TRUST_SERVER_CERTIFICATE", "yes"
    ).strip()

    windows_auth = (
        CONFIG.get("DB_WINDOWS_AUTH", "true")
        .strip()
        .lower() == "true"
    )

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        f"Encrypt={encrypt}",
        f"TrustServerCertificate={trust_cert}",
    ]

    if windows_auth:
        parts.append("Trusted_Connection=yes")
    else:
        db_user = CONFIG.get("DB_USER")
        db_password = CONFIG.get("DB_PASSWORD")
        if not db_user or not db_password:
            raise ValueError(
                "DB_USER and DB_PASSWORD are required when "
                "DB_WINDOWS_AUTH is false."
            )
        parts.extend([
            f"UID={_escape_odbc_value(db_user)}",
            f"PWD={_escape_odbc_value(db_password)}",
        ])

    connection_string = ";".join(parts) + ";"

    print(f"SQL Server: {server}")
    print(f"Database: {database}")
    print(f"Driver: {driver}")

    return pyodbc.connect(connection_string, timeout=15)



# ============================================================
# 2. TẠO EMBEDDING
# ============================================================

async def generate_embedding(client: httpx.AsyncClient, text: str) -> bytes:
    response = await client.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={
            "model": EMBED_MODEL,
            "prompt": text,
        },
    )
    response.raise_for_status()

    vector = response.json().get("embedding")

    if not vector:
        raise ValueError("Ollama không trả về embedding.")

    if len(vector) != 768:
        raise ValueError(
            f"Vector có {len(vector)} chiều, yêu cầu 768 chiều."
        )

    return struct.pack("<" + "f" * len(vector), *vector)


# ============================================================
# 3. TẠO TÀI LIỆU VÀ PHIÊN BẢN NẾU CHƯA CÓ
# ============================================================

def ensure_document_and_version(cursor):
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM dbo.TAI_LIEU
            WHERE MaTaiLieu = ?
        )
        BEGIN
            INSERT INTO dbo.TAI_LIEU
                (MaTaiLieu, TieuDe, LoaiVanBan, LinhVuc, CoQuanBanHanh)
            VALUES (?, ?, ?, ?, ?)
        END
        """,
        DOCUMENT_ID,
        DOCUMENT_ID,
        "Bộ Pháp điển - Xây dựng, nhà ở, đô thị",
        "HTML",
        TOPIC,
        "Bộ Tư pháp - Bộ Pháp điển",
    )

    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM dbo.PHIEN_BAN_TAI_LIEU
            WHERE MaPhienBan = ?
        )
        BEGIN
            INSERT INTO dbo.PHIEN_BAN_TAI_LIEU
                (
                    MaPhienBan, MaTaiLieu, MaND, SoPhienBan,
                    NgayHieuLuc, TrangThai, DuongDanFile, is_active
                )
            VALUES (?, ?, NULL, ?, NULL, N'Draft', ?, 0)
        END
        """,
        VERSION_ID,
        VERSION_ID,
        DOCUMENT_ID,
        "2026",
        str(DATA_FILE),
    )

    cursor.execute(
        """
        SELECT MaTaiLieu
        FROM dbo.PHIEN_BAN_TAI_LIEU
        WHERE MaPhienBan = ?
        """,
        VERSION_ID,
    )
    row = cursor.fetchone()

    if not row or row[0] != DOCUMENT_ID:
        raise RuntimeError(
            f"Phiên bản {VERSION_ID} không liên kết đúng tài liệu "
            f"{DOCUMENT_ID}. Hãy kiểm tra dữ liệu hiện có."
        )


# ============================================================
# 4. NẠP CÁC ĐOẠN VĂN BẢN VÀ VECTOR
# ============================================================

async def ingest():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu: {DATA_FILE}")

    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    records = [
        record for record in records
        if record.get("topic_title_vi") == TOPIC
        and record.get("article_id")
        and record.get("content_text", "").strip()
    ]

    print(f"Số bản ghi hợp lệ: {len(records)}")

    connection = get_connection()
    cursor = connection.cursor()

    inserted = 0
    skipped = 0
    failed = 0

    try:
        ensure_document_and_version(cursor)
        connection.commit()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120.0)
        ) as client:

            for index, record in enumerate(records, start=1):
                article_id = record["article_id"]
                content = record["content_text"].strip()

                # ID ổn định, tối đa 20 ký tự.
                identity = f"{VERSION_ID}|{article_id}"
                chunk_id = "PD" + hashlib.sha256(
                    identity.encode("utf-8")
                ).hexdigest()[:18]

                cursor.execute(
                    """
                    SELECT 1
                    FROM dbo.DOAN_VAN_BAN
                    WHERE MaDoan = ?
                    """,
                    chunk_id,
                )

                if cursor.fetchone():
                    skipped += 1
                    print(f"[{index}/{len(records)}] Bỏ qua: {article_id}")
                    continue

                try:
                    embedding_bytes = await generate_embedding(
                        client, content
                    )

                    metadata = {
                        "record_id": record.get("record_id"),
                        "article_id": article_id,
                        "article_title": record.get("article_title"),
                        "chapter_title": record.get("chapter_title"),
                        "topic_title_vi": record.get("topic_title_vi"),
                        "subject_title_vi": record.get("subject_title_vi"),
                        "source_note_text": record.get("source_note_text"),
                        "source_links": record.get("source_links", []),
                        "source_url": record.get("source_url"),
                        "scraped_at": record.get("scraped_at"),
                    }

                    cursor.execute(
                        """
                        EXEC dbo.sp_InsertChunkAndVector
                            @MaDoan = ?,
                            @MaPhienBan = ?,
                            @ThuTu = ?,
                            @DieuKhoan = ?,
                            @NoiDung = ?,
                            @SoTrang = ?,
                            @VectorData = ?,
                            @IndexMetadata = ?
                        """,
                        chunk_id,
                        VERSION_ID,
                        index,
                        article_id[:100],
                        content,
                        None,
                        pyodbc.Binary(embedding_bytes),
                        json.dumps(metadata, ensure_ascii=False),
                    )

                    connection.commit()
                    inserted += 1

                    print(
                        f"[{index}/{len(records)}] Đã nạp: "
                        f"{article_id}"
                    )

                except Exception as error:
                    connection.rollback()
                    failed += 1
                    print(f"[{index}/{len(records)}] LỖI {article_id}: {error}")

    finally:
        cursor.close()
        connection.close()

    print("\n========== KẾT QUẢ ==========")
    print(f"Tổng bản ghi hợp lệ : {len(records)}")
    print(f"Đã nạp mới          : {inserted}")
    print(f"Đã bỏ qua           : {skipped}")
    print(f"Thất bại             : {failed}")

    if failed:
        print("Có bản ghi lỗi. Kiểm tra thông báo bên trên trước khi chạy lại.")


if __name__ == "__main__":
    asyncio.run(ingest())
