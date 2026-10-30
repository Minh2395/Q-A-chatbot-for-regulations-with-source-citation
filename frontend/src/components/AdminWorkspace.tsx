const evaluationCriteria = [
  {
    name: "Độ chính xác",
    description:
      "Tỷ lệ câu trả lời đúng trên bộ câu hỏi có đáp án chuẩn được chuyên viên xác nhận.",
    value: "Chưa có dữ liệu",
  },
  {
    name: "Tính trung thành",
    description:
      "Mức độ câu trả lời được hỗ trợ bởi các đoạn bằng chứng đã truy xuất, không thêm nội dung ngoài nguồn.",
    value: "Chưa có dữ liệu",
  },
  {
    name: "Độ chính xác trích dẫn",
    description:
      "Tỷ lệ trích dẫn đúng tài liệu, điều khoản và đoạn nội dung thực sự hỗ trợ câu trả lời.",
    value: "Chưa có dữ liệu",
  },
];

export function AdminWorkspace() {
  return (
    <div className="admin-workspace">
      <div className="notice notice-warning">
        Chức năng quản trị dưới đây cần API backend tương ứng. Hiện tại
        <code> main.py</code> chỉ đăng ký chat, tài liệu và lịch sử; không có API
        tài khoản, nhật ký hệ thống hoặc đánh giá mô hình. Vì vậy trang không
        hiển thị dữ liệu giả và không cung cấp thao tác CRUD chưa được nối API.
      </div>

      <section className="surface-card admin-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">QUẢN LÝ DANH TÍNH</p>
            <h2>Tài khoản người dùng</h2>
          </div>
          <span className="status-pill status-unavailable">API chưa có</span>
        </div>
        <p className="muted">
          Xem danh sách người dùng, tạo mới, cập nhật hồ sơ và khóa hoặc xóa tài
          khoản cần các endpoint quản lý <code>NGUOI_DUNG</code> và trường{" "}
          <code>VaiTro</code>. Backend hiện chưa công bố các endpoint này.
        </p>
        <div className="capability-list">
          <span>Danh sách tài khoản</span>
          <span>Tạo và chỉnh sửa</span>
          <span>Xóa / khóa tài khoản</span>
          <span>Quản lý vai trò</span>
        </div>
      </section>

      <section className="surface-card admin-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">GIÁM SÁT VẬN HÀNH</p>
            <h2>Nhật ký hệ thống</h2>
          </div>
          <span className="status-pill status-unavailable">API chưa có</span>
        </div>
        <p className="muted">
          Backend chưa có endpoint đọc nhật ký hoạt động. API lịch sử hiện có
          chỉ trả lịch sử hội thoại theo mã người dùng, không phải nhật ký kiểm
          toán toàn hệ thống.
        </p>
      </section>

      <section className="surface-card admin-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">CHẤT LƯỢNG MÔ HÌNH</p>
            <h2>Đánh giá hiệu năng AI</h2>
          </div>
          <span className="status-pill status-unavailable">Chưa thể đo</span>
        </div>
        <p className="muted">
          Backend chưa đăng ký router đánh giá và chưa cung cấp bộ dữ liệu chuẩn.
          Các chỉ số chỉ có thể được tính sau khi có pipeline đánh giá và kết
          quả lưu trữ; độ tin cậy truy xuất không thay thế các chỉ số này.
        </p>
        <div className="evaluation-grid">
          {evaluationCriteria.map((criterion) => (
            <article key={criterion.name} className="metric-card">
              <span className="metric-value">{criterion.value}</span>
              <h3>{criterion.name}</h3>
              <p>{criterion.description}</p>
            </article>
          ))}
        </div>
        <div className="notice notice-info">
          Để bật báo cáo, backend cần API đánh giá có khả năng trả điểm theo từng
          tiêu chí, thời gian chạy, số lượng mẫu, bộ dữ liệu và các trường hợp
          cần rà soát. Không có các dữ liệu này, mọi tỷ lệ hiển thị sẽ gây hiểu
          nhầm.
        </div>
      </section>
    </div>
  );
}
