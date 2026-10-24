import { useRef, useState } from "react";
import { uploadDocument, approveDocumentVersion } from "../../services/api";

interface UploadResponse {
  message: string;
  ma_phien_ban: string;
  so_phien_ban: string;
  trang_thai: string;
}

interface DocumentUploadProps {
  onSuccess?: () => void;
}

export default function DocumentUpload({ onSuccess }: DocumentUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [maTaiLieu, setMaTaiLieu] = useState("");
  const [soPhienBan, setSoPhienBan] = useState("v1.0");
  const [maNd, setMaNd] = useState("ADMIN_01");

  const [uploading, setUploading] = useState(false);
  const [approving, setApproving] = useState(false);

  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const handleFileChange = (selectedFile?: File) => {
    setFile(selectedFile ?? null);
    setResult(null);
    setError("");
    setSuccessMessage("");
  };

  const handleUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!file) {
      setError("Vui lòng chọn file PDF hoặc Word.");
      return;
    }

    const extension = file.name.split(".").pop()?.toLowerCase();

    if (!["pdf", "doc", "docx"].includes(extension ?? "")) {
      setError("Chỉ hỗ trợ file PDF, DOC hoặc DOCX.");
      return;
    }

    if (!maTaiLieu.trim() || !soPhienBan.trim() || !maNd.trim()) {
      setError("Vui lòng nhập đầy đủ thông tin tài liệu.");
      return;
    }

    setUploading(true);
    setError("");
    setSuccessMessage("");
    setResult(null);

    try {
      const formData = new FormData();

      formData.append("file", file);
      formData.append("ma_tai_lieu", maTaiLieu.trim());
      formData.append("so_phien_ban", soPhienBan.trim());
      formData.append("ma_nd", maNd.trim());

      const data = await uploadDocument(formData);

      setResult(data);
      setSuccessMessage(data.message || "Upload tài liệu thành công.");

      onSuccess?.();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;

      setError(
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((item: any) => item.msg).join(", ")
            : err?.response?.data?.message ||
              err?.message ||
              "Không thể upload tài liệu. Vui lòng thử lại.",
      );
    } finally {
      setUploading(false);
    }
  };

  const handleApprove = async () => {
    if (!result?.ma_phien_ban) {
      setError("Không tìm thấy mã phiên bản cần phê duyệt.");
      return;
    }

    const confirmed = window.confirm(
      `Bạn có chắc muốn phê duyệt phiên bản ${result.ma_phien_ban}?`,
    );

    if (!confirmed) return;

    setApproving(true);
    setError("");
    setSuccessMessage("");

    try {
      const data = await approveDocumentVersion(result.ma_phien_ban);

      setResult((previous) =>
        previous ? { ...previous, trang_thai: "Approved" } : previous,
      );

      setSuccessMessage(data.message || "Phê duyệt tài liệu thành công.");

      onSuccess?.();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;

      setError(
        typeof detail === "string"
          ? detail
          : err?.response?.data?.message ||
              err?.message ||
              "Không thể phê duyệt tài liệu.",
      );
    } finally {
      setApproving(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-3xl rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="mb-6">
        <p className="text-sm font-medium text-amber-700">QUẢN LÝ TRI THỨC</p>

        <h2 className="mt-2 text-2xl font-bold text-gray-900">
          Nạp tài liệu quy chế
        </h2>

        <p className="mt-2 text-sm leading-6 text-gray-500">
          Tải lên văn bản nhà ở và đất đai để đưa vào quy trình xử lý, kiểm tra
          và phê duyệt.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {successMessage && (
        <div
          role="status"
          className="mb-5 rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-700"
        >
          {successMessage}
        </div>
      )}

      <form onSubmit={handleUpload} className="space-y-5">
        <div>
          <label
            htmlFor="document-file"
            className="mb-2 block text-sm font-semibold text-gray-700"
          >
            File văn bản
          </label>

          <input
            ref={fileInputRef}
            id="document-file"
            type="file"
            accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => handleFileChange(event.target.files?.[0])}
            disabled={uploading || approving}
            className="block w-full cursor-pointer rounded-lg border border-gray-300 bg-gray-50 text-sm text-gray-700 file:mr-4 file:border-0 file:bg-gray-100 file:px-4 file:py-3 file:font-medium hover:file:bg-gray-200 disabled:opacity-50"
          />

          <p className="mt-2 text-xs text-gray-500">
            Định dạng hỗ trợ: PDF, DOC, DOCX.
          </p>

          {file && (
            <p className="mt-2 break-all text-sm text-gray-600">
              File đã chọn: {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div>
            <label
              htmlFor="ma-tai-lieu"
              className="mb-2 block text-sm font-semibold text-gray-700"
            >
              Mã tài liệu
            </label>

            <input
              id="ma-tai-lieu"
              value={maTaiLieu}
              onChange={(event) => setMaTaiLieu(event.target.value)}
              placeholder="TL_DATDAI_2026"
              required
              disabled={uploading || approving}
              className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-100 disabled:bg-gray-100"
            />
          </div>

          <div>
            <label
              htmlFor="so-phien-ban"
              className="mb-2 block text-sm font-semibold text-gray-700"
            >
              Số phiên bản
            </label>

            <input
              id="so-phien-ban"
              value={soPhienBan}
              onChange={(event) => setSoPhienBan(event.target.value)}
              placeholder="v1.0"
              required
              disabled={uploading || approving}
              className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-100 disabled:bg-gray-100"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="ma-nguoi-dung"
            className="mb-2 block text-sm font-semibold text-gray-700"
          >
            Mã người nạp
          </label>

          <input
            id="ma-nguoi-dung"
            value={maNd}
            onChange={(event) => setMaNd(event.target.value)}
            placeholder="ADMIN_01"
            required
            disabled={uploading || approving}
            className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-amber-500 focus:ring-2 focus:ring-amber-100 disabled:bg-gray-100"
          />
        </div>

        <button
          type="submit"
          disabled={uploading || approving}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-600 px-5 py-3 font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {uploading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Đang tải lên và xử lý...
            </>
          ) : (
            "Tải lên tài liệu"
          )}
        </button>
      </form>

      {result && (
        <div className="mt-6 rounded-xl border border-gray-200 bg-gray-50 p-5">
          <h3 className="font-semibold text-gray-900">Kết quả xử lý</h3>

          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
              <dt className="text-gray-500">Mã phiên bản</dt>
              <dd className="break-all font-medium text-gray-900">
                {result.ma_phien_ban}
              </dd>
            </div>

            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Phiên bản</dt>
              <dd className="font-medium text-gray-900">
                {result.so_phien_ban}
              </dd>
            </div>

            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Trạng thái</dt>
              <dd
                className={`font-semibold ${
                  result.trang_thai === "Approved"
                    ? "text-green-700"
                    : "text-amber-700"
                }`}
              >
                {result.trang_thai}
              </dd>
            </div>
          </dl>

          {result.trang_thai !== "Approved" && (
            <button
              type="button"
              onClick={handleApprove}
              disabled={uploading || approving}
              className="mt-5 w-full rounded-lg bg-green-600 px-5 py-3 font-semibold text-white transition hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {approving ? "Đang phê duyệt..." : "Phê duyệt phiên bản"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
