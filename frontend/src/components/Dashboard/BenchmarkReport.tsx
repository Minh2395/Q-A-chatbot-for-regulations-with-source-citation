import { useCallback, useEffect, useState } from "react";
import {
  getApiErrorMessage,
  getLatestEvaluationReport,
  runLatestEvaluation,
} from "../../services/api";
import type { EvaluationReport } from "../../services/api";

const metrics = [
  { name: "Độ chính xác", key: "accuracy" },
  { name: "Tính trung thành", key: "faithfulness" },
  { name: "Độ chính xác trích dẫn", key: "citation_correctness" },
] as const;

function statusLabel(status: EvaluationReport["status"] | undefined): string {
  switch (status) {
    case "Completed":
      return "Đã hoàn tất";
    case "Running":
      return "Đang chạy";
    case "Pending":
      return "Chờ xác minh";
    case "Preliminary":
      return "Đã chạy thử · chưa chấm chính thức";
    case "Failed":
      return "Thất bại";
    default:
      return "Chưa có báo cáo";
  }
}

function formatScore(score: number | null | undefined): string {
  return score == null ? "Chưa có dữ liệu" : `${(score * 100).toFixed(1)}%`;
}

function preliminaryMatchLabel(status: string | null | undefined): string {
  switch (status) {
    case "CANDIDATE_SOURCE_FOUND_REQUIRES_REVIEW":
      return "Có nguồn ứng viên, cần chuyên viên xác minh";
    case "NO_DIRECT_EVIDENCE_IN_CURRENT_199_CHUNKS":
      return "Chưa tìm được nguồn phù hợp trong dữ liệu hiện tại";
    case "OUT_OF_SCOPE_REFUSAL":
      return "Câu hỏi ngoài phạm vi, cần xác nhận cách từ chối";
    default:
      return "Chưa phân loại";
  }
}

