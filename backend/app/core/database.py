import pyodbc
from app.core.config import settings

def get_business_db_connection():
    conn_str = (
        f"DRIVER={{{settings.DB_DRIVER}}};"
        f"SERVER={settings.DB_SERVER};"
        f"DATABASE={settings.DB_BUSINESS};"
        f"UID={settings.DB_USER};"
        f"PWD={settings.DB_PASSWORD};"
    )
    return pyodbc.connect(conn_str)

def get_vector_db_connection():
    conn_str = (
        f"DRIVER={{{settings.DB_DRIVER}}};"
        f"SERVER={settings.DB_SERVER};"
        f"DATABASE={settings.DB_VECTOR};" 
        f"UID={settings.DB_USER};" 
        f"PWD={settings.DB_PASSWORD};"
    )
    return pyodbc.connect(conn_str)