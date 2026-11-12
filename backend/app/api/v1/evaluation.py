import json
import logging
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.v1 import chat
from app.core.database import get_business_db_connection
from app.services.audit import generate_trace_id, write_audit_log
from app.services.rag_service import retrieve_evidence
from app.core.security import AuthenticatedUser, require_roles


router = APIRouter(prefix="/evaluation", tags=["Evaluation"])
logger = logging.getLogger("AIK01.Evaluation")

BACKEND_DIR = Path(__file__).resolve().parents[3]
DATASET_FILE = BACKEND_DIR / "data" / "evaluation_dataset_preliminary_matched.json"
REPORT_DIR = BACKEND_DIR / "reports"
MINIMUM_QUESTION_COUNT = 50
VALID_STATUSES = {"ThanhCong", "TuChoi"}
VERIFIED_REVIEW_STATUSES = {"VERIFIED", "APPROVED"}

_claim_lock = threading.Lock()
_claimed_document_versions: set[str] = set()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dataset(dataset_path: Path = DATASET_FILE) -> list[dict[str, Any]]:
    """Load and structurally validate the JSON benchmark."""
    try:
        with dataset_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as error:
        raise ValueError(f"Evaluation dataset not found: {dataset_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid evaluation JSON: {error}") from error

    if not isinstance(data, list):
        raise ValueError("Evaluation dataset must be a JSON array.")
    if len(data) < MINIMUM_QUESTION_COUNT:
        raise ValueError(
            f"Evaluation dataset requires at least {MINIMUM_QUESTION_COUNT} "
            f"questions; found {len(data)}."
        )

    seen_ids: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Dataset entry {index + 1} must be an object.")
        question_id = item.get("id")
        question = item.get("question")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Dataset entry {index + 1} has no valid id.")
        if question_id in seen_ids:
            raise ValueError(f"Duplicate evaluation question id: {question_id}")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Question {question_id} has no valid question text.")
        seen_ids.add(question_id)

    return data


def _pending_reason(question: dict[str, Any]) -> str | None:
    review_status = str(question.get("review_status", "")).strip().upper()
    problems = []
    if review_status not in VERIFIED_REVIEW_STATUSES:
        problems.append("Question has not completed legal-officer review.")

    required_values = {
        "expected_status": question.get("expected_status"),
        "reviewed_by": question.get("reviewed_by"),
        "reviewed_at": question.get("reviewed_at"),
    }
    if question.get("expected_status") == "ThanhCong":
        required_values.update({
            "expected_answer": question.get("expected_answer"),
            "expected_ma_doan": question.get("expected_ma_doan"),
            "expected_document_id": question.get("expected_document_id"),
            "expected_version": question.get("expected_version"),
            "expected_article": question.get("expected_article"),
        })
    missing = [
        key for key, value in required_values.items()
        if not isinstance(value, str) or not value.strip()
    ]
    if missing:
        problems.append("Missing verified reference fields: " + ", ".join(missing))
    elif question["expected_status"] not in VALID_STATUSES:
        problems.append("expected_status must be ThanhCong or TuChoi.")
    if question.get("expected_status") == "ThanhCong":
        keywords = question.get("expected_keywords")
        if (
            not isinstance(keywords, list)
            or not keywords
            or any(
                not isinstance(keyword, str) or not keyword.strip()
                for keyword in keywords
            )
        ):
            problems.append("Expected legal keywords are missing or invalid.")

    return "; ".join(problems) if problems else None


