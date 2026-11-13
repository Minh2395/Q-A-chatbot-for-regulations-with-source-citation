USE Db_QuyChe_Business;
GO

-- View 1: Lọc các đoạn văn bản thuộc phiên bản tài liệu đang có hiệu lực
CREATE OR ALTER VIEW v_ActiveDoanVanBan AS
SELECT
    d.MaDoan,
    d.NoiDung,
    d.DieuKhoan,
    d.SoTrang,
    p.MaPhienBan,
    p.SoPhienBan,
    t.TieuDe AS TenTaiLieu,
    t.LinhVuc
FROM DOAN_VAN_BAN d
INNER JOIN PHIEN_BAN_TAI_LIEU p
    ON d.MaPhienBan = p.MaPhienBan
INNER JOIN TAI_LIEU t
    ON p.MaTaiLieu = t.MaTaiLieu
WHERE p.is_active = 1
    AND p.TrangThai = 'Approved';

GO

-- View 2: Tổng hợp câu hỏi, câu trả lời và thông tin trích dẫn
CREATE OR ALTER VIEW v_ChiTietCauTraLoiAndTrichDan AS
SELECT
    q.MaCauHoi,
    q.NoiDung AS NoiDungCauHoi,
    a.MaCauTraLoi,
    a.NoiDung AS NoiDungTraLoi,
    a.TrangThai,
    a.DoTinCay,
    a.LyDoTuChoi,
    a.TraceId,
    td.MaTrichDan,
    td.ThuTu AS ThuTuTrichDan,
    td.DoanTrich,
    d.MaDoan,
    d.DieuKhoan AS DieuKhoanGoc,
    d.SoTrang AS SoTrangGoc,
    t.TieuDe AS TenTaiLieuGoc
FROM CAU_HOI q
INNER JOIN CAU_TRA_LOI a
    ON q.MaCauHoi = a.MaCauHoi
LEFT JOIN TRICH_DAN td
    ON a.MaCauTraLoi = td.MaCauTraLoi
LEFT JOIN DOAN_VAN_BAN d
    ON td.MaDoan = d.MaDoan
LEFT JOIN PHIEN_BAN_TAI_LIEU p
    ON d.MaPhienBan = p.MaPhienBan
LEFT JOIN TAI_LIEU t
    ON p.MaTaiLieu = t.MaTaiLieu;

GO