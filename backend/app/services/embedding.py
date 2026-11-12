import httpx
import struct
from typing import List

from app.core.config import settings


async def generate_vector_embedding(text: str) -> bytes:
    """
    Gửi văn bản thô tới Ollama Local API để lấy mảng Vector Float,
    sau đó đóng gói thành chuỗi nhị phân (bytes) để lưu vào SQL Server (VARBINARY).
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/embeddings"

    payload = {
        "model": settings.OLLAMA_EMBED_MODEL,  # VD: "nomic-embed-text"
        "prompt": text
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    vector_floats: List[float] = data.get("embedding", [])

    # Chuyển đổi mảng List[float] thành bytes (Binary) để lưu vào cột VARBINARY trong SQL Server
    binary_vector = struct.pack(f'{len(vector_floats)}f', *vector_floats)

    return binary_vector