USE Db_QuyChe_Business;
GO

-- Trigger 1: Tự động vô hiệu hóa phiên bản cũ
-- khi một phiên bản mới được duyệt và kích hoạt
CREATE OR ALTER TRIGGER trg_AutoDeactivateOldVersions
ON PHIEN_BAN_TAI_LIEU
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- Xác định phiên bản hợp lệ cần được giữ hiệu lực
    ;WITH ActiveVersions AS (
        SELECT
            i.MaPhienBan,
            i.MaTaiLieu,
            ROW_NUMBER() OVER (
                PARTITION BY i.MaTaiLieu
                ORDER BY
                    i.NgayHieuLuc DESC,
                    i.MaPhienBan DESC
            ) AS RowNum
        FROM inserted i
        WHERE i.is_active = 1
            AND i.TrangThai = 'Approved'
    ),
    SelectedVersions AS (
        SELECT MaPhienBan, MaTaiLieu
        FROM ActiveVersions
        WHERE RowNum = 1
    )
    UPDATE p
    SET
        p.is_active = 0,
        p.TrangThai = 'Expired',
        p.NgayHetHieuLuc = GETDATE()
    FROM PHIEN_BAN_TAI_LIEU p
    INNER JOIN SelectedVersions s
        ON p.MaTaiLieu = s.MaTaiLieu
    WHERE p.MaPhienBan <> s.MaPhienBan
        AND p.is_active = 1;

END;
GO


-- Trigger 2: Đồng bộ xóa embedding khi xóa đoạn văn bản
-- giữa Db_QuyChe_Business và Db_QuyChe_Vector
CREATE OR ALTER TRIGGER trg_CascadeDeleteVector
ON DOAN_VAN_BAN
AFTER DELETE
AS
BEGIN
    SET NOCOUNT ON;

    DELETE v
    FROM Db_QuyChe_Vector.dbo.BANG_VECTOR_EMBEDDING AS v
    INNER JOIN deleted AS d
        ON v.MaDoan = d.MaDoan;

END;
GO