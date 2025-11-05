"""Unified Azure SQL access helpers for the DC Lab workspace.

This module standardises how the project authenticates to Azure SQL using
`pyodbc`, ensures the Homebrew ODBC driver is discovered on macOS, and
exposes convenience helpers that mirror the tables documented in
`Database_Scheme.md` (Banking_Comments, Banking_Drivers, BankingMetrics).
"""

from __future__ import annotations

import logging
import os
import platform
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

import pandas as pd
import pyodbc
from dotenv import load_dotenv

try:  # Streamlit is optional
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - streamlit unavailable locally
    st = None


LOGGER = logging.getLogger(__name__)

# Ensure unixODBC looks in Homebrew's configuration directory on macOS.
os.environ.setdefault("ODBCSYSINI", "/opt/homebrew/etc")
os.environ.setdefault("ODBCINI", "/opt/homebrew/etc/odbc.ini")

# Eagerly load environment variables so downstream imports have access.
PROJECT_ROOT = Path(__file__).resolve().parent
ROOT_DOTENV = PROJECT_ROOT / ".env"
if ROOT_DOTENV.exists():
    load_dotenv(ROOT_DOTENV)
else:
    load_dotenv()


# Environment variables and secrets that may hold the Azure SQL connection string.
TARGET_CONNECTION_KEYS: Sequence[str] = (
    "AZURE_SQL_ODBC",
    "AZURE_SQL_CONNECTION_STRING",
    "TARGET_DB_CONNECTION_STRING",
    "DC_DB_STRING_MASTER",
    "DB_AILAB_CONN",
)

SOURCE_CONNECTION_KEYS: Sequence[str] = (
    "SOURCE_DB_CONNECTION_STRING",
    "LEGACY_DB_CONNECTION_STRING",
)

DRIVER_LIBRARY_CANDIDATES: Sequence[Path] = (
    Path("/opt/homebrew/lib/libmsodbcsql.17.dylib"),
    Path("/usr/local/lib/libmsodbcsql.17.dylib"),
    Path("/opt/homebrew/lib/libmsodbcsql.18.dylib"),
    Path("/usr/local/lib/libmsodbcsql.18.dylib"),
)


def _get_secret_value(key: str) -> Optional[str]:
    if st is None:
        return None

    try:
        secrets_obj = getattr(st, "secrets", None)
        if secrets_obj is None:
            return None
        if hasattr(secrets_obj, "get"):
            value = secrets_obj.get(key)
        else:
            value = secrets_obj[key]
    except Exception:  # pragma: no cover - Streamlit secrets access can fail silently
        return None

    if isinstance(value, str) and value.strip():
        return value
    return None


def normalize_connection_string(raw: str) -> str:
    """Collapse whitespace and quote characters into a clean ODBC string."""

    cleaned = raw.strip().strip('"').strip("'")
    if not cleaned:
        return cleaned

    # Remove newline breaks while preserving delimiters.
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    cleaned = "".join(lines)

    # Normalise spacing and case for driver tokens.
    cleaned = cleaned.replace("; ", ";")
    cleaned = cleaned.replace("Driver=", "DRIVER=")
    cleaned = cleaned.replace("driver=", "DRIVER=")

    # Ensure we have a trailing semicolon so pyodbc treats it as DSN-less.
    if not cleaned.endswith(";"):
        cleaned += ";"

    return cleaned


def _extract_driver_token(conn_str: str) -> Optional[str]:
    for segment in conn_str.split(";"):
        if not segment.strip():
            continue
        key, _, value = segment.partition("=")
        if key.strip().upper() == "DRIVER" and value:
            return value.strip()
    return None
