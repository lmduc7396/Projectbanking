"""Lightweight Azure SQL helpers built around pyodbc.

This module centralises how the Streamlit app locates connection strings and
opens database connections. It prefers Streamlit secrets (so deployments on
Streamlit Cloud just work) but gracefully falls back to environment variables.

Compared with the previous pymssql implementation, pyodbc relies on an ODBC
driver being installed on the host machine. We don't hard-fail if the requested
driver is missing; instead we attempt to reuse any SQL Server driver that pyodbc
can see. If none are present, the eventual connection attempt will raise the
native pyodbc error, which keeps the behaviour close to stock pyodbc.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional, Sequence

import pandas as pd
import pyodbc

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover - streamlit isn't available in local CLI runs
    st = None


LOGGER = logging.getLogger(__name__)

# Streamlit secret / environment keys searched in priority order.
TARGET_DB_KEYS: Sequence[str] = (
    "AZURE_SQL_ODBC",
    "DB_AILAB_CONN",
    "AZURE_SQL_CONNECTION_STRING",
    "TARGET_DB_CONNECTION_STRING",
    "DC_DB_STRING_MASTER",
)

SOURCE_DB_KEYS: Sequence[str] = (
    "SOURCE_DB_CONNECTION_STRING",
    "LEGACY_DB_CONNECTION_STRING",
)

# Separator used in ODBC connection strings.
ODBC_DELIMITER = ";"


def _streamlit_secret(name: str) -> Optional[str]:
    if st is None:
        return None
    try:
        secrets_obj = getattr(st, "secrets", None)
        if secrets_obj is None:
            return None
        # Support dict-like and Mapping-like interfaces.
        if hasattr(secrets_obj, "get"):
            value = secrets_obj.get(name)
        else:
            value = secrets_obj[name]
    except Exception:  # pragma: no cover - runtime secrets errors shouldn't abort
        return None

    if isinstance(value, str) and value.strip():
        return value
    return None


def _normalize_connection_string(raw: str) -> str:
    cleaned = raw.strip().strip('"').strip("'")
    if not cleaned:
        return cleaned

    # Remove stray newlines and duplicated whitespace.
    parts = [line.strip() for line in cleaned.splitlines() if line.strip()]
    cleaned = "".join(parts)

    # Normalise DRIVER casing for easier substitutions later.
    cleaned = cleaned.replace("driver=", "DRIVER=")

    if not cleaned.endswith(ODBC_DELIMITER):
        cleaned += ODBC_DELIMITER
    return cleaned


def _extract_driver_token(conn_str: str) -> Optional[str]:
    for segment in conn_str.split(ODBC_DELIMITER):
        if not segment.strip():
            continue
        key, _, value = segment.partition("=")
        if key.strip().upper() == "DRIVER" and value:
            return value.strip()
    return None


def _detect_sql_server_driver() -> Optional[str]:
    for driver in pyodbc.drivers():
        if "sql server" in driver.lower():
            return driver
    return None


def _coerce_driver(conn_str: str) -> str:
    """Ensure the connection string references an installed SQL Server driver."""

    token = _extract_driver_token(conn_str)
    available = {driver.lower(): driver for driver in pyodbc.drivers()}

    if token and token.startswith("{") and token.endswith("}"):
        requested = token.strip("{}")
        if requested.lower() in available:
            return conn_str

        fallback = _detect_sql_server_driver()
        if fallback:
            LOGGER.warning(
                "Requested ODBC driver '%s' was not found; using '%s' instead.",
                requested,
                fallback,
            )
            return conn_str.replace(f"DRIVER={token}", f"DRIVER={{{fallback}}}")
        return conn_str

    if not token:
        fallback = _detect_sql_server_driver()
        if fallback:
            LOGGER.info(
                "No DRIVER specified in connection string; using '%s'.",
                fallback,
            )
            return f"DRIVER={{{fallback}}};{conn_str}"
    return conn_str


def _resolve_connection_string(*keys: str) -> Optional[str]:
    for key in keys:
        secret_value = _streamlit_secret(key)
        if secret_value:
            LOGGER.debug("Loaded connection string from Streamlit secrets key '%s'.", key)
            return _coerce_driver(_normalize_connection_string(secret_value))

        env_value = os.getenv(key)
        if env_value:
            LOGGER.debug("Loaded connection string from environment variable '%s'.", key)
            return _coerce_driver(_normalize_connection_string(env_value))
    return None


def _default_connection_string(role: str = "target") -> str:
    keys = TARGET_DB_KEYS if role == "target" else SOURCE_DB_KEYS
    conn_str = _resolve_connection_string(*keys)
    if conn_str:
        return conn_str

    available = ", ".join(keys)
    raise RuntimeError(
        f"Database connection string not configured. Expected one of [{available}] "
        "to be defined via Streamlit secrets or environment variables."
    )


def get_sql_connection(
    connection_str: Optional[str] = None,
    *,
    autocommit: bool = False,
) -> pyodbc.Connection:
    """Create a live pyodbc connection."""

    resolved = (
        _coerce_driver(_normalize_connection_string(connection_str))
        if connection_str
        else _default_connection_string("target")
    )
    return pyodbc.connect(resolved, autocommit=autocommit)


def resolve_connection_string(role: str = "target") -> str:
    return _default_connection_string(role)


def establish_connection(role: str = "target", *, autocommit: bool = False) -> pyodbc.Connection:
    conn_str = resolve_connection_string(role)
    return get_sql_connection(conn_str, autocommit=autocommit)


@contextmanager
def connection(role: str = "target", *, autocommit: bool = False) -> Iterator[pyodbc.Connection]:
    conn = establish_connection(role=role, autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


def _translate_param_markers(sql: str) -> str:
    """Convert legacy %s placeholders into pyodbc-style ? markers."""

    return sql.replace("%s", "?")


def read_sql(sql: str, *, params: Optional[Sequence] = None, role: str = "target") -> pd.DataFrame:
    translated = _translate_param_markers(sql)
    with connection(role=role) as conn:
        return pd.read_sql(translated, conn, params=params)


def execute(sql: str, params: Optional[Sequence] = None, *, role: str = "target", autocommit: bool = False) -> None:
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
    qualified = f"[{schema}].[{table}]" if schema else table
    return read_sql(f"SELECT * FROM {qualified}", role=role)


def list_tables(*, schema: Optional[str] = None, role: str = "target") -> pd.DataFrame:
    sql = (
        "SELECT TABLE_SCHEMA, TABLE_NAME "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE'"
    )
    params: Optional[Sequence[str]] = None
    if schema:
        sql += " AND TABLE_SCHEMA = ?"
        params = [schema]

    tables = read_sql(sql + " ORDER BY TABLE_SCHEMA, TABLE_NAME", params=params, role=role)
    return tables.reset_index(drop=True)


__all__ = [
    "connection",
    "establish_connection",
    "execute",
    "fetch_table",
    "get_sql_connection",
    "list_tables",
    "read_sql",
    "resolve_connection_string",
]

