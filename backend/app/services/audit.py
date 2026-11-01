
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any


BASE_DIR = Path(__file__).resolve().parents[2]

AUDIT_DIR = BASE_DIR / "logs"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_FILE = AUDIT_DIR / "audit.jsonl"

logger = logging.getLogger("AIK01.Audit")


def generate_trace_id() -> str:
    import uuid
    return str(uuid.uuid4())


def write_audit_log(
    event: str,
    trace_id: str,
    ma_nd: Optional[str] = None,
    ma_phien: Optional[str] = None,
    ma_cau_hoi: Optional[str] = None,
    status: Optional[str] = None,
    confidence: Optional[float] = None,
    details: Optional[dict[str, Any]] = None
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "trace_id": trace_id,
        "ma_nd": ma_nd,
        "ma_phien": ma_phien,
        "ma_cau_hoi": ma_cau_hoi,
        "status": status,
        "confidence": confidence,
        "details": details or {}
    }

    try:
        with AUDIT_FILE.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str
                ) + "\n"
            )

        logger.info(
            "AUDIT: %s | %s",
            event,
            trace_id
        )

    except OSError:
        logger.exception("Không thể ghi Audit Log")


def audit_rag_step(
    trace_id: str,
    step: str,
    details: Optional[dict[str, Any]] = None,
    ma_nd: Optional[str] = None,
    ma_phien: Optional[str] = None,
    ma_cau_hoi: Optional[str] = None
):
    write_audit_log(
        event=step,
        trace_id=trace_id,
        ma_nd=ma_nd,
        ma_phien=ma_phien,
        ma_cau_hoi=ma_cau_hoi,
        details=details
    )


def audit_chat_result(
    trace_id: str,
    ma_nd: str,
    ma_phien: str,
    ma_cau_hoi: str,
    status: str,
    confidence: Optional[float] = None,
    reason: Optional[str] = None,
    citation_count: int = 0
):
    write_audit_log(
        event="CHAT_RESULT",
        trace_id=trace_id,
        ma_nd=ma_nd,
        ma_phien=ma_phien,
        ma_cau_hoi=ma_cau_hoi,
        status=status,
        confidence=confidence,
        details={
            "reason": reason,
            "citation_count": citation_count
        }
    )
