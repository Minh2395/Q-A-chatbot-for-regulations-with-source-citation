import { useEffect, useState } from "react";
import "./App.css";

type HealthResponse = {
  status: string;
  service: string;
};

function App() {
  const [backendStatus, setBackendStatus] = useState("Đang kiểm tra...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Backend trả về lỗi");
        }
        return response.json() as Promise<HealthResponse>;
      })
      .then((data) => {
        setBackendStatus(
          data.status === "ok" ? "Đã kết nối Backend" : "Backend chưa sẵn sàng",
        );
      })
      .catch(() => {
        setBackendStatus("Không thể kết nối Backend");
      });
  }, []);

  return (
    <main className="app">
      <header className="header">
        <h1>Trợ lý quy chế nhà ở và đất đai</h1>
        <p>Hỏi đáp dựa trên văn bản được duyệt, có trích dẫn nguồn.</p>
      </header>

      <section className="status-card">
        <h2>Trạng thái hệ thống</h2>
        <p>{backendStatus}</p>
      </section>

      <section className="chat-card">
        <h2>Hỏi đáp quy chế</h2>
        <p>Giao diện hỏi đáp sẽ được phát triển ở bước tiếp theo.</p>
      </section>
    </main>
  );
}

export default App;
