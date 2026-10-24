import React, { useState } from "react";
import type { FormEvent } from "react";

import { sendChatQuery } from "../../services/api";
import { CitationCard } from "./CitationCard";

interface Citation {
  ten_tai_lieu: string;
  dieu_khoan: string;
  so_trang: number;
  noi_dung_trich: string;
}

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

interface ChatResponse {
  noi_dung_tra_loi: string;
  trang_thai: string;
  do_tin_cay: number;
  trace_id: string;
  ly_do_tu_choi?: string | null;
  trich_dan?: Citation[];
}

export const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const handleSend = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!input.trim() || loading) return;

    const question = input;

    const userMsg: ChatMessage = {
      role: "user",
      content: question,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      // Gọi API RAG Query tới FastAPI (ma_phien & ma_nd cố định cho phiên demo)
      const data: ChatResponse = await sendChatQuery(
        "SESSION_DEMO_01",
        "USER_DEMO_01",
        question,
      );

      const botMsg: ChatMessage = {
        role: "assistant",
        content: data.noi_dung_tra_loi,
        status: data.trang_thai,
        confidence: data.do_tin_cay,
        traceId: data.trace_id,
        rejectionReason: data.ly_do_tu_choi ?? undefined,
        citations: data.trich_dan || [],
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "⚠️ Đã xảy ra lỗi kết nối tới máy chủ FastAPI Backend.",
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[650px] bg-white rounded-lg shadow-md border border-slate-200">
      {/* Header Khung Chat */}
      <div className="bg-slate-800 text-white p-4 rounded-t-lg flex justify-between items-center">
        <div>
          <h2 className="font-bold text-lg">
            AIK-01 — Trợ lý Hỏi đáp Quy chế Đất đai
          </h2>

          <p className="text-xs text-slate-300">
            RAG On-Premise | Cổng kiểm soát bằng chứng minh bạch
          </p>
        </div>

        <span className="bg-emerald-500 text-xs px-2.5 py-1 rounded-full font-medium">
          Online
        </span>
      </div>

      {/* Danh sách tin nhắn */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex flex-col ${
              msg.role === "user" ? "items-end" : "items-start"
            }`}
          >
            <div
              className={`max-w-[80%] p-3.5 rounded-lg text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-none"
                  : msg.status === "TuChoi"
                    ? "bg-amber-50 border border-amber-200 text-amber-900 rounded-bl-none"
                    : msg.isError
                      ? "bg-red-50 border border-red-200 text-red-700 rounded-bl-none"
                      : "bg-white border border-slate-200 text-slate-800 shadow-sm rounded-bl-none"
              }`}
            >
              <p className="whitespace-pre-line leading-relaxed">
                {msg.content}
              </p>

              {/* Cảnh báo khi Cổng Bằng Chứng từ chối trả lời */}
              {msg.status === "TuChoi" && (
                <div className="mt-2 text-xs text-amber-700 bg-amber-100 p-2 rounded">
                  ⚠️ <strong>Cổng Bằng Chứng kích hoạt:</strong>{" "}
                  {msg.rejectionReason}
                </div>
              )}

              {/* Danh sách Thẻ Trích Dẫn nếu trả lời thành công */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 border-t border-slate-200 pt-2">
                  <p className="text-xs font-bold text-slate-600 mb-1">
                    📚 Căn cứ trích dẫn:
                  </p>

                  {msg.citations.map((cite, cIdx) => (
                    <CitationCard key={cIdx} citation={cite} />
                  ))}
                </div>
              )}

              {/* Badge Mã Kiểm Toán TraceId */}
              {msg.traceId && (
                <div className="mt-2 text-[10px] text-slate-400 text-right font-mono">
                  TraceId: {msg.traceId} | Độ tin cậy:{" "}
                  {((msg.confidence ?? 0) * 100).toFixed(1)}%
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center space-x-2 text-slate-500 text-sm italic">
            <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>

            <span>AI đang tra cứu CSDL Vector & lọc cờ hiệu lực...</span>
          </div>
        )}
      </div>

      {/* Input gửi câu hỏi */}
      <form
        onSubmit={handleSend}
        className="p-3 border-t border-slate-200 bg-white flex space-x-2 rounded-b-lg"
      >
        <input
          type="text"
          value={input}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setInput(e.target.value)
          }
          placeholder="Đặt câu hỏi về đền bù, quy hoạch đất đai & nhà ở TP..."
          disabled={loading}
          className="flex-1 border border-slate-300 rounded-md px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-md font-medium text-sm transition-colors disabled:opacity-50"
        >
          {loading ? "Đang gửi..." : "Gửi"}
        </button>
      </form>
    </div>
  );
};
