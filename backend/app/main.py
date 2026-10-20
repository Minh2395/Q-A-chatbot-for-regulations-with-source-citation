
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Housing and Land Regulations Q&A API",
    description="API trợ lý hỏi đáp quy chế nhà ở và đất đai có trích dẫn nguồn.",
    version="0.1.0",
)

# Cho phép frontend chạy ở máy phát triển truy cập backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Housing and Land Regulations Q&A API",
        "status": "running",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "backend",
    }
