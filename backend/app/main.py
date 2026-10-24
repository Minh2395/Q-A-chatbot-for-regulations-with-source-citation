from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import documents, chat


app = FastAPI(
    title="AIK-01 Legal AI Assistant API",
    version="7.0",
    description="Hệ thống Trợ lý Hỏi đáp Quy chế Đất đai & Nhà ở (RAG On-Premise + Evidence Gate)"
)


# Cấu hình CORS kết nối React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Khai báo Routers
app.include_router(documents.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "AIK-01 Backend Service v7 is running smoothly!"
    }