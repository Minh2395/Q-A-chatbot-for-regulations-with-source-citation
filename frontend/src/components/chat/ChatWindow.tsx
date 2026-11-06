import { useState } from "react";
import type { FormEvent } from "react";
import {
  getApiErrorMessage,
  sendChatQuery,
} from "../../services/api";
import type { Citation, ChatQueryResponse } from "../../services/api";
import { CitationCard } from "./CitationCard";
import { TraceBadge } from "./TraceBadge";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  status?: string;
  confidence?: number;
  traceId?: string;
  rejectionReason?: string;
  citations?: Citation[];
  isError?: boolean;
}

interface ChatWindowProps {
  maNd: string;
  maPhien: string;
}

export function ChatWindow({ maNd, maPhien }: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setMessages((previous) => [
      ...previous,
      { role: "user", content: question },
    ]);
    setInput("");
    setLoading(true);

    try {
      const data: ChatQueryResponse = await sendChatQuery(maPhien, maNd, question);
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: data.noi_dung_tra_loi,
          status: data.trang_thai,
          confidence: data.do_tin_cay,
          traceId: data.trace_id,
          rejectionReason: data.ly_do_tu_choi ?? undefined,
          citations: data.trich_dan ?? [],
        },
      ]);
    } catch (error: unknown) {
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: getApiErrorMessage(
            error,
            "Không thể kết nối tới máy chủ. Vui lòng thử lại.",
          ),
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-card">
      <div className="chat-header">
        <div>
          <div className="chat-title-row">
            <span className="chat-mark" aria-hidden="true">✦</span>
            <h2>Trợ lý Hỏi đáp Quy chế</h2>
          </div>
          <p>Trả lời dựa trên bằng chứng từ tài liệu đã phê duyệt</p>
        </div>
        <span className="info-chip">RAG On-Premise</span>
      </div>

      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="empty-icon" aria-hidden="true">✦</div>
            <h3>Bạn muốn tìm hiểu quy định nào?</h3>
            <p>
              Hãy đặt câu hỏi cụ thể. Câu trả lời sẽ kèm trích dẫn khi có đủ bằng
              chứng đã được phê duyệt.
            </p>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={`${index}-${message.role}`}
            className={`message-row ${message.role === "user" ? "message-user" : "message-assistant"}`}
          >
            <div
              className={`message-bubble ${message.role === "user" ? "bubble-user" : ""} ${message.status === "TuChoi" ? "bubble-refusal" : ""} ${message.isError ? "bubble-error" : ""}`}
            >
              <p>{message.content}</p>

              {message.status === "TuChoi" && message.rejectionReason && (
                <div className="message-callout">
                  Cổng bằng chứng từ chối: {message.rejectionReason}
                </div>
              )}

              {message.citations && message.citations.length > 0 && (
                <div className="citations">
                  <h3>Căn cứ trích dẫn</h3>
                  {message.citations.map((citation, citationIndex) => (
                    <CitationCard
                      key={citation.ma_doan ?? citationIndex}
                      citation={citation}
                    />
                  ))}
                </div>
              )}

              {message.traceId && (
                <TraceBadge
                  traceId={message.traceId}
                  confidence={message.confidence}
                />
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="loading-line" role="status">
            <span className="loading-dot" />
            Đang truy xuất tài liệu và tạo câu trả lời…
          </div>
        )}
      </div>

      <form className="chat-form" onSubmit={handleSend}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ví dụ: Điều kiện cấp giấy chứng nhận quyền sử dụng đất là gì?"
          aria-label="Câu hỏi"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? "Đang gửi…" : "Gửi câu hỏi"}
        </button>
      </form>
      <p className="chat-footnote">
        Câu trả lời có tính tham khảo và phụ thuộc vào tài liệu đã được phê duyệt.
      </p>
    </div>
  );
}