def _ensure_driver_available(conn_str: str) -> None:
    token = _extract_driver_token(conn_str)
    if not token:
        return

    # Token is a named driver: {ODBC Driver X for SQL Server}
    if token.startswith("{") and token.endswith("}"):
        driver_name = token.strip("{}")
        installed = {driver.lower() for driver in pyodbc.drivers()}
        if driver_name.lower() in installed:
            return

        raise RuntimeError(
            "ODBC driver '{driver}' not found. Install the Microsoft ODBC driver "
            "for SQL Server (msodbcsql17) and unixODBC libraries. "
            "See https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-"
            "microsoft-odbc-driver-17-sql-server for installation instructions."
            .format(driver=driver_name)
        )

    # Token is an explicit filesystem path to a driver library
    elif any(token.startswith(prefix) for prefix in ("/", "~")):
        driver_path = Path(token).expanduser()
        if driver_path.exists():
            return

        raise RuntimeError(
            f"ODBC driver library not found at '{driver_path}'. Verify the SQL Server "
            "driver installation on the host and update the connection string."
        )


def _ensure_driver_path(conn_str: str) -> str:
    """Replace the logical driver name with the actual dylib path on macOS."""

    if platform.system() != "Darwin":
        return conn_str

    for marker in ("{ODBC Driver 17 for SQL Server}", "{ODBC Driver 18 for SQL Server}"):
        if marker not in conn_str:
            continue

        for candidate in DRIVER_LIBRARY_CANDIDATES:
            if candidate.exists():
                LOGGER.debug("Using explicit driver library: %s", candidate)
                return conn_str.replace(f"DRIVER={marker}", f"DRIVER={candidate}")

        LOGGER.warning(
            "ODBC driver dylib not found for marker %s; leaving logical name in place.",
            marker,
        )
        break
    return conn_str


