"""Database utilities for reading and writing project data.

All connection strings are read from environment variables to avoid embedding
credentials in source control. The module exposes convenience helpers for
executing read queries and performing batched upserts into SQL Server tables.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyodbc

# Environment variables that should contain fully qualified pyodbc connection strings
SOURCE_DB_ENV = "SOURCE_DB_CONNECTION_STRING"
TARGET_DB_ENV = "TARGET_DB_CONNECTION_STRING"

# Default schema to use when callers pass an unqualified table name
DEFAULT_SCHEMA = "dbo"


def _get_connection_string(db: str) -> str:
    """Return the connection string for the requested database role."""
    env_var = TARGET_DB_ENV if db == "target" else SOURCE_DB_ENV
    conn_str = os.getenv(env_var)
    if not conn_str:
        raise RuntimeError(
            f"Environment variable '{env_var}' is not set. "
            "Please define the connection string before running this action."
        )
    return conn_str


@contextmanager
def get_connection(db: str = "target", autocommit: bool = False) -> Iterable[pyodbc.Connection]:
    """Context manager that yields an open pyodbc connection.

    Args:
        db: "target" for the analytics warehouse, "source" for the legacy
            extraction database.
        autocommit: When True, autocommit is enabled on the connection.
    """
    conn_str = _get_connection_string(db)
    connection = pyodbc.connect(conn_str, autocommit=autocommit)
    try:
        yield connection
    finally:
        connection.close()


def read_sql(query: str, params: Optional[Sequence] = None, db: str = "target") -> pd.DataFrame:
    """Execute a SELECT query and return the results as a DataFrame."""
    with get_connection(db=db) as conn:
        return pd.read_sql(query, conn, params=params)


def execute(query: str, params: Optional[Sequence] = None, db: str = "target") -> None:
    """Execute an arbitrary SQL statement against the selected database."""
    with get_connection(db=db, autocommit=False) as conn:
        cursor = conn.cursor()
        cursor.execute(query) if params is None else cursor.execute(query, params)
        conn.commit()


def _qualify_table(table: str, schema: Optional[str]) -> str:
    if schema:
        return f"[{schema}].[{table}]"
    if "." in table:
        return table
    return f"[{DEFAULT_SCHEMA}].[{table}]"


def _prepare_dataframe(df: pd.DataFrame, columns: Sequence[str]) -> Tuple[List[str], List[Tuple]]:
    """Return column list and row tuples ready for executemany calls."""
    selected = df.loc[:, columns]
    # Replace NaN/NaT with None so pyodbc transmits NULL
    sanitized = selected.replace({np.nan: None})
    sanitized = sanitized.where(pd.notnull(sanitized), None)
    return list(selected.columns), list(map(tuple, sanitized.to_numpy()))


def _executemany(cursor: pyodbc.Cursor, sql: str, rows: List[Tuple]) -> None:
    if not rows:
        return
    cursor.fast_executemany = True
    cursor.executemany(sql, rows)


def _delete_conflicts(
    cursor: pyodbc.Cursor,
    qualified_table: str,
    key_columns: Sequence[str],
    rows: List[Tuple],
) -> None:
    if not key_columns or not rows:
        return

    where_clause = " AND ".join(f"[{col}] = ?" for col in key_columns)
    delete_sql = f"DELETE FROM {qualified_table} WHERE {where_clause}"
    _executemany(cursor, delete_sql, rows)


def _chunk_iterable(items: List[Tuple], chunk_size: int) -> Iterable[List[Tuple]]:
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]


def upsert_dataframe(
    df: pd.DataFrame,
    table: str,
    *,
    key_columns: Sequence[str],
    batch_size: int = 1000,
    schema: Optional[str] = None,
    db: str = "target",
) -> int:
    """Upsert (delete + insert) dataframe rows into the target table.

    Args:
        df: The dataframe whose rows should be written.
        table: Table name without schema (defaults to dbo). Use schema-qualified
            names if desired (e.g., "analytics.FA_Quarterly").
        key_columns: Columns that uniquely identify records. Existing rows with
            matching keys will be removed prior to insert.
        batch_size: Number of rows to process per DELETE/INSERT batch.
        schema: Optional schema override.
        db: "target" or "source" connection selection.

    Returns:
        Number of rows inserted.
    """
    if df.empty:
        return 0

    qualified_table = _qualify_table(table, schema)
    all_columns = list(df.columns)
    insert_columns, prepared_rows = _prepare_dataframe(df, all_columns)

    with get_connection(db=db, autocommit=False) as conn:
        cursor = conn.cursor()
        try:
            for chunk in _chunk_iterable(prepared_rows, batch_size):
                # Build tuple list for matching key columns in this chunk
                if key_columns:
                    key_indices = [insert_columns.index(col) for col in key_columns]
                    key_rows = [[row[idx] for idx in key_indices] for row in chunk]
                    _delete_conflicts(cursor, qualified_table, key_columns, key_rows)

                placeholders = ", ".join("?" for _ in insert_columns)
                column_list = ", ".join(f"[{col}]" for col in insert_columns)
                insert_sql = f"INSERT INTO {qualified_table} ({column_list}) VALUES ({placeholders})"
                _executemany(cursor, insert_sql, chunk)

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return len(prepared_rows)


def table_exists(table: str, schema: Optional[str] = None, db: str = "target") -> bool:
    qualified_table = _qualify_table(table, schema)
    if "." in qualified_table:
        schema_name, table_name = qualified_table.replace("[", "").replace("]", "").split(".")
    else:
        schema_name, table_name = DEFAULT_SCHEMA, qualified_table

    query = (
        "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?"
    )
    with get_connection(db=db) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (schema_name, table_name))
        result = cursor.fetchone()
    return bool(result and result.cnt)


def fetch_table(table: str, *, schema: Optional[str] = None, db: str = "target") -> pd.DataFrame:
    qualified_table = _qualify_table(table, schema)
    return read_sql(f"SELECT * FROM {qualified_table}", db=db)
