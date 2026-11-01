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
    assert [item["id"] for item in report["pending_verification_questions"]] == [
        f"EVAL{number:03d}" for number in range(1, 51)
    ]


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


def test_approval_schedules_evaluation_after_commit(monkeypatch):
    class Cursor:
        rowcount = 1

        def execute(self, query, *params):
            self.query = query
            self.params = params
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
                ma_nd="REVIEWER",
                vai_tro="ChuyenVienPhapChe",
            ),
        )
    )

    assert response["trang_thai"] == "Approved"
    assert response["evaluation_status"] == "Pending"
    assert connection.committed
    assert connection.closed
    assert "AND MaND <> ?" in cursor.query
    assert cursor.params == (("PB_APPROVED_TEST", "REVIEWER"),)
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].args == ("PB_APPROVED_TEST",)