export function BenchmarkReport() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [queuedRun, setQueuedRun] = useState<{
    documentVersionId: string;
    previousStartedAt?: string;
  } | null>(null);
  const [error, setError] = useState("");
  const needsPreliminaryRun = Boolean(
    report &&
      report.verified_question_count < report.dataset_question_count,
  );

  const loadReport = useCallback(async () => {
    try {
      const latestReport = await getLatestEvaluationReport();
      setReport(latestReport);
      setError("");
    } catch (loadError: unknown) {
      setError(
        getApiErrorMessage(loadError, "Không thể tải báo cáo đánh giá."),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;

    const pollReport = async () => {
      try {
        const latestReport = await getLatestEvaluationReport();
        if (active) {
          setReport(latestReport);
          if (
            queuedRun &&
            latestReport?.document_version_id === queuedRun.documentVersionId &&
            latestReport.started_at !== queuedRun.previousStartedAt
          ) {
            setQueuedRun(null);
          }
          setError("");
          timer = window.setTimeout(
            pollReport,
            latestReport?.status === "Running" ? 2500 : 10000,
          );
        }
      } catch (loadError: unknown) {
        if (active) {
          setError(
            getApiErrorMessage(loadError, "Không thể tải báo cáo đánh giá."),
          );
          timer = window.setTimeout(pollReport, 10000);
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    void pollReport();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [queuedRun]);

  const handleRun = async () => {
    if (running || queuedRun || report?.status === "Running") return;
    setRunning(true);
    setError("");
    try {
      const result = await runLatestEvaluation();
      setQueuedRun({
        documentVersionId: result.document_version_id,
        previousStartedAt:
          report?.document_version_id === result.document_version_id
            ? report.started_at
            : undefined,
      });
    } catch (runError: unknown) {
      setError(
        getApiErrorMessage(runError, "Không thể bắt đầu đánh giá mô hình."),
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="surface-card admin-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">CHẤT LƯỢNG MÔ HÌNH</p>
          <h2>Đánh giá hiệu năng AI</h2>
        </div>
        <span className="status-pill status-unavailable">
          {loading
            ? "Đang tải"
            : queuedRun
              ? "Đang chạy"
              : statusLabel(report?.status)}
        </span>
      </div>
      <p className="muted">
        Chạy thử truy xuất và tạo câu trả lời trên bộ câu hỏi. Chỉ số chính thức
        chỉ xuất hiện sau khi đáp án và nguồn tham chiếu được xác minh pháp lý.
      </p>
      <div className="document-actions">
        <button
          className="primary-button"
          type="button"
          onClick={() => void handleRun()}
          disabled={running || Boolean(queuedRun) || report?.status === "Running"}
        >
          {running || queuedRun || report?.status === "Running"
            ? "Đang chạy benchmark…"
            : needsPreliminaryRun
              ? "Chạy thử benchmark (không tính điểm)"
              : "Chạy đánh giá hiệu năng"}
        </button>
        <button
          className="secondary-button"
          type="button"
          onClick={() => void loadReport()}
          disabled={loading}
        >
          {loading ? "Đang tải…" : "Làm mới báo cáo"}
        </button>
      </div>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {report?.status === "Pending" &&
        report.pending_verification_questions.length > 0 && (
          <div className="notice notice-warning" role="status">
            <strong>Đánh giá đã chạy nhưng chưa thể chấm điểm.</strong>{" "}
            {report.pending_verification_questions.length} câu hỏi benchmark
            chưa được chuyên viên pháp chế xác minh. Chấp nhận tài liệu chỉ kích
            hoạt phiên bản tài liệu, không xác minh câu hỏi benchmark. Hãy bổ
            sung đáp án chuẩn, từ khóa, điều khoản và mã đoạn nguồn đã duyệt cho
            các câu hỏi đang chờ bên dưới rồi chạy lại.
          </div>
        )}
      {report?.status === "Running" &&
        report.preliminary_metrics && (
          <div className="notice notice-info" role="status">
            Đang chạy thử {report.preliminary_metrics.questions_completed}/
            {report.preliminary_metrics.questions_attempted} câu hỏi. Đây là
            lượt chạy sơ bộ, không tạo điểm chính thức.
          </div>
        )}
      {report?.status === "Preliminary" && report.preliminary_metrics && (
        <>
          <div className="notice notice-warning" role="status">
            Đã chạy thử {report.preliminary_metrics.questions_completed}/
            {report.preliminary_metrics.questions_attempted} câu. Đây là chỉ số
            truy xuất sơ bộ, không phải điểm chính xác/trung thành/trích dẫn
            chính thức.
          </div>
          <div className="evaluation-grid">
            <article className="metric-card">
              <span className="metric-value">
                {report.preliminary_metrics.retrieval_coverage == null
                  ? "Chưa có dữ liệu"
                  : `${(
                      report.preliminary_metrics.retrieval_coverage * 100
                    ).toFixed(1)}%`}
              </span>
              <h3>Truy xuất đạt ngưỡng</h3>
              <p>
                {report.preliminary_metrics.qualified_retrievals}/
                {report.preliminary_metrics.questions_completed} câu có bằng
                chứng qua ngưỡng truy xuất.
              </p>
            </article>
            <article className="metric-card">
              <span className="metric-value">
                {report.preliminary_metrics.generated_answers}
              </span>
              <h3>Câu trả lời được tạo</h3>
            </article>
            <article className="metric-card">
              <span className="metric-value">
                {report.preliminary_metrics.refusals}
              </span>
              <h3>Lượt từ chối</h3>
            </article>
            <article className="metric-card">
              <span className="metric-value">
                {report.preliminary_metrics.failed_questions}
              </span>
              <h3>Lượt lỗi</h3>
            </article>
          </div>
          {report.question_results && report.question_results.length > 0 && (
            <details className="notice notice-info">
              <summary>Xem kết quả chạy thử từng câu</summary>
              <ol>
                {report.question_results.map((result) => (
                  <li key={result.id}>
                    <strong>{result.id}</strong>: {result.question}
                    {result.retrieval && (
                      <p className="field-hint">
                        Truy xuất:{" "}
                        {result.retrieval.qualified
                          ? "đạt ngưỡng"
                          : "không đạt ngưỡng"}
                        {" · "}điểm gần nhất:{" "}
                        {(result.retrieval.best_score * 100).toFixed(1)}%
                        {" · "}trạng thái: {result.status}
                      </p>
                    )}
                    {result.generated_answer && (
                      <p>{result.generated_answer}</p>
                    )}
                    {result.retrieved_sources &&
                      result.retrieved_sources.length > 0 && (
                        <ul>
                          {result.retrieved_sources.map((source, index) => (
                            <li
                              key={`${result.id}-${source.ma_doan ?? index}`}
                            >
                              <code>{source.ma_doan || "Nguồn"}</code>
                              {source.ten_tai_lieu
                                ? ` · ${source.ten_tai_lieu}`
                                : ""}
                              {source.dieu_khoan
                                ? ` · ${source.dieu_khoan}`
                                : ""}
                            </li>
                          ))}
                        </ul>
                      )}
                    {result.error && (
                      <p className="notice notice-error">{result.error}</p>
                    )}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      )}
      {report?.metrics && (
        <div className="evaluation-grid">
          {metrics.map((metric) => (
            <article key={metric.key} className="metric-card">
              <span className="metric-value">
                {report.official
                  ? formatScore(report.metrics?.[metric.key])
                  : "Chưa có dữ liệu"}
              </span>
              <h3>{metric.name}</h3>
            </article>
          ))}
        </div>
      )}
      {report && (
        <>
          <p className="muted" role="status">
            Bộ dữ liệu: {report.dataset_question_count} câu hỏi; đã xác minh:{" "}
            {report.verified_question_count}; được chấm:{" "}
            {report.metrics?.scored_questions ?? 0}. Phiên bản tài liệu:{" "}
            <code>{report.document_version_id}</code>
          </p>
          {report.pending_verification_questions.length > 0 && (
            <details className="notice notice-info">
              <summary>
                Câu hỏi đang chờ xác minh (
                {report.pending_verification_questions.length})
              </summary>
              <ul>
                {report.pending_verification_questions.map((question) => (
                  <li key={question.id}>
                    <strong>{question.id}</strong>: {question.question}
                    <p className="field-hint">
                      {preliminaryMatchLabel(
                        question.preliminary_match_status,
                      )}
                      {" — "}
                      {question.preliminary_note || question.reason}
                    </p>
                    {question.candidate_sources &&
                      question.candidate_sources.length > 0 && (
                        <ul>
                          {question.candidate_sources.map((source) => (
                            <li
                              key={`${question.id}-${source.ma_doan_candidate}`}
                            >
                              Nguồn gợi ý (chưa xác minh):{" "}
                              <code>{source.ma_doan_candidate}</code>
                              {source.article_title_candidate
                                ? ` · ${source.article_title_candidate}`
                                : source.article_candidate
                                  ? ` · ${source.article_candidate}`
                                  : ""}
                              {source.document_id && source.version
                                ? ` · ${source.document_id} ${source.version}`
                                : ""}
                              {source.ma_phien_ban
                                ? ` · ${source.ma_phien_ban}`
                                : ""}
                            </li>
                          ))}
                        </ul>
                      )}
                    {question.missing_reference_fields &&
                      question.missing_reference_fields.length > 0 && (
                        <p className="field-hint">
                          Còn thiếu:{" "}
                          {question.missing_reference_fields.join(", ")}
                        </p>
                      )}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {report.errors.map((reportError) => (
            <div className="notice notice-warning" key={reportError}>
              {reportError}
            </div>
          ))}
        </>
      )}
    </section>
  );
}