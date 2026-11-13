import asyncio
import json

from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from app.api.v1 import documents, evaluation
from app.core.security import AuthenticatedUser, get_current_user
from app.main import app


def _active_document_records():
    return [{
        "ma_doan": "D1",
        "ma_tai_lieu": "DOC1",
        "ma_phien_ban": "VERSION1",
        "so_phien_ban": "1.0",
        "dieu_khoan": "Article 1",
        "noi_dung": "Alpha beta",
    }]


def test_dataset_has_50_unverified_questions():
    dataset = evaluation.load_dataset()

    assert len(dataset) == 50
    assert sum(bool(item.get("candidate_sources")) for item in dataset) == 10
    assert sum(
        item["preliminary_match_status"] == "NO_DIRECT_EVIDENCE_IN_CURRENT_199_CHUNKS"
        for item in dataset
    ) == 35
    assert sum(
        item["preliminary_match_status"] == "OUT_OF_SCOPE_REFUSAL"
        for item in dataset
    ) == 5
    assert all(
        "Question has not completed legal-officer review."
        in evaluation._pending_reason(question)
        for question in dataset
    )


def test_unverified_dataset_blocks_rag_and_writes_pending_report(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(
        evaluation, "_load_active_document_records", _active_document_records
    )
    monkeypatch.setattr(evaluation, "write_audit_log", lambda **kwargs: None)
    monkeypatch.setattr(
        evaluation,
        "retrieve_evidence",
        lambda question: (_ for _ in ()).throw(
            AssertionError("RAG must not run while references are unverified.")
        ),
    )
    document_version_id = "PB_EVALUATION_PENDING_TEST"
    evaluation._claimed_document_versions.discard(document_version_id)

    asyncio.run(evaluation.run_evaluation_for_document(document_version_id))

    report = json.loads(
        (tmp_path / "evaluation_latest.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "Pending"
    assert report["official"] is False
    assert report["dataset_question_count"] == 50
    assert report["verified_question_count"] == 0
    assert report["metrics"]["scored_questions"] == 0
    assert report["metrics"]["accuracy"] is None
    assert report["metrics"]["faithfulness"] is None
    assert report["metrics"]["citation_correctness"] is None
    assert document_version_id not in evaluation._claimed_document_versions
    assert [item["id"] for item in report["pending_verification_questions"]] == [
        f"EVAL{number:03d}" for number in range(1, 51)
    ]
    candidate_question = next(
        item for item in report["pending_verification_questions"]
        if item["id"] == "EVAL028"
    )
    assert candidate_question["preliminary_match_status"] == (
        "CANDIDATE_SOURCE_FOUND_REQUIRES_REVIEW"
    )
    assert candidate_question["candidate_sources"][0]["ma_doan_candidate"] == (
        "D_B195037637"
    )


def test_preliminary_evaluation_runs_unverified_questions_without_official_scores(
    monkeypatch, tmp_path
):
    async def retrieve(_question):
        return {
            "qualified": True,
            "best_score": 0.82,
            "threshold": 0.7,
            "total_active_vectors": 12,
            "chunks": [{"ma_doan": "D1", "noi_dung": "Source text"}],
        }

    async def generate_answer(**_kwargs):
        return "Generated answer"

    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(
        evaluation, "_load_active_document_records", _active_document_records
    )
    monkeypatch.setattr(evaluation, "write_audit_log", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "retrieve_evidence", retrieve)
    monkeypatch.setattr(evaluation.chat, "generate_answer", generate_answer)
    monkeypatch.setattr(
        evaluation.chat,
        "build_citations",
        lambda _chunks: [{"ma_doan": "D1"}],
    )
    document_version_id = "PB_PRELIMINARY_TEST"
    evaluation._claimed_document_versions.discard(document_version_id)

    asyncio.run(
        evaluation.run_evaluation_for_document(
            document_version_id,
            preliminary=True,
        )
    )

    report = json.loads(
        (tmp_path / "evaluation_latest.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "Preliminary"
    assert report["official"] is False
    assert report["verified_question_count"] == 0
    assert report["metrics"]["scored_questions"] == 0
    assert report["preliminary_metrics"] == {
        "questions_attempted": 50,
        "questions_completed": 50,
        "qualified_retrievals": 50,
        "retrieval_coverage": 1.0,
        "generated_answers": 50,
        "refusals": 0,
        "failed_questions": 0,
    }
    assert report["question_results"][0]["generated_answer"] == "Generated answer"
    assert report["question_results"][0]["scores"] is None


def test_question_failure_is_recorded_without_raising(monkeypatch):
    async def fail_retrieval(question):
        raise RuntimeError("retrieval unavailable")

    monkeypatch.setattr(evaluation, "retrieve_evidence", fail_retrieval)
    result = asyncio.run(evaluation._run_question({
        "id": "EVAL_TEST",
        "question": "Question",
    }))

    assert result["status"] == "Failed"
    assert "retrieval unavailable" in result["error"]


def test_question_metrics_compare_answer_keywords_and_source():
    scores = evaluation._answer_metrics(
        {
            "expected_status": "ThanhCong",
            "expected_answer": "Alpha beta",
            "expected_keywords": ["Alpha", "beta"],
            "expected_ma_doan": "D1",
            "expected_version": "1.0",
            "expected_article": "Article 1",
        },
        "Alpha beta",
        "ThanhCong",
        [{
            "ma_doan": "D1",
            "so_phien_ban": "1.0",
            "dieu_khoan": "Article 1",
        }],
        [{"ma_doan": "D1", "noi_dung": "Alpha beta"}],
    )

    assert scores["accuracy_score"] == 1
    assert scores["faithfulness_score"] == 1
    assert scores["citation_correct"] is True


def test_wrong_answer_and_unsupported_claim_reduce_quality_scores():
    question = {
        "expected_status": "ThanhCong",
        "expected_answer": "Alpha beta",
        "expected_keywords": ["Alpha", "beta"],
        "expected_ma_doan": "D1",
        "expected_version": "1.0",
        "expected_article": "Article 1",
    }
    scores = evaluation._answer_metrics(
        question,
        "Alpha beta. Gamma is required.",
        "ThanhCong",
        [{
            "ma_doan": "D1",
            "so_phien_ban": "1.0",
            "dieu_khoan": "Article 1",
        }],
        [{"ma_doan": "D1", "noi_dung": "Alpha beta"}],
    )

    assert 0 < scores["accuracy_score"] < 1
    assert scores["faithfulness_checked_claims"] == 2
    assert scores["faithfulness_supported_claims"] == 1
    assert scores["faithfulness_score"] == 0.5


def test_contradictory_negation_does_not_pass_content_accuracy():
    scores = evaluation._answer_metrics(
        {
            "expected_status": "ThanhCong",
            "expected_answer": "Alpha beta",
            "expected_keywords": ["Alpha", "beta"],
            "expected_ma_doan": "D1",
        },
        "Không Alpha beta",
        "ThanhCong",
        [],
        [{"ma_doan": "D1", "noi_dung": "Alpha beta"}],
    )

    assert scores["keyword_score"] == 1
    assert scores["answer_similarity"] == 0.8
    assert scores["accuracy_score"] == 0


def test_invalid_citation_is_counted_against_citation_accuracy():
    scores = evaluation._answer_metrics(
        {
            "expected_status": "ThanhCong",
            "expected_answer": "Alpha beta",
            "expected_keywords": ["Alpha", "beta"],
            "expected_ma_doan": "D1",
            "expected_version": "1.0",
            "expected_article": "Article 1",
        },
        "Alpha beta",
        "ThanhCong",
        [
            {
                "ma_doan": "D1",
                "so_phien_ban": "1.0",
                "dieu_khoan": "Article 1",
            },
            {
                "ma_doan": "D2",
                "so_phien_ban": "1.0",
                "dieu_khoan": "Article 1",
            },
        ],
        [{"ma_doan": "D1", "noi_dung": "Alpha beta"}],
    )

    assert scores["citation_checked_count"] == 2
    assert scores["citation_correct_count"] == 1
    assert scores["citation_score"] == 0.5


def test_correct_refusal_is_not_accuracy_and_is_counted_separately():
    assert evaluation._pending_reason({
        "expected_status": "TuChoi",
        "review_status": "VERIFIED",
        "reviewed_by": "legal-reviewer",
        "reviewed_at": "2026-11-08T00:00:00Z",
    }) is None

    scores = evaluation._answer_metrics(
        {"expected_status": "TuChoi"},
        "I cannot answer that.",
        "TuChoi",
        [],
        [],
    )

    assert scores["accuracy_score"] is None
    assert scores["faithfulness_checked_claims"] == 0
    assert scores["citation_checked_count"] == 0
    assert scores["correct_refusal"] is True


def test_wrong_refusal_for_in_scope_question_counts_as_incorrect_answer():
    scores = evaluation._answer_metrics(
        {
            "expected_status": "ThanhCong",
            "expected_answer": "Alpha beta",
            "expected_keywords": ["Alpha", "beta"],
            "expected_ma_doan": "D1",
        },
        "I cannot answer that.",
        "TuChoi",
        [],
        [],
    )

    assert scores["accuracy_score"] == 0


def test_aggregate_metrics_exclude_failed_questions_from_score_denominator():
    results = [
        {
            "status": "Completed",
            "expected_status": "ThanhCong",
            "scores": {
                "accuracy_score": 1.0,
                "faithfulness_checked_claims": 5,
                "faithfulness_supported_claims": 4,
                "citation_checked_count": 1,
                "citation_correct_count": 1,
                "status_correct": True,
            },
        },
        {
            "status": "Failed",
            "expected_status": "ThanhCong",
            "scores": None,
        },
        {
            "status": "Completed",
            "expected_status": "TuChoi",
            "scores": {
                "accuracy_score": None,
                "faithfulness_checked_claims": 0,
                "faithfulness_supported_claims": 0,
                "citation_checked_count": 0,
                "citation_correct_count": 0,
                "correct_refusal": True,
            },
        },
    ]

    metrics = evaluation._aggregate_metrics(results)

    assert metrics["accuracy"] == 1.0
    assert metrics["faithfulness"] == 0.8
    assert metrics["citation_correctness"] == 1.0
    assert metrics["accuracy_sample_count"] == 1
    assert metrics["faithfulness_sample_count"] == 5
    assert metrics["citation_sample_count"] == 1
    assert metrics["correct_refusal_rate"] == 1.0
    assert metrics["correct_refusal_sample_count"] == 1
    assert metrics["scored_questions"] == 1
    assert metrics["failed_questions"] == 1


def test_metrics_are_unavailable_when_no_valid_samples_exist():
    metrics = evaluation._aggregate_metrics([
        {
            "status": "Failed",
            "expected_status": "ThanhCong",
            "scores": None,
        },
    ])

    assert metrics["accuracy"] is None
    assert metrics["faithfulness"] is None
    assert metrics["citation_correctness"] is None
    assert metrics["accuracy_sample_count"] == 0
    assert metrics["faithfulness_sample_count"] == 0
    assert metrics["citation_sample_count"] == 0


def test_partially_verified_run_scores_only_verified_questions(
    monkeypatch, tmp_path
):
    verified = {
        "id": "EVAL001",
        "question": "Question with a verified answer",
        "expected_status": "ThanhCong",
        "expected_answer": "Alpha beta",
        "expected_keywords": ["Alpha", "beta"],
        "expected_ma_doan": "D1",
        "expected_document_id": "DOC1",
        "expected_version": "1.0",
        "expected_article": "Article 1",
        "review_status": "VERIFIED",
        "reviewed_by": "legal-reviewer",
        "reviewed_at": "2026-11-08T00:00:00Z",
    }
    pending = {
        "id": "EVAL002",
        "question": "Question without a verified answer",
        "expected_status_candidate": "ThanhCong",
        "expected_answer": None,
        "expected_keywords": [],
        "expected_ma_doan": None,
        "expected_document_id": None,
        "expected_version": None,
        "expected_article": None,
        "review_status": "PENDING_LEGAL_REVIEW",
        "preliminary_match_status": "NO_DIRECT_EVIDENCE_IN_CURRENT_199_CHUNKS",
    }

    async def retrieve(_question):
        return {
            "qualified": True,
            "best_score": 0.9,
            "threshold": 0.7,
            "total_active_vectors": 1,
            "chunks": [{
                "ma_doan": "D1",
                "noi_dung": "Alpha beta",
                "dieu_khoan": "Article 1",
                "so_phien_ban": "1.0",
            }],
        }

    async def generate_answer(**_kwargs):
        return "Alpha beta"

    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(evaluation, "load_dataset", lambda: [verified, pending])
    monkeypatch.setattr(
        evaluation, "_load_active_document_records", _active_document_records
    )
    monkeypatch.setattr(
        evaluation,
        "_verify_source_record",
        lambda _question, _active_documents=None: (True, None),
    )
    monkeypatch.setattr(evaluation, "write_audit_log", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "retrieve_evidence", retrieve)
    monkeypatch.setattr(evaluation.chat, "generate_answer", generate_answer)
    monkeypatch.setattr(
        evaluation.chat,
        "build_citations",
        lambda _chunks: [{
            "ma_doan": "D1",
            "dieu_khoan": "Article 1",
            "so_phien_ban": "1.0",
        }],
    )
    monkeypatch.setattr(
        evaluation,
        "_persist_existing_evaluation_result",
        lambda _report: {"status": "skipped"},
    )
    document_version_id = "PB_PARTIALLY_VERIFIED_TEST"
    evaluation._claimed_document_versions.discard(document_version_id)

    asyncio.run(
        evaluation.run_evaluation_for_document(
            document_version_id,
            preliminary=True,
        )
    )

    report = json.loads(
        (tmp_path / "evaluation_latest.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "Preliminary"
    assert report["official"] is True
    assert report["dataset_question_count"] == 2
    assert report["verified_question_count"] == 1
    assert len(report["pending_verification_questions"]) == 1
    assert report["metrics"]["accuracy"] == 1.0
    assert report["metrics"]["scored_questions"] == 1
    assert report["preliminary_metrics"]["questions_attempted"] == 2
    assert report["preliminary_metrics"]["generated_answers"] == 2
    assert report["question_results"][1]["scores"] is None

    previous_evaluation_id = report["evaluation_id"]
    asyncio.run(
        evaluation.run_evaluation_for_document(
            document_version_id,
            preliminary=True,
        )
    )
    repeated_report = json.loads(
        (tmp_path / "evaluation_latest.json").read_text(encoding="utf-8")
    )
    assert repeated_report["evaluation_id"] != previous_evaluation_id
    assert repeated_report["metrics"]["accuracy"] == 1.0
    assert repeated_report["preliminary_metrics"]["questions_attempted"] == 2
    assert len(repeated_report["question_results"]) == 2


def test_latest_report_returns_not_found_when_no_report_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        ma_nd="ADMIN",
        vai_tro="QuanTriVien",
    )
    try:
        response = TestClient(app).get("/api/v1/evaluation/latest")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404


def test_latest_report_endpoint_returns_saved_json(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)
    expected_report = {"status": "Pending", "official": False}
    (tmp_path / "evaluation_latest.json").write_text(
        json.dumps(expected_report),
        encoding="utf-8",
    )

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        ma_nd="ADMIN",
        vai_tro="QuanTriVien",
    )
    try:
        response = TestClient(app).get("/api/v1/evaluation/latest")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == expected_report


def test_admin_can_clear_latest_report_without_deleting_version_history(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(evaluation, "_claimed_document_versions", set())
    latest_report = tmp_path / "evaluation_latest.json"
    version_report = tmp_path / "evaluation_PB_TEST.json"
    latest_report.write_text("{}", encoding="utf-8")
    version_report.write_text("{}", encoding="utf-8")

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        ma_nd="ADMIN",
        vai_tro="QuanTriVien",
    )
    try:
        response = TestClient(app).delete("/api/v1/evaluation/latest")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert not latest_report.exists()
    assert version_report.exists()


def test_cannot_clear_latest_report_during_active_evaluation(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(
        evaluation, "_claimed_document_versions", {"PB_RUNNING"}
    )
    latest_report = tmp_path / "evaluation_latest.json"
    latest_report.write_text("{}", encoding="utf-8")

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        ma_nd="ADMIN",
        vai_tro="QuanTriVien",
    )
    try:
        response = TestClient(app).delete("/api/v1/evaluation/latest")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 409
    assert latest_report.exists()


def test_admin_can_schedule_evaluation_for_latest_active_version(monkeypatch):
    class Cursor:
        def execute(self, query, *params):
            self.query = query
            self.params = params

        def fetchone(self):
            return ("PB_ACTIVE",)

    class Connection:
        closed = False

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    connection = Connection()
    scheduled = []
    monkeypatch.setattr(
        evaluation, "get_business_db_connection", lambda: connection
    )
    monkeypatch.setattr(
        evaluation,
        "run_evaluation_for_document",
        lambda version_id, **kwargs: scheduled.append((version_id, kwargs)),
    )
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        ma_nd="ADMIN",
        vai_tro="QuanTriVien",
    )
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/evaluation/run-latest")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 202
    assert response.json()["document_version_id"] == "PB_ACTIVE"
    assert connection.closed
    assert scheduled == [("PB_ACTIVE", {"preliminary": True})]


def test_run_latest_evaluation_returns_not_found_without_active_version(
    monkeypatch,
):
    class Cursor:
        def execute(self, _query):
            pass

        def fetchone(self):
            return None

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(
        evaluation, "get_business_db_connection", Connection
    )
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        ma_nd="ADMIN",
        vai_tro="QuanTriVien",
    )
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/evaluation/run-latest")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404
    assert "không sử dụng phiên bản cũ" in response.json()["detail"]


def test_active_document_snapshot_tracks_version_switch_and_multiple_documents(
    monkeypatch,
):
    snapshots = [
        [
            ("SEG_OLD", "DOC1", "PB_OLD", "1.0", "Điều 1", "Old source"),
            ("SEG_OTHER", "DOC2", "PB_OTHER", "3.0", "Điều 2", "Other source"),
        ],
        [
            ("SEG_NEW", "DOC1", "PB_NEW", "2.0", "Điều 1", "New source"),
            ("SEG_OTHER", "DOC2", "PB_OTHER", "3.0", "Điều 2", "Other source"),
        ],
    ]
    statements = []

    class Cursor:
        def execute(self, query):
            statements.append(query)

        def fetchall(self):
            return snapshots.pop(0)

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(
        evaluation, "get_business_db_connection", lambda: Connection()
    )

    first_snapshot = evaluation._load_active_document_records()
    second_snapshot = evaluation._load_active_document_records()

    assert {record["ma_tai_lieu"] for record in first_snapshot} == {
        "DOC1",
        "DOC2",
    }
    assert {
        record["ma_phien_ban"] for record in second_snapshot
    } == {"PB_NEW", "PB_OTHER"}
    assert all("p.is_active = 1" in query for query in statements)
    assert all("p.TrangThai = 'Approved'" in query for query in statements)
    assert all("TOP (1)" not in query for query in statements)


def test_active_source_snapshot_rejects_stale_version_and_bad_cited_content():
    question = {
        "expected_status": "ThanhCong",
        "expected_answer": "Current legal text",
        "expected_keywords": ["Current", "legal", "text"],
        "expected_ma_doan": "SEG_NEW",
        "expected_document_id": "DOC1",
        "expected_version": "2.0",
        "expected_ma_phien_ban": "PB_NEW",
        "expected_article": "Điều 1",
    }
    active_documents = {
        "SEG_NEW": {
            "ma_doan": "SEG_NEW",
            "ma_tai_lieu": "DOC1",
            "ma_phien_ban": "PB_NEW",
            "so_phien_ban": "2.0",
            "dieu_khoan": "Điều 1",
            "noi_dung": "Current legal text",
        },
    }
    stale_chunk = {
        "ma_doan": "SEG_OLD",
        "ma_phien_ban": "PB_OLD",
        "so_phien_ban": "1.0",
        "dieu_khoan": "Điều 1",
        "noi_dung": "Current legal text",
    }
    stale_reference = {
        **question,
        "expected_ma_doan": "SEG_OLD",
        "expected_version": "1.0",
        "expected_ma_phien_ban": "PB_OLD",
    }

    assert evaluation._verify_source_record(
        stale_reference, active_documents
    ) == (
        False,
        "Reference chunk is not in the active approved document repository.",
    )

    scores = evaluation._answer_metrics(
        question,
        "Current legal text",
        "ThanhCong",
        [{
            "ma_doan": "SEG_NEW",
            "ma_phien_ban": "PB_NEW",
            "so_phien_ban": "2.0",
            "dieu_khoan": "Điều 1",
            "noi_dung_trich": "Outdated or altered source",
        }],
        [{
            **stale_chunk,
            "ma_doan": "SEG_NEW",
            "ma_phien_ban": "PB_NEW",
            "so_phien_ban": "2.0",
        }],
        active_documents,
    )

    assert scores["accuracy_score"] == 1
    assert scores["faithfulness_score"] == 1
    assert scores["citation_correct_count"] == 0
    assert scores["citation_score"] == 0


def test_active_source_content_marks_unsupported_claims_unfaithful():
    question = {
        "expected_status": "ThanhCong",
        "expected_answer": "Alpha beta",
        "expected_keywords": ["Alpha", "beta"],
        "expected_ma_doan": "SEG1",
        "expected_document_id": "DOC1",
        "expected_version": "1.0",
        "expected_article": "Article 1",
    }
    active_record = {
        "ma_doan": "SEG1",
        "ma_tai_lieu": "DOC1",
        "ma_phien_ban": "PB1",
        "so_phien_ban": "1.0",
        "dieu_khoan": "Article 1",
        "noi_dung": "Alpha beta",
    }

    scores = evaluation._answer_metrics(
        question,
        "Alpha beta. Gamma is required.",
        "ThanhCong",
        [{
            "ma_doan": "SEG1",
            "ma_phien_ban": "PB1",
            "so_phien_ban": "1.0",
            "dieu_khoan": "Article 1",
            "noi_dung_trich": "Alpha beta",
        }],
        [{
            "ma_doan": "SEG1",
            "ma_phien_ban": "PB1",
            "so_phien_ban": "1.0",
            "dieu_khoan": "Article 1",
            "noi_dung": "Alpha beta",
        }],
        {"SEG1": active_record},
    )

    assert scores["faithfulness_checked_claims"] == 2
    assert scores["faithfulness_supported_claims"] == 1
    assert scores["faithfulness_score"] == 0.5


def test_evaluation_stops_when_active_document_snapshot_is_empty(
    monkeypatch, tmp_path
):
    document_version_id = "PB_NO_ACTIVE_DOCUMENTS"
    monkeypatch.setattr(evaluation, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(evaluation, "write_audit_log", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "_load_active_document_records", lambda: [])
    monkeypatch.setattr(
        evaluation,
        "load_dataset",
        lambda: [{"id": "EVAL001", "question": "Question"}],
    )
    monkeypatch.setattr(
        evaluation,
        "retrieve_evidence",
        lambda _question: (_ for _ in ()).throw(
            AssertionError("Retrieval must not run without active documents.")
        ),
    )
    evaluation._claimed_document_versions.discard(document_version_id)

    asyncio.run(evaluation.run_evaluation_for_document(document_version_id))

    report = json.loads(
        (tmp_path / "evaluation_latest.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "NoActiveDocuments"
    assert report["dataset_question_count"] == 1
    assert report["preliminary_metrics"] is None
    assert report["metrics"]["accuracy"] is None
    assert report["active_document_count"] == 0
    assert "No approved active documents" in report["errors"][0]


def test_approval_schedules_evaluation_after_commit(monkeypatch):
    class Cursor:
        rowcount = 1

        def __init__(self):
            self.statements = []

        def execute(self, query, *params):
            self.query = query
            self.params = params
            self.statements.append((query, params))
            return self

    class Connection:
        committed = False
        closed = False

        def cursor(self):
            return Cursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("Successful approval must not roll back.")

        def close(self):
            self.closed = True

    connection = Connection()
    cursor = Cursor()
    connection.cursor = lambda: cursor
    monkeypatch.setattr(
        documents, "get_business_db_connection", lambda: connection
    )
    monkeypatch.setattr(
        documents,
        "run_evaluation_for_document",
        lambda *_args: None,
    )
    monkeypatch.setattr(documents, "write_audit_log", lambda **_entry: None)
    background_tasks = BackgroundTasks()

    response = asyncio.run(
        documents.approve_document_version(
            "PB_APPROVED_TEST",
            background_tasks,
            AuthenticatedUser(
                ma_nd="UPLOADER",
                vai_tro="ChuyenVienPhapChe",
            ),
        )
    )

    assert response["trang_thai"] == "Approved"
    assert response["evaluation_status"] == "Pending"
    assert connection.committed
    assert connection.closed
    assert "MaND <>" not in cursor.query
    assert cursor.params == (("PB_APPROVED_TEST",),)
    assert "SET TrangThai = 'Expired'" in cursor.statements[0][0]
    assert "SET TrangThai = 'Approved'" in cursor.statements[1][0]
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].args == ("PB_APPROVED_TEST",)
