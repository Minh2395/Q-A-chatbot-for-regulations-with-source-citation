import asyncio
import json

from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from app.api.v1 import documents, evaluation
from app.core.security import AuthenticatedUser, get_current_user
from app.main import app


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
        },
        "Alpha beta",
        "ThanhCong",
        [{"ma_doan": "D1"}],
        [{"noi_dung": "Alpha beta"}],
    )

    assert scores["accuracy_score"] == 1
    assert scores["faithfulness_score"] == 1
    assert scores["citation_correct"] is True


def test_aggregate_metrics_exclude_failed_questions_from_score_denominator():
    results = [
        {
            "status": "Completed",
            "expected_status": "ThanhCong",
            "scores": {
                "accuracy_score": 1.0,
                "faithfulness_score": 0.8,
                "citation_score": 1.0,
                "status_correct": True,
            },
        },
        {
            "status": "Failed",
            "expected_status": "ThanhCong",
            "scores": None,
        },
    ]

    metrics = evaluation._aggregate_metrics(results)

    assert metrics["accuracy"] == 1.0
    assert metrics["faithfulness"] == 0.8
    assert metrics["citation_correctness"] == 1.0
    assert metrics["scored_questions"] == 1
    assert metrics["failed_questions"] == 1


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
