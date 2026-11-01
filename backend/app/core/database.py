import pyodbc
from app.core.config import settings


def get_connection(database: str):
    server = settings.DB_SERVER.strip().replace("\\\\", "\\")

    parts = [
        f"DRIVER={{{settings.DB_DRIVER}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        f"Encrypt={settings.DB_ENCRYPT}",
        f"TrustServerCertificate={settings.DB_TRUST_SERVER_CERTIFICATE}",
    ]

    if settings.DB_WINDOWS_AUTH:
        parts.append("Trusted_Connection=yes")
    else:
        if not settings.DB_USER or not settings.DB_PASSWORD:
            raise ValueError(
                "Thiếu DB_USER hoặc DB_PASSWORD trong cấu hình."
            )

        parts.append(f"UID={_escape_odbc_value(settings.DB_USER)}")
        parts.append(f"PWD={_escape_odbc_value(settings.DB_PASSWORD)}")

    return pyodbc.connect(";".join(parts) + ";", timeout=15)


def _escape_odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def get_business_db_connection():
    return get_connection(settings.DB_BUSINESS)


def get_vector_db_connection():
    return get_connection(settings.DB_VECTOR)
