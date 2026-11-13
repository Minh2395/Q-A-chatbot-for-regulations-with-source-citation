USE Db_QuyChe_Business;
GO

-- Store 1: Nạp đồng thời nội dung đoạn văn bản vào Db_Business
-- và vector embedding vào Db_Vector
CREATE OR ALTER PROCEDURE sp_InsertChunkAndVector
    @MaDoan VARCHAR(20),
    @MaPhienBan VARCHAR(20),
    @ThuTu INT,
    @DieuKhoan NVARCHAR(100),
    @NoiDung NVARCHAR(MAX),
    @SoTrang INT,
    @VectorData VARBINARY(MAX),
    @IndexMetadata NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Ghi nội dung vào database nghiệp vụ
        INSERT INTO dbo.DOAN_VAN_BAN (
            MaDoan,
            MaPhienBan,
            ThuTu,
            DieuKhoan,
            NoiDung,
            SoTrang
        )
        VALUES (
            @MaDoan,
            @MaPhienBan,
            @ThuTu,
            @DieuKhoan,
            @NoiDung,
            @SoTrang
        );

        -- Ghi vector embedding vào database vector
        INSERT INTO Db_QuyChe_Vector.dbo.BANG_VECTOR_EMBEDDING (
            MaDoan,
            VectorData,
            IndexMetadata
        )
        VALUES (
            @MaDoan,
            @VectorData,
            @IndexMetadata
        );

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRANSACTION;

        THROW;
    END CATCH;
END;
GO


-- Store 2: Nhận danh sách MaDoan từ Vector Search
-- và chỉ trả về các đoạn văn bản đang có hiệu lực
-- Định dạng đầu vào: 'D1,D2,D3'
CREATE OR ALTER PROCEDURE sp_FilterActiveChunksByVectorIds
    @ListMaDoan NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        v.MaDoan,
        v.NoiDung,
        v.DieuKhoan,
        v.SoTrang,
        v.TenTaiLieu,
        v.SoPhienBan
    FROM dbo.v_ActiveDoanVanBan AS v
    INNER JOIN (
        SELECT DISTINCT
            LTRIM(RTRIM(value)) AS MaDoan
        FROM STRING_SPLIT(@ListMaDoan, ',')
        WHERE LTRIM(RTRIM(value)) <> ''
    ) AS s
        ON v.MaDoan = s.MaDoan;
END;
GO


-- Store 3: Lưu câu trả lời, trạng thái xử lý,
-- độ tin cậy, lý do từ chối và TraceId
CREATE OR ALTER PROCEDURE sp_SaveChatResponse
    @MaCauTraLoi VARCHAR(20),
    @MaCauHoi VARCHAR(20),
    @NoiDung NVARCHAR(MAX),
    @TrangThai NVARCHAR(50),
    @DoTinCay FLOAT,
    @LyDoTuChoi NVARCHAR(255),
    @TraceId VARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    INSERT INTO dbo.CAU_TRA_LOI (
        MaCauTraLoi,
        MaCauHoi,
        NoiDung,
        TrangThai,
        DoTinCay,
        LyDoTuChoi,
        TraceId
    )
    VALUES (
        @MaCauTraLoi,
        @MaCauHoi,
        @NoiDung,
        @TrangThai,
        @DoTinCay,
        @LyDoTuChoi,
        @TraceId
    );
END;
GO