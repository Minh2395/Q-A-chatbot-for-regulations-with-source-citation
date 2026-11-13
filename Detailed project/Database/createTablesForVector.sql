USE Db_QuyChe_Vector;
GO

CREATE TABLE BANG_VECTOR_EMBEDDING (
    MaDoan VARCHAR(20) PRIMARY KEY,
    VectorData VARBINARY(MAX) NOT NULL, -- Dãy số nhị phân mã hóa Vector
    IndexMetadata NVARCHAR(MAX), -- Chỉ mục bổ trợ
);

GO