def _verify_source_record(
    question: dict[str, Any],
    active_documents: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str | None]:
    """Require the reference chunk/version in the active approved snapshot."""
    if active_documents is not None:
        record = active_documents.get(
            str(question.get("expected_ma_doan") or "")
        )
        if not record:
            return False, "Reference chunk is not in the active approved document repository."
        if record["ma_tai_lieu"] != question["expected_document_id"]:
            return False, "Reference chunk document ID does not match the dataset."
        if record["so_phien_ban"] != question["expected_version"]:
            return False, "Reference chunk version does not match the dataset."
        if question.get("expected_ma_phien_ban") and (
            record["ma_phien_ban"] != question["expected_ma_phien_ban"]
        ):
            return False, "Reference chunk version ID does not match the dataset."
        if record["dieu_khoan"].strip() != question["expected_article"].strip():
            return False, "Reference chunk article/clause does not match the dataset."
        return True, None

    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                d.MaDoan,
                p.MaTaiLieu,
                p.MaPhienBan,
                p.SoPhienBan,
                d.DieuKhoan
            FROM dbo.DOAN_VAN_BAN d
            INNER JOIN dbo.PHIEN_BAN_TAI_LIEU p
                ON p.MaPhienBan = d.MaPhienBan
            WHERE d.MaDoan = ?
              AND p.TrangThai = 'Approved'
              AND p.is_active = 1
              AND p.NgayHieuLuc IS NOT NULL
              AND p.NgayHieuLuc <= GETDATE()
            """,
            question["expected_ma_doan"],
        )
        row = cursor.fetchone()
        if not row:
            return False, "Reference chunk is not in the active approved document repository."

        _, document_id, version_id, version_label, article = row
        if str(document_id) != question["expected_document_id"]:
            return False, "Reference chunk document ID does not match the dataset."
        if str(version_label) != question["expected_version"]:
            return False, "Reference chunk version does not match the dataset."
        if question.get("expected_ma_phien_ban") and (
            str(version_id) != question["expected_ma_phien_ban"]
        ):
            return False, "Reference chunk version ID does not match the dataset."
        if str(article or "").strip() != question["expected_article"].strip():
            return False, "Reference chunk article/clause does not match the dataset."
        return True, None
    except Exception:
        logger.exception("Could not verify benchmark source for %s", question.get("id"))
        return False, "Unable to verify reference against the active SQL Server repository."
    finally:
        if conn:
            conn.close()


def _load_active_document_records() -> list[dict[str, Any]]:
    """Load the current approved evidence corpus for evaluation scoring."""
    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                d.MaDoan,
                p.MaTaiLieu,
                p.MaPhienBan,
                p.SoPhienBan,
                d.DieuKhoan,
                d.NoiDung
            FROM dbo.DOAN_VAN_BAN d
            INNER JOIN dbo.PHIEN_BAN_TAI_LIEU p
                ON p.MaPhienBan = d.MaPhienBan
            WHERE p.is_active = 1
              AND p.TrangThai = 'Approved'
            ORDER BY p.MaTaiLieu, p.MaPhienBan, d.MaDoan
            """
        )
        return [
            {
                "ma_doan": str(row[0]),
                "ma_tai_lieu": str(row[1]),
                "ma_phien_ban": str(row[2]),
                "so_phien_ban": str(row[3]),
                "dieu_khoan": str(row[4] or ""),
                "noi_dung": str(row[5] or ""),
            }
            for row in cursor.fetchall()
        ]
    finally:
        if conn:
            conn.close()


def _normalized_source_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _active_evidence_chunks(
    chunks: list[dict[str, Any]],
    active_documents: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    current_chunks = []
    for chunk in chunks:
        record = active_documents.get(str(chunk.get("ma_doan") or ""))
        if not record:
            continue
        if (
            str(chunk.get("ma_phien_ban") or "") == record["ma_phien_ban"]
            and str(chunk.get("so_phien_ban") or "") == record["so_phien_ban"]
            and _normalized_source_text(chunk.get("dieu_khoan"))
                == _normalized_source_text(record["dieu_khoan"])
            and _normalized_source_text(chunk.get("noi_dung"))
                == _normalized_source_text(record["noi_dung"])
        ):
            current_chunks.append(chunk)
    return current_chunks


def _normalize_tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)


_CLAIM_STOPWORDS = {
    "các", "của", "cho", "đã", "được", "hoặc", "là", "mà", "này", "nếu",
    "những", "ở", "sẽ", "theo", "thì", "trong", "và", "về", "với",
}
_NEGATION_TOKENS = {
    "không", "chưa", "chẳng", "khỏi", "not", "no", "never", "without",
}


def _answer_claims(answer: str) -> list[set[str]]:
    claims = []
    for sentence in re.split(r"[.!?;\n]+", answer):
        tokens = {
            token for token in _normalize_tokens(sentence)
            if len(token) > 1 and token not in _CLAIM_STOPWORDS
        }
        if tokens:
            claims.append(tokens)
    return claims


def _has_unexpected_negation(answer: str, expected_answer: str) -> bool:
    answer_negations = set(_normalize_tokens(answer)) & _NEGATION_TOKENS
    expected_negations = set(_normalize_tokens(expected_answer)) & _NEGATION_TOKENS
    return bool(answer_negations - expected_negations)


