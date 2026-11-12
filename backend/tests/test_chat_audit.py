import asyncio
import json

from app.api.v1 import chat
from app.core.security import AuthenticatedUser
from app.services import audit


def read_audit_records(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_chat_success_is_audited_once(monkeypatch, tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE", audit_file)

    async def retrieve_evidence(question):
        assert question == "Question"
        return {
            "best_score": 0.91,
            "threshold": 0.70,
            "qualified": True,
            "chunks": [{
                "ma_doan": "D1",
                "noi_dung": "Evidence",
                "score": 0.91,
                "metadata": {},
            }],
        }

    async def generate_answer(question, evidence_chunks):
        assert question == "Question"
        assert evidence_chunks
        return "Answer"

    monkeypatch.setattr(chat, "retrieve_evidence", retrieve_evidence)
    monkeypatch.setattr(chat, "generate_answer", generate_answer)
    monkeypatch.setattr(chat, "save_chat_result", lambda **kwargs: kwargs)

    response = asyncio.run(chat.chat_with_rag(
        chat.ChatRequest(
            ma_phien="S1",
            ma_nd="U1",
            noi_dung_cau_hoi="Question",
        ),
        AuthenticatedUser(ma_nd="U1", vai_tro="NguoiDung"),
    ))

    records = read_audit_records(audit_file)
    results = [record for record in records if record["event"] == "CHAT_RESULT"]

    assert response.trang_thai == "ThanhCong"
    assert len(results) == 1
    assert results[0]["status"] == "ThanhCong"
    assert results[0]["ma_nd"] == "U1"
    assert results[0]["ma_phien"] == "S1"
    assert results[0]["ma_cau_hoi"]
    assert all(
        record["trace_id"] == response.trace_id
        and record["ma_nd"] == "U1"
        and record["ma_phien"] == "S1"
        and record["ma_cau_hoi"] == results[0]["ma_cau_hoi"]
        for record in records
    )


def test_chat_refusal_is_audited_once(monkeypatch, tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE", audit_file)

    async def retrieve_evidence(question):
        assert question == "Question"
        return {
            "best_score": 0.2,
            "threshold": 0.70,
            "qualified": False,
            "chunks": [],
        }

    monkeypatch.setattr(chat, "retrieve_evidence", retrieve_evidence)
    monkeypatch.setattr(chat, "save_chat_result", lambda **kwargs: kwargs)

    response = asyncio.run(chat.chat_with_rag(
        chat.ChatRequest(
            ma_phien="S2",
            ma_nd="U2",
            noi_dung_cau_hoi="Question",
        ),
        AuthenticatedUser(ma_nd="U2", vai_tro="NguoiDung"),
    ))

    records = read_audit_records(audit_file)
    results = [record for record in records if record["event"] == "CHAT_RESULT"]

    assert response.trang_thai == "TuChoi"
    assert len(results) == 1
    assert results[0]["status"] == "TuChoi"
    assert results[0]["details"]["citation_count"] == 0
    assert results[0]["ma_nd"] == "U2"
    assert results[0]["ma_phien"] == "S2"


def test_chat_refuses_evidence_below_80_percent_without_citations(
    monkeypatch, tmp_path
):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE", audit_file)
    persisted = {}

    async def retrieve_evidence(question):
        return {
            "best_score": 0.79,
            "threshold": 0.70,
            "qualified": True,
            "chunks": [{
                "ma_doan": "D1",
                "noi_dung": "Below-threshold evidence",
                "score": 0.79,
                "metadata": {},
            }],
        }

    async def unexpected_generation(*_args, **_kwargs):
        raise AssertionError("Generation must not run below the evidence threshold.")

    monkeypatch.setattr(chat, "retrieve_evidence", retrieve_evidence)
    monkeypatch.setattr(chat, "generate_answer", unexpected_generation)
    monkeypatch.setattr(
        chat,
        "save_chat_result",
        lambda **kwargs: persisted.update(kwargs),
    )

    response = asyncio.run(chat.chat_with_rag(
        chat.ChatRequest(
            ma_phien="S3",
            ma_nd="U3",
            noi_dung_cau_hoi="Question",
        ),
        AuthenticatedUser(ma_nd="U3", vai_tro="NguoiDung"),
    ))

    records = read_audit_records(audit_file)
    results = [record for record in records if record["event"] == "CHAT_RESULT"]

    assert response.trang_thai == "TuChoi"
    assert response.trich_dan == []
    assert response.do_tin_cay == 0.79
    assert "0.80" in (response.ly_do_tu_choi or "")
    assert persisted["status"] == "TuChoi"
    assert persisted["chunks"] == []
    assert len(results) == 1
    assert results[0]["details"]["citation_count"] == 0


def test_chat_accepts_evidence_at_exact_80_percent(monkeypatch, tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_FILE", audit_file)

    async def retrieve_evidence(_question):
        return {
            "best_score": 0.80,
            "threshold": 0.70,
            "qualified": True,
            "chunks": [{
                "ma_doan": "D1",
                "noi_dung": "Evidence",
                "score": 0.80,
                "metadata": {},
            }],
        }

    async def generate_answer(**_kwargs):
        return "Answer"

    monkeypatch.setattr(chat, "retrieve_evidence", retrieve_evidence)
    monkeypatch.setattr(chat, "generate_answer", generate_answer)
    monkeypatch.setattr(chat, "save_chat_result", lambda **_kwargs: None)

    response = asyncio.run(chat.chat_with_rag(
        chat.ChatRequest(
            ma_phien="S4",
            ma_nd="U4",
            noi_dung_cau_hoi="Question",
        ),
        AuthenticatedUser(ma_nd="U4", vai_tro="NguoiDung"),
    ))

    assert response.trang_thai == "ThanhCong"
    assert response.trich_dan
