import React, { useState } from "react";
import { ChatWindow } from "./components/chat/ChatWindow";

type TabType = "chat" | "docs";

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>("chat");

  return (
    <div className="min-h-screen bg-slate-100 p-6 font-sans">
      <div className="max-w-4xl mx-auto space-y-4">
        {/* Thanh Điều Hướng Chức Năng */}
        <div className="flex space-x-2 bg-white p-2 rounded-lg shadow-sm border border-slate-200">
          <button
            onClick={() => setActiveTab("chat")}
            className={`px-4 py-2 rounded-md font-medium text-sm transition-colors ${
              activeTab === "chat"
                ? "bg-blue-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            💬 Hỏi đáp AI
          </button>

          <button
            onClick={() => setActiveTab("docs")}
            className={`px-4 py-2 rounded-md font-medium text-sm transition-colors ${
              activeTab === "docs"
                ? "bg-blue-600 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            📁 Cổng Pháp chế (Upload & Duyệt quy chế)
          </button>
        </div>

        {/* Nội dung Màn hình chính */}
        {activeTab === "chat" ? (
          <ChatWindow />
        ) : (
          <div className="bg-white p-6 rounded-lg shadow border border-slate-200 text-slate-700">
            <h3 className="font-bold text-lg mb-2">Phân hệ Cổng Pháp chế</h3>

            <p className="text-sm text-slate-500">
              Chức năng dành cho Chuyên viên upload file PDF/Word quy chế mới và
              bấm duyệt để kích hoạt cờ{" "}
              <code className="bg-slate-100 px-1 py-0.5 rounded text-blue-600 font-mono">
                is_active = 1
              </code>
              .
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
