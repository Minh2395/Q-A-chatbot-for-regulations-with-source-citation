import re
from io import BytesIO
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document


def extract_chunks_from_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Đọc file PDF, bóc tách văn bản theo từng trang và phát hiện Điều/Khoản.
    """
    reader = PdfReader(BytesIO(file_bytes))
    chunks = []
    chunk_order = 1

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if not text.strip():
            continue

        # Tìm các vị trí ghi "Điều XX" hoặc "Khoản XX" trong trang
        lines = text.split("\n")
        current_dieu_khoan = f"Trang {page_num}"
        current_content = []

        for line in lines:
            line_str = line.strip()

            # Phát hiện định dạng Điều khoản (ví dụ: Điều 12, Điều 5...)
            match = re.match(
                r'^(Điều\s+\d+[\.\:]?.*)',
                line_str,
                re.IGNORECASE
            )

            if match:
                if current_content:
                    chunks.append({
                        "thu_tu": chunk_order,
                        "dieu_khoan": current_dieu_khoan,
                        "noi_dung": "\n".join(current_content),
                        "so_trang": page_num
                    })

                    chunk_order += 1
                    current_content = []

                current_dieu_khoan = match.group(1)[:100]  # Giới hạn độ dài tiêu đề

            current_content.append(line_str)

        if current_content:
            chunks.append({
                "thu_tu": chunk_order,
                "dieu_khoan": current_dieu_khoan,
                "noi_dung": "\n".join(current_content),
                "so_trang": page_num
            })

            chunk_order += 1

    return chunks


def extract_chunks_from_docx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Đọc file Word (.docx), trích xuất các đoạn văn bản và phát hiện Điều/Khoản.
    """
    doc = Document(BytesIO(file_bytes))
    chunks = []
    chunk_order = 1
    current_dieu_khoan = "Mục chung"
    current_content = []

    for para in doc.paragraphs:
        text = para.text.strip()

        if not text:
            continue

        match = re.match(
            r'^(Điều\s+\d+[\.\:]?.*)',
            text,
            re.IGNORECASE
        )

        if match:
            if current_content:
                chunks.append({
                    "thu_tu": chunk_order,
                    "dieu_khoan": current_dieu_khoan,
                    "noi_dung": "\n".join(current_content),
                    "so_trang": 1  # File Word mặc định xem như dòng chảy liên tục
                })

                chunk_order += 1
                current_content = []

            current_dieu_khoan = match.group(1)[:100]

        current_content.append(text)

    if current_content:
        chunks.append({
            "thu_tu": chunk_order,
            "dieu_khoan": current_dieu_khoan,
            "noi_dung": "\n".join(current_content),
            "so_trang": 1
        })

    return chunks

def extract_chunks_from_html(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Đọc file HTML từ Bộ Pháp điển, loại bỏ thẻ không cần thiết
    và bóc tách nội dung theo Điều.

    Lưu ý:
    - Mỗi chunk hiện tương ứng với một Điều.
    - so_trang mặc định là 1 vì HTML không cung cấp thông tin trang
      theo cách mà hàm này đang xử lý.
    """

    soup = BeautifulSoup(file_bytes, "html.parser")

    # Loại bỏ nội dung không phục vụ việc truy xuất văn bản.
    for element in soup(["script", "style", "header", "footer", "nav"]):
        element.decompose()

    text = soup.get_text(separator="\n")

    # Chuẩn hóa khoảng trắng và loại bỏ dòng rỗng.
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]

    chunks: List[Dict[str, Any]] = []
    chunk_order = 1

    current_dieu_khoan = "Mục chung Bộ Pháp điển"
    current_content: List[str] = []

    # Nhận diện tiêu đề Điều, ví dụ:
    # Điều 1. Phạm vi điều chỉnh
    # Điều 2: Đối tượng áp dụng
    # Điều 3
    dieu_pattern = re.compile(
        r"^Điều\s+\d+\b(?:\s*[\.:]\s*.*|\s+.*)?$",
        re.IGNORECASE,
    )

    def save_chunk() -> None:
        nonlocal chunk_order

        content = "\n".join(current_content).strip()

        if not content:
            return

        chunks.append(
            {
                "thu_tu": chunk_order,
                "dieu_khoan": current_dieu_khoan[:100],
                "noi_dung": content,
                "so_trang": 1,
            }
        )
        chunk_order += 1

    for line in lines:
        if dieu_pattern.match(line):
            save_chunk()
            current_content.clear()
            current_dieu_khoan = line[:100]

        current_content.append(line)

    save_chunk()

    return chunks