def _answer_metrics(
    question: dict[str, Any],
    answer: str,
    status: str,
    citations: list[dict[str, Any]],
    evidence_chunks: list[dict[str, Any]],
    active_documents: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected_status = question["expected_status"]
    status_correct = status == expected_status
    expected_answer = question.get("expected_answer") or ""
    expected_keywords = question.get("expected_keywords") or []

    matched_keywords = [
        keyword for keyword in expected_keywords
        if keyword.casefold() in answer.casefold()
    ]
    keyword_recall = (
        len(matched_keywords) / len(expected_keywords) if expected_keywords else 0.0
    )
    expected_tokens = _normalize_tokens(expected_answer)
    answer_tokens = _normalize_tokens(answer)
    expected_counts: dict[str, int] = {}
    answer_counts: dict[str, int] = {}
    for token in expected_tokens:
        expected_counts[token] = expected_counts.get(token, 0) + 1
    for token in answer_tokens:
        answer_counts[token] = answer_counts.get(token, 0) + 1
    overlap = sum(
        min(count, answer_counts.get(token, 0))
        for token, count in expected_counts.items()
    )
    precision = overlap / len(answer_tokens) if answer_tokens else 0.0
    recall = overlap / len(expected_tokens) if expected_tokens else 0.0
    answer_f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    accuracy = None
    if expected_status == "ThanhCong":
        accuracy = (
            round((keyword_recall + answer_f1) / 2, 4)
            if status_correct
            and not _has_unexpected_negation(answer, expected_answer)
            else 0.0
        )

    claims = (
        _answer_claims(answer)
        if expected_status == "ThanhCong" and status == "ThanhCong"
        else []
    )
    evidence_tokens = {
        token
        for chunk in evidence_chunks
        for token in _normalize_tokens(str(chunk.get("noi_dung", "")))
        if len(token) > 1 and token not in _CLAIM_STOPWORDS
    }
    supported_claims = sum(claim.issubset(evidence_tokens) for claim in claims)

    if active_documents is not None:
        evidence_chunks = _active_evidence_chunks(
            evidence_chunks, active_documents
        )

    chunks_by_id = {
        str(chunk.get("ma_doan")): chunk
        for chunk in evidence_chunks
        if chunk.get("ma_doan") is not None
    }
    expected_chunk_id = str(question.get("expected_ma_doan") or "")
    cited_chunk_ids = [
        str(citation.get("ma_doan"))
        for citation in citations
        if citation.get("ma_doan") is not None
    ]
    citation_results = []
    citations_to_check = citations if expected_status == "ThanhCong" else []
    for citation in citations_to_check:
        chunk_id = str(citation.get("ma_doan") or "")
        chunk = chunks_by_id.get(chunk_id)
        active_record = (
            active_documents.get(chunk_id)
            if active_documents is not None else None
        )
        source_tokens = set(_normalize_tokens(
            str(
                active_record.get("noi_dung", "")
                if active_record is not None
                else chunk.get("noi_dung", "") if chunk else ""
            )
        ))
        source_claim_support = any(
            claim.issubset(source_tokens) for claim in claims
        )
        expected_version_id = question.get("expected_ma_phien_ban")
        version_id_matches = (
            not expected_version_id
            or str(citation.get("ma_phien_ban") or "").strip()
                == str(expected_version_id).strip()
        )
        citation_matches = bool(
            chunk
            and chunk_id == expected_chunk_id
            and version_id_matches
            and str(citation.get("dieu_khoan") or "").strip()
                == str(question.get("expected_article") or "").strip()
            and str(citation.get("so_phien_ban") or "").strip()
                == str(question.get("expected_version") or "").strip()
            and source_claim_support
        )
        if active_documents is not None:
            citation_matches = bool(
                citation_matches
                and active_record
                and active_record["ma_tai_lieu"]
                    == str(question.get("expected_document_id") or "")
                and str(citation.get("ma_phien_ban") or "")
                    == active_record["ma_phien_ban"]
                and str(citation.get("so_phien_ban") or "")
                    == active_record["so_phien_ban"]
                and _normalized_source_text(citation.get("dieu_khoan"))
                    == _normalized_source_text(active_record["dieu_khoan"])
                and _normalized_source_text(citation.get("noi_dung_trich"))
                    == _normalized_source_text(active_record["noi_dung"])
            )
        citation_results.append(citation_matches)

    if expected_status == "ThanhCong" and status == "ThanhCong" and not citations:
        citation_results.append(False)
    citation_correct_count = sum(citation_results)
    citation_checked_count = len(citations_to_check)
    if expected_status == "ThanhCong" and status == "ThanhCong" and not citations:
        citation_checked_count = 1
    return {
        "status_correct": status_correct,
        "keyword_score": round(keyword_recall, 4),
        "answer_similarity": round(answer_f1, 4),
        "accuracy_score": accuracy,
        "faithfulness_score": (
            supported_claims / len(claims) if claims else None
        ),
        "faithfulness_supported_claims": supported_claims,
        "faithfulness_checked_claims": len(claims),
        "citation_correct": bool(citation_results) and all(citation_results),
        "citation_score": (
            citation_correct_count / citation_checked_count
            if citation_checked_count else None
        ),
        "citation_correct_count": citation_correct_count,
        "citation_checked_count": citation_checked_count,
        "correct_refusal": expected_status == "TuChoi" and status_correct,
        "matched_keywords": matched_keywords,
        "missing_keywords": [
            keyword for keyword in expected_keywords
            if keyword not in matched_keywords
        ],
        "expected_chunk_id": expected_chunk_id or None,
        "cited_chunk_ids": cited_chunk_ids,
    }


async def _run_question(
    question: dict[str, Any],
    active_documents: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": question["id"],
        "question": question["question"],
        "status": "Running",
        "generated_answer": None,
        "response_status": None,
        "retrieved_sources": [],
        "scores": None,
        "error": None,
    }
    try:
        retrieval = await retrieve_evidence(question["question"])
        chunks = retrieval.get("chunks") or []
        if not retrieval.get("qualified") or not chunks:
            response_status = "TuChoi"
            answer = chat.REFUSAL_MESSAGE
            citations: list[dict[str, Any]] = []
        else:
            answer = await chat.generate_answer(
                question=question["question"],
                evidence_chunks=chunks,
            )
            response_status = "ThanhCong"
            citations = chat.build_citations(chunks)
        result.update({
            "status": "Completed",
            "retrieval": {
                "qualified": bool(retrieval.get("qualified")),
                "best_score": retrieval.get("best_score", 0.0),
                "threshold": retrieval.get("threshold"),
                "total_active_vectors": retrieval.get("total_active_vectors", 0),
            },
            "response_status": response_status,
            "generated_answer": answer,
            "retrieved_sources": citations,
            "scores": _answer_metrics(
                question,
                answer,
                response_status,
                citations,
                chunks,
                active_documents,
            ),
        })
    except Exception as error:
        logger.exception("Evaluation question %s failed", question["id"])
        result.update({
            "status": "Failed",
            "error": f"{type(error).__name__}: {error}",
        })
    return result


async def _run_preliminary_question(question: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": question["id"],
        "question": question["question"],
        "status": "Running",
        "preliminary_match_status": question.get("preliminary_match_status"),
        "preliminary_note": question.get("preliminary_note"),
        "candidate_sources": question.get("candidate_sources", []),
        "retrieval_diagnostics_not_verified": question.get(
            "retrieval_diagnostics_not_verified", []
        ),
        "retrieval": None,
        "response_status": None,
        "generated_answer": None,
        "retrieved_sources": [],
        "scores": None,
        "error": None,
    }
    try:
        retrieval = await retrieve_evidence(question["question"])
        chunks = retrieval.get("chunks") or []
        if not retrieval.get("qualified") or not chunks:
            answer = chat.REFUSAL_MESSAGE
            response_status = "TuChoi"
            citations: list[dict[str, Any]] = []
        else:
            answer = await chat.generate_answer(
                question=question["question"],
                evidence_chunks=chunks,
            )
            response_status = "ThanhCong"
            citations = chat.build_citations(chunks)
        result.update({
            "status": "Completed",
            "retrieval": {
                "qualified": bool(retrieval.get("qualified")),
                "best_score": retrieval.get("best_score", 0.0),
                "threshold": retrieval.get("threshold"),
                "total_active_vectors": retrieval.get("total_active_vectors", 0),
            },
            "response_status": response_status,
            "generated_answer": answer,
            "retrieved_sources": citations,
        })
    except Exception as error:
        logger.exception("Preliminary evaluation question %s failed", question["id"])
        result.update({
            "status": "Failed",
            "error": f"{type(error).__name__}: {error}",
        })
    return result


def _aggregate_preliminary_metrics(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    completed = [item for item in results if item["status"] == "Completed"]
    qualified = [
        item for item in completed
        if item.get("retrieval", {}).get("qualified")
    ]
    return {
        "questions_attempted": len(results),
        "questions_completed": len(completed),
        "qualified_retrievals": len(qualified),
        "retrieval_coverage": (
            round(len(qualified) / len(completed), 4) if completed else None
        ),
        "generated_answers": sum(
            item.get("response_status") == "ThanhCong" for item in completed
        ),
        "refusals": sum(
            item.get("response_status") == "TuChoi" for item in completed
        ),
        "failed_questions": sum(
            item["status"] == "Failed" for item in results
        ),
    }


def _aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [
        item for item in results
        if item.get("status") == "Completed" and item.get("scores")
    ]
    accuracy_samples = [
        item for item in completed
        if item.get("expected_status") == "ThanhCong"
        and item["scores"].get("accuracy_score") is not None
    ]
    checked_claims = sum(
        item["scores"].get("faithfulness_checked_claims", 0)
        for item in completed
    )
    supported_claims = sum(
        item["scores"].get("faithfulness_supported_claims", 0)
        for item in completed
    )
    checked_citations = sum(
        item["scores"].get("citation_checked_count", 0)
        for item in completed
    )
    correct_citations = sum(
        item["scores"].get("citation_correct_count", 0)
        for item in completed
    )
    refusals = [
        item for item in completed
        if item.get("expected_status") == "TuChoi"
    ]
    return {
        "accuracy": round(
            sum(
                item["scores"]["accuracy_score"]
                for item in accuracy_samples
            ) / len(accuracy_samples),
            4,
        ) if accuracy_samples else None,
        "faithfulness": round(
            supported_claims / checked_claims,
            4,
        ) if checked_claims else None,
        "citation_correctness": round(
            correct_citations / checked_citations,
            4,
        ) if checked_citations else None,
        "correct_refusal_rate": round(
            sum(
                item["scores"].get("correct_refusal", False)
                for item in refusals
            )
            / len(refusals),
            4,
        ) if refusals else None,
        "accuracy_sample_count": len(accuracy_samples),
        "faithfulness_sample_count": checked_claims,
        "citation_sample_count": checked_citations,
        "correct_refusal_sample_count": len(refusals),
        "scored_questions": len(accuracy_samples),
        "failed_questions": sum(
            item.get("status") == "Failed" for item in results
        ),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "accuracy": None,
        "faithfulness": None,
        "citation_correctness": None,
        "correct_refusal_rate": None,
        "accuracy_sample_count": 0,
        "faithfulness_sample_count": 0,
        "citation_sample_count": 0,
        "correct_refusal_sample_count": 0,
        "scored_questions": 0,
        "failed_questions": 0,
    }


def _persist_existing_evaluation_result(report: dict[str, Any]) -> dict[str, Any]:
    """Persist only when existing SQL benchmark rows already satisfy all FKs."""
    results = [
        item for item in report["question_results"]
        if item.get("reviewed_by") and item.get("reviewed_at")
    ]
    question_ids = [item["id"] for item in results]
    if not question_ids:
        return {"status": "skipped", "reason": "No evaluation results to persist."}

    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        placeholders = ", ".join("?" for _ in question_ids)
        cursor.execute(
            f"""
            SELECT MaCauHoiDG, MaBo, MaDoanChuan, DapAnChuan, LoaiCau
            FROM dbo.CAU_HOI_DANH_GIA
            WHERE MaCauHoiDG IN ({placeholders})
            """,
            *question_ids,
        )
        stored_questions = {
            str(row[0]): {
                "dataset_id": str(row[1]),
                "source_chunk_id": str(row[2]) if row[2] is not None else None,
                "expected_answer": str(row[3]) if row[3] is not None else None,
                "question_type": str(row[4]) if row[4] is not None else None,
            }
            for row in cursor.fetchall()
        }
        if set(stored_questions) != set(question_ids):
            return {
                "status": "skipped",
                "reason": (
                    "JSON benchmark IDs are not all present in "
                    "CAU_HOI_DANH_GIA; no benchmark records were inserted."
                ),
            }
        for item in results:
            stored = stored_questions[item["id"]]
            if (
                stored["source_chunk_id"] != item.get("expected_ma_doan")
                or stored["expected_answer"] != item.get("expected_answer")
                or stored["question_type"] != item.get("question_type")
            ):
                return {
                    "status": "skipped",
                    "reason": (
                        f"Existing SQL benchmark row {item['id']} does not "
                        "match the verified JSON reference."
                    ),
                }

        dataset_ids = {
            item["dataset_id"] for item in stored_questions.values()
        }
        if len(dataset_ids) != 1:
            return {
                "status": "skipped",
                "reason": "Questions belong to multiple existing evaluation sets.",
            }

        result_id = "KQ" + uuid.uuid4().hex[:18].upper()
        metrics = report["metrics"]
        cursor.execute(
            """
            INSERT INTO dbo.KET_QUA_DANH_GIA
                (MaKQ, MaBo, TyLeDung, TyLeTuChoiDung, TyLeTrichDanDung)
            VALUES (?, ?, ?, ?, ?)
            """,
            result_id,
            dataset_ids.pop(),
            metrics["accuracy"],
            metrics["correct_refusal_rate"],
            metrics["citation_correctness"],
        )
        for item in results:
            scores = item.get("scores") or {}
            cursor.execute(
                """
                INSERT INTO dbo.CHI_TIET_KET_QUA
                    (MaKQ, MaCauHoiDG, KetQuaDung, TrichDanDung)
                VALUES (?, ?, ?, ?)
                """,
                result_id,
                item["id"],
                int(scores.get("status_correct", False)
                    and scores.get("accuracy_score") == 1.0),
                int(scores.get("citation_correct", False)),
            )
        conn.commit()
        return {"status": "persisted", "ma_ket_qua": result_id}
    except Exception as error:
        if conn:
            conn.rollback()
        logger.exception("Could not persist evaluation result to SQL Server.")
        return {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
    finally:
        if conn:
            conn.close()


def _write_report(report: dict[str, Any], document_version_id: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", document_version_id)
    for destination in (
        REPORT_DIR / f"evaluation_{safe_id}.json",
        REPORT_DIR / "evaluation_latest.json",
    ):
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=REPORT_DIR, delete=False
            ) as file:
                json.dump(report, file, ensure_ascii=False, indent=2)
                file.write("\n")
                temporary_path = file.name
            os.replace(temporary_path, destination)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)


async def run_evaluation_for_document(
    document_version_id: str,
    preliminary: bool = False,
) -> None:
    """Run after approval; unverified benchmarks produce a Pending report."""
    with _claim_lock:
        if document_version_id in _claimed_document_versions:
            logger.info("Skipping duplicate evaluation for %s", document_version_id)
            return
        _claimed_document_versions.add(document_version_id)

    trace_id = generate_trace_id()
    report: dict[str, Any] = {
        "evaluation_id": "EV" + uuid.uuid4().hex[:18].upper(),
        "document_version_id": document_version_id,
        "started_at": _utc_now(),
        "completed_at": None,
        "status": "Running",
        "official": False,
        "dataset_path": str(DATASET_FILE),
        "dataset_question_count": 0,
        "active_document_count": 0,
        "verified_question_count": 0,
        "pending_verification_questions": [],
        "failed_questions": [],
        "question_results": [],
        "metrics": _empty_metrics(),
        "preliminary_metrics": None,
        "database_persistence": {"status": "not_attempted"},
        "errors": [],
    }
    write_audit_log(
        event="MODEL_EVALUATION_STARTED",
        trace_id=trace_id,
        ma_phien=document_version_id,
    )
    try:
        _write_report(report, document_version_id)
        dataset = load_dataset()
        report["dataset_question_count"] = len(dataset)
        active_records = _load_active_document_records()
        if not active_records:
            report["status"] = "NoActiveDocuments"
            report["errors"].append(
                "No approved active documents are available; evaluation was not run."
            )
            write_audit_log(
                event="MODEL_EVALUATION_BLOCKED_NO_ACTIVE_DOCUMENTS",
                trace_id=trace_id,
                ma_phien=document_version_id,
                status="NoActiveDocuments",
            )
            return

        active_documents = {
            record["ma_doan"]: record for record in active_records
        }
        if len(active_documents) != len(active_records):
            raise ValueError(
                "The active document repository contains duplicate segment IDs."
            )
        report["active_document_count"] = len({
            (record["ma_tai_lieu"], record["ma_phien_ban"])
            for record in active_records
        })

        verified: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        for question in dataset:
            reason = _pending_reason(question)
            if reason is None and question["expected_status"] == "ThanhCong":
                source_matches, source_reason = _verify_source_record(
                    question, active_documents
                )
                if source_matches:
                    verified.append(question)
                else:
                    reason = source_reason
            elif reason is None:
                verified.append(question)
            if reason:
                missing_fields = [
                    field for field in (
                        "expected_status",
                        "expected_answer",
                        "expected_keywords",
                        "expected_ma_doan",
                        "expected_document_id",
                        "expected_version",
                        "expected_article",
                        "reviewed_by",
                        "reviewed_at",
                    )
                    if not question.get(field)
                ]
                pending.append({
                    "id": question["id"],
                    "question": question["question"],
                    "status": "Pending",
                    "reason": reason,
                    "review_status": question.get("review_status"),
                    "review_note": question.get("review_note"),
                    "preliminary_match_status": question.get(
                        "preliminary_match_status"
                    ),
                    "preliminary_note": question.get("preliminary_note"),
                    "candidate_sources": question.get("candidate_sources", []),
                    "retrieval_diagnostics_not_verified": question.get(
                        "retrieval_diagnostics_not_verified", []
                    ),
                    "missing_reference_fields": missing_fields,
                })

        report["pending_verification_questions"] = pending
        report["verified_question_count"] = len(verified)
        if pending and not preliminary:
            report["status"] = "Pending"
            report["question_results"] = pending
            report["errors"].append(
                "Unverified questions were not run. Official metrics are "
                "calculated only for questions with verified references."
            )
            write_audit_log(
                event="MODEL_EVALUATION_BLOCKED",
                trace_id=trace_id,
                ma_phien=document_version_id,
                status="Pending",
                details={
                    "pending_question_count": len(pending),
                    "verified_question_count": len(verified),
                    "dataset_question_count": len(dataset),
                },
            )
        else:
            verified_by_id = {question["id"]: question for question in verified}
            questions_to_run = dataset if preliminary else verified
            question_results = [
                {
                    "id": question["id"],
                    "question": question["question"],
                    "status": "Running",
                    "preliminary_match_status": question.get(
                        "preliminary_match_status"
                    ),
                    "preliminary_note": question.get("preliminary_note"),
                    "candidate_sources": question.get("candidate_sources", []),
                    "retrieval_diagnostics_not_verified": question.get(
                        "retrieval_diagnostics_not_verified", []
                    ),
                    "retrieval": None,
                    "response_status": None,
                    "generated_answer": None,
                    "retrieved_sources": [],
                    "scores": None,
                    "error": None,
                }
                for question in questions_to_run
            ]
            report["status"] = "Running"
            report["question_results"] = question_results
            report["preliminary_metrics"] = _aggregate_preliminary_metrics(
                question_results
            )
            _write_report(report, document_version_id)
            for index, question in enumerate(questions_to_run):
                verified_question = verified_by_id.get(question["id"])
                if verified_question:
                    result = await _run_question(
                        verified_question,
                        active_documents,
                    )
                    result.update({
                        "expected_status": verified_question["expected_status"],
                        "expected_answer": verified_question.get("expected_answer"),
                        "expected_keywords": verified_question.get("expected_keywords"),
                        "expected_ma_doan": verified_question.get("expected_ma_doan"),
                        "expected_document_id": verified_question.get(
                            "expected_document_id"
                        ),
                        "expected_version": verified_question.get("expected_version"),
                        "expected_article": verified_question.get("expected_article"),
                        "question_type": verified_question.get("question_type"),
                        "review_status": verified_question.get("review_status"),
                        "reviewed_by": verified_question["reviewed_by"],
                        "reviewed_at": verified_question["reviewed_at"],
                    })
                else:
                    result = await _run_preliminary_question(question)

                question_results[index] = result
                report["failed_questions"] = [
                    {
                        "id": item["id"],
                        "question": item["question"],
                        "error": item["error"],
                    }
                    for item in question_results
                    if item.get("status") == "Failed"
                ]
                report["metrics"] = _aggregate_metrics(question_results)
                report["preliminary_metrics"] = _aggregate_preliminary_metrics(
                    question_results
                )
                report["official"] = bool(
                    verified and any(
                        item.get("reviewed_by") for item in question_results
                    )
                )
                _write_report(report, document_version_id)

            report["failed_questions"] = [
                {
                    "id": item["id"],
                    "question": item["question"],
                    "error": item["error"],
                }
                for item in question_results
                if item.get("status") == "Failed"
            ]
            report["metrics"] = _aggregate_metrics(question_results)
            report["preliminary_metrics"] = _aggregate_preliminary_metrics(
                question_results
            )
            report["official"] = bool(verified)
            report["status"] = "Preliminary" if pending else "Completed"
            if pending:
                report["errors"].append(
                    "Unverified questions have no official scores. Any "
                    "official metrics shown cover verified questions only."
                )
            if report["metrics"]["accuracy"] is not None:
                report["database_persistence"] = (
                    _persist_existing_evaluation_result(report)
                )
                if report["database_persistence"]["status"] == "failed":
                    report["errors"].append(
                        report["database_persistence"]["reason"]
                    )
            write_audit_log(
                event=(
                    "MODEL_EVALUATION_PRELIMINARY_COMPLETED"
                    if pending else "MODEL_EVALUATION_COMPLETED"
                ),
                trace_id=trace_id,
                ma_phien=document_version_id,
                status=report["status"],
                details={
                    "evaluation_id": report["evaluation_id"],
                    "metrics": report["metrics"],
                    "preliminary_metrics": report["preliminary_metrics"],
                    "failed_question_count": len(report["failed_questions"]),
                    "database_persistence": report["database_persistence"],
                },
            )
    except Exception as error:
        logger.exception("Evaluation failed for document %s", document_version_id)
        report["status"] = "Failed"
        report["errors"].append(f"{type(error).__name__}: {error}")
        write_audit_log(
            event="MODEL_EVALUATION_FAILED",
            trace_id=trace_id,
            ma_phien=document_version_id,
            status="Failed",
            details={"error_type": type(error).__name__, "error": str(error)},
        )
    finally:
        report["completed_at"] = _utc_now()
        try:
            _write_report(report, document_version_id)
        except OSError:
            logger.exception(
                "Could not write evaluation report for %s", document_version_id
            )
        with _claim_lock:
            _claimed_document_versions.discard(document_version_id)


@router.get("/latest")
def get_latest_evaluation_report(
    _current_user: AuthenticatedUser = Depends(
        require_roles("QuanTriVien")
    ),
) -> dict[str, Any]:
    report_path = REPORT_DIR / "evaluation_latest.json"
    try:
        with report_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="No evaluation report is available yet.",
        ) from error
    except json.JSONDecodeError as error:
        logger.exception("Latest evaluation report is invalid.")
        raise HTTPException(
            status_code=500,
            detail="The latest evaluation report is invalid.",
        ) from error


@router.delete("/latest")
def clear_latest_evaluation_report(
    _current_user: AuthenticatedUser = Depends(
        require_roles("QuanTriVien")
    ),
) -> dict[str, str]:
    report_path = REPORT_DIR / "evaluation_latest.json"
    with _claim_lock:
        if _claimed_document_versions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Không thể xóa báo cáo khi benchmark đang chạy.",
            )
        try:
            report_path.unlink(missing_ok=True)
        except OSError as error:
            logger.exception("Could not clear the latest evaluation report.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể xóa báo cáo đánh giá mới nhất.",
            ) from error
    return {"message": "Đã xóa báo cáo đánh giá mới nhất."}


@router.post("/run-latest", status_code=status.HTTP_202_ACCEPTED)
def run_evaluation_for_latest_active_document(
    background_tasks: BackgroundTasks,
    _current_user: AuthenticatedUser = Depends(
        require_roles("QuanTriVien")
    ),
) -> dict[str, str]:
    conn = None
    try:
        conn = get_business_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TOP (1) MaPhienBan
            FROM dbo.PHIEN_BAN_TAI_LIEU
            WHERE TrangThai = 'Approved'
              AND is_active = 1
            ORDER BY NgayHieuLuc DESC, MaPhienBan DESC
            """
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Không có tài liệu nào được phê duyệt và đang hoạt động; "
                    "đánh giá đã dừng, không sử dụng phiên bản cũ."
                ),
            )

        document_version_id = str(row[0])
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Could not find an active document for evaluation.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tìm phiên bản tài liệu để đánh giá.",
        ) from error
    finally:
        if conn:
            conn.close()

    background_tasks.add_task(
        run_evaluation_for_document,
        document_version_id,
        preliminary=True,
    )
    return {
        "message": "Đã đưa đánh giá hiệu năng vào hàng đợi.",
        "document_version_id": document_version_id,
        "status": "Pending",
    }