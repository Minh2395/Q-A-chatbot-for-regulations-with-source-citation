import asyncio
from pathlib import Path

import httpx


# Xác định thư mục gốc của project, không phụ thuộc thư mục chạy lệnh.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Thư mục chứa HTML Bộ Pháp điển.
PHAPDIEN_DIR = PROJECT_ROOT / "data_phapdien" / "demuc"

# API upload của FastAPI.
API_UPLOAD_URL = "http://127.0.0.1:8000/api/v1/documents/upload"

# Cấu hình nạp dữ liệu.
SO_PHIEN_BAN = "Bộ Pháp Điển 2026"
MA_ND = "ADMIN_PHAPDIEN"
TIMEOUT_SECONDS = 300.0


async def batch_ingest_phapdien():
    """Quét và nạp tuần tự các file HTML qua API FastAPI."""

    if not PHAPDIEN_DIR.exists():
        print(f"❌ Không tìm thấy thư mục: {PHAPDIEN_DIR}")
        return

    # Tìm HTML/HTM trong cả các thư mục con.
    html_files = sorted(
        path
        for path in PHAPDIEN_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".htm"}
    )

    if not html_files:
        print(f"❌ Không tìm thấy file HTML trong: {PHAPDIEN_DIR}")
        return

    print(f"📂 Thư mục dữ liệu: {PHAPDIEN_DIR}")
    print(f"🚀 Tổng số file cần nạp: {len(html_files)}")
    print("-" * 60)

    success_count = 0
    failed_count = 0

    timeout = httpx.Timeout(TIMEOUT_SECONDS)

    async with httpx.AsyncClient(timeout=timeout) as client:
        for idx, file_path in enumerate(html_files, start=1):
            filename = file_path.name

            # Mã tài liệu phải khớp với dữ liệu đã tạo trong TAI_LIEU.
            ma_tai_lieu = f"PD_{idx:04d}"

            print(f"[{idx}/{len(html_files)}] 📄 {filename}")

            try:
                with file_path.open("rb") as file:
                    files = {
                        "file": (filename, file, "text/html")
                    }

                    data = {
                        "ma_tai_lieu": ma_tai_lieu,
                        "so_phien_ban": SO_PHIEN_BAN,
                        "ma_nd": MA_ND,
                    }

                    response = await client.post(
                        API_UPLOAD_URL,
                        files=files,
                        data=data,
                    )

                if response.status_code == 201:
                    result = response.json()
                    success_count += 1

                    print("   ✅ Nạp thành công")
                    print(
                        f"   Mã tài liệu: {ma_tai_lieu}"
                    )
                    print(
                        f"   Mã phiên bản: "
                        f"{result.get('ma_phien_ban', 'N/A')}"
                    )
                    print(
                        f"   Số đoạn: {result.get('so_doan', 'N/A')}"
                    )

                else:
                    failed_count += 1
                    print(
                        f"   ❌ HTTP {response.status_code}: "
                        f"{response.text[:1000]}"
                    )

            except httpx.RequestError as exc:
                failed_count += 1
                print(f"   ❌ Lỗi kết nối API: {exc}")

            except (OSError, ValueError) as exc:
                failed_count += 1
                print(f"   ❌ Lỗi đọc file hoặc phản hồi: {exc}")

            print()

    print("=" * 60)
    print("📊 KẾT QUẢ NẠP DỮ LIỆU")
    print(f"   Tổng số file: {len(html_files)}")
    print(f"   Thành công:   {success_count}")
    print(f"   Thất bại:     {failed_count}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(batch_ingest_phapdien())