def _resolve_connection_string(keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        secret_value = _get_secret_value(key)
        if secret_value:
            LOGGER.debug("Resolved connection string via st.secrets[%s]", key)
            return _ensure_driver_path(normalize_connection_string(secret_value))

        env_value = os.getenv(key)
        if env_value:
            LOGGER.debug("Resolved connection string via %s", key)
            return _ensure_driver_path(normalize_connection_string(env_value))
    return None


def _default_connection_string(role: str = "target") -> str:
    keys = TARGET_CONNECTION_KEYS if role == "target" else SOURCE_CONNECTION_KEYS
    conn_str = _resolve_connection_string(keys)
    if conn_str:
        return conn_str

    available = ", ".join(keys)
    raise RuntimeError(
        "Database connection string not configured. Set one of "
        f"[{available}] via Streamlit secrets or environment variables."
    )


def get_sql_connection(
    connection_str: Optional[str] = None,
    *,
    autocommit: bool = False,
) -> pyodbc.Connection:
    normalized = (
        _ensure_driver_path(normalize_connection_string(connection_str))
        if connection_str
        else _default_connection_string("target")
    )
    _ensure_driver_available(normalized)
    return pyodbc.connect(normalized, autocommit=autocommit)


def resolve_connection_string(role: str = "target", *, strict: bool = True) -> str:
    """Return the connection string for the requested role (target/source)."""

    try:
        return _default_connection_string(role)
    except RuntimeError:
        if strict:
            raise
        return ""


def establish_connection(role: str = "target", *, autocommit: bool = False) -> pyodbc.Connection:
    """Create a live pyodbc connection for the requested database role."""

    conn_str = resolve_connection_string(role)
    return get_sql_connection(conn_str, autocommit=autocommit)


@contextmanager
def connection(role: str = "target", *, autocommit: bool = False) -> Iterator[pyodbc.Connection]:
    """Context manager that yields a pyodbc connection and closes it safely."""

    conn = establish_connection(role=role, autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


def _translate_param_markers(sql: str) -> str:
    """Convert legacy %s style parameters to ? for pyodbc."""

    return sql.replace("%s", "?")


def read_sql(sql: str, *, params: Optional[Sequence] = None, role: str = "target") -> pd.DataFrame:
    """Execute a SELECT query and return the results as a DataFrame."""

    translated = _translate_param_markers(sql)
    with connection(role=role) as conn:
        return pd.read_sql(translated, conn, params=params)


def execute(sql: str, params: Optional[Sequence] = None, *, role: str = "target", autocommit: bool = False) -> None:
    """Execute a non-query statement (INSERT/UPDATE/DELETE)."""

    translated = _translate_param_markers(sql)
    with connection(role=role, autocommit=autocommit) as conn:
        cursor = conn.cursor()
        try:
            if params is not None:
                cursor.execute(translated, params)
            else:
                cursor.execute(translated)
            if not autocommit:
                conn.commit()
        finally:
            cursor.close()


def fetch_table(table: str, *, schema: str = "dbo", role: str = "target") -> pd.DataFrame:
    """Convenience helper to fetch all rows from a table."""

    qualified = f"[{schema}].[{table}]" if schema else table
    return read_sql(f"SELECT * FROM {qualified}", role=role)


def list_tables(*, schema: Optional[str] = None, role: str = "target") -> pd.DataFrame:
    """Return INFORMATION_SCHEMA metadata for available tables."""

    sql = (
        "SELECT TABLE_SCHEMA, TABLE_NAME "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE'"
    )
    params: Optional[List[str]] = None
    if schema:
        sql += " AND TABLE_SCHEMA = ?"
        params = [schema]

    tables = read_sql(sql + " ORDER BY TABLE_SCHEMA, TABLE_NAME", params=params, role=role)
    return tables.reset_index(drop=True)


def load_banking_comments(*, ticker: Optional[str] = None, role: str = "target") -> pd.DataFrame:
    """Load commentary records documented in Database_Scheme.md."""

    sql = "SELECT TICKER, SECTOR, DATE, COMMENT FROM dbo.Banking_Comments"
    params: Optional[List[str]] = None
    if ticker:
        sql += " WHERE TICKER = ?"
        params = [ticker]

    df = read_sql(sql + " ORDER BY DATE DESC", params=params, role=role)
    if not df.empty:
        df['DATE'] = df['DATE'].astype(str)
    return df


def load_banking_drivers(
    *,
    period_type: Optional[str] = None,
    ticker: Optional[str] = None,
    role: str = "target",
) -> pd.DataFrame:
    """Load banking driver metrics with optional filters."""

    sql = "SELECT * FROM dbo.Banking_Drivers"
    clauses: List[str] = []
    params: List[str] = []

    if period_type:
        clauses.append("PERIOD_TYPE = ?")
        params.append(period_type.upper())
    if ticker:
        clauses.append("TICKER = ?")
        params.append(ticker.upper())

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    sql += " ORDER BY DATE DESC, TICKER"
    return read_sql(sql, params=params or None, role=role)


def load_banking_metrics(
    *,
    period_type: Optional[str] = None,
    actual: Optional[bool] = True,
    ticker: Optional[str] = None,
    role: str = "target",
) -> pd.DataFrame:
    """Load rows from dbo.BankingMetrics with helpful filters."""

    sql = "SELECT * FROM dbo.BankingMetrics"
    clauses: List[str] = []
    params: List = []

    if actual is not None:
        clauses.append("ACTUAL = ?")
        params.append(int(bool(actual)))
    if period_type:
        clauses.append("PERIOD_TYPE = ?")
        params.append(period_type.upper())
    if ticker:
        clauses.append("TICKER = ?")
        params.append(ticker.upper())

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    sql += " ORDER BY DATE DESC, TICKER"
    df = read_sql(sql, params=params or None, role=role)

    if not df.empty and 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE'], errors='coerce')

    return df


__all__ = [
    "normalize_connection_string",
    "get_sql_connection",
    "resolve_connection_string",
    "establish_connection",
    "connection",
    "read_sql",
    "execute",
    "fetch_table",
    "list_tables",
    "load_banking_comments",
    "load_banking_drivers",
    "load_banking_metrics",
]


if __name__ == "__main__":
    comments = load_banking_comments()
    print(f"Banking_Comments rows: {len(comments)}")

    drivers = load_banking_drivers(period_type="Q")
    print(f"Banking_Drivers rows (Q): {len(drivers)}")

    metrics = load_banking_metrics(period_type="Q")
    print(f"BankingMetrics rows (actual, Q): {len(metrics)}")
