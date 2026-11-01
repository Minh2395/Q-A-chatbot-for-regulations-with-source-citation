import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.api.v1 import documents
from app.core.security import AuthenticatedUser


SPECIALIST = AuthenticatedUser(
    ma_nd="SPECIALIST_1",
    vai_tro="ChuyenVienPhapChe",
)


class FakeCursor:
    def __init__(self, rows=(), one=None):
        self.rows = rows
        self.one = one
        self.statements = []

    def execute(self, query, *params):
        self.statements.append((query, params))
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_list_document_catalog_maps_existing_sql_columns(monkeypatch):
    cursor = FakeCursor(
        rows=[
            ("DOC1", "Legal document", "PDF", "Civil", None),
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        documents,
        "get_business_db_connection",
        lambda: connection,
    )

    result = documents.list_document_catalog(SPECIALIST)

    assert result[0].model_dump() == {
        "ma_tai_lieu": "DOC1",
        "tieu_de": "Legal document",
        "loai_van_ban": "PDF",
        "linh_vuc": "Civil",
        "co_quan_ban_hanh": None,
    }
    assert "FROM dbo.TAI_LIEU" in cursor.statements[0][0]
    assert connection.closed


def test_create_document_catalog_uses_existing_table_and_audits(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    audit_entries = []
    monkeypatch.setattr(
        documents,
        "get_business_db_connection",
        lambda: connection,
    )
    monkeypatch.setattr(
        documents,
        "write_audit_log",
        lambda **entry: audit_entries.append(entry),
    )

    result = documents.create_document_catalog_item(
        documents.DocumentCatalogCreate(
            tieu_de="  New law  ",
            loai_van_ban=" pdf ",
            linh_vuc=" Civil ",
            co_quan_ban_hanh=" Issuer ",
        ),
        SPECIALIST,
    )

    query, params = cursor.statements[0]
    assert "INSERT INTO dbo.TAI_LIEU" in query
    assert len(params) == 5
    assert params[1:] == ("New law", "PDF", "Civil", "Issuer")
    assert len(result.ma_tai_lieu) == 20
    assert connection.committed
    assert connection.closed
    assert audit_entries[0]["event"] == "DOCUMENT_CATALOG_CREATED"


def test_list_document_versions_returns_existing_version_metadata(monkeypatch):
    cursor = FakeCursor(
        rows=[
            (
                "PB1",
                "DOC1",
                "Legal document",
                "UPLOADER",
                "uploader",
                "v1",
                "Draft",
                0,
                "law.pdf",
                None,
            ),
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        documents,
        "get_business_db_connection",
        lambda: connection,
    )

    result = documents.list_document_versions("Draft", SPECIALIST)

    assert result[0].ma_phien_ban == "PB1"
    assert result[0].ma_nguoi_tai == "UPLOADER"
    assert result[0].trang_thai == "Draft"
    assert result[0].is_active is False
    assert "dbo.PHIEN_BAN_TAI_LIEU" in cursor.statements[0][0]
    assert cursor.statements[0][1] == ("Draft",)


def test_get_version_chunks_returns_reviewable_extracted_text(monkeypatch):
    cursor = FakeCursor(
        rows=[("D1", 1, "Article 1", "Legal text", 2)],
        one=("1",),
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        documents,
        "get_business_db_connection",
        lambda: connection,
    )

    result = documents.get_document_version_chunks("PB1", SPECIALIST)

    assert result[0].ma_doan == "D1"
    assert result[0].noi_dung == "Legal text"
    assert len(cursor.statements) == 2
    assert "dbo.DOAN_VAN_BAN" in cursor.statements[1][0]


def test_missing_document_is_rejected_before_chunking(monkeypatch):
    cursor = FakeCursor(one=None)
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        documents,
        "get_business_db_connection",
        lambda: connection,
    )
    monkeypatch.setattr(
        documents,
        "extract_chunks_from_pdf",
        lambda _content: pytest.fail("No extraction expected."),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            documents.upload_document(
                UploadFile(filename="law.pdf", file=BytesIO(b"pdf")),
                "MISSING",
                "v1",
                SPECIALIST.ma_nd,
                SPECIALIST,
            )
        )

    assert error.value.status_code == 404
    assert connection.closed


def test_upload_creates_draft_and_persists_extracted_chunks(monkeypatch):
    validation_cursor = FakeCursor(one=("1",))
    persistence_cursor = FakeCursor()
    validation_connection = FakeConnection(validation_cursor)
    persistence_connection = FakeConnection(persistence_cursor)
    connection_iterator = iter([validation_connection, persistence_connection])
    monkeypatch.setattr(
        documents,
        "get_business_db_connection",
        lambda: next(connection_iterator),
    )
    monkeypatch.setattr(
        documents,
        "extract_chunks_from_pdf",
        lambda _content: [
            {
                "thu_tu": 1,
                "dieu_khoan": "Article 1",
                "noi_dung": "Verified source text",
                "so_trang": 1,
            }
        ],
    )
    monkeypatch.setattr(documents, "write_audit_log", lambda **_entry: None)

    async def embedding(_text):
        return b"vector"

    monkeypatch.setattr(documents, "generate_vector_embedding", embedding)

    result = asyncio.run(
        documents.upload_document(
            UploadFile(filename="law.pdf", file=BytesIO(b"pdf")),
            "DOC1",
            "v1",
            SPECIALIST.ma_nd,
            SPECIALIST,
        )
    )

    assert result["trang_thai"] == "Draft"
    assert result["so_doan"] == 1
    assert any(
        "INSERT INTO PHIEN_BAN_TAI_LIEU" in query
        for query, _params in persistence_cursor.statements
    )
    assert any(
        "sp_InsertChunkAndVector" in query
        for query, _params in persistence_cursor.statements
    )
    assert persistence_connection.committed
    assert persistence_connection.closed
    assert validation_connection.closed
