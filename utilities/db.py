"""Database helper functions built on top of the pyodbc connector."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyodbc

from dclab_sql import establish_connection, execute as _execute, get_sql_connection, read_sql as _read_sql


DEFAULT_SCHEMA = "dbo"


def _translate_role(db: str) -> str:
    return "target" if db == "target" else "source"


def create_connection_from_string(conn_str: str, autocommit: bool = False) -> pyodbc.Connection:
    """Instantiate a pyodbc connection from an arbitrary connection string."""

    return get_sql_connection(conn_str, autocommit=autocommit)


@contextmanager
def get_connection(db: str = "target", autocommit: bool = False) -> Iterable[pyodbc.Connection]:
    """Yield a live pyodbc connection for the requested database role."""

    conn = establish_connection(role=_translate_role(db), autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


def read_sql(query: str, params: Optional[Sequence] = None, db: str = "target") -> pd.DataFrame:
    """Execute a SELECT query returning a pandas DataFrame."""

    return _read_sql(query, params=params, role=_translate_role(db))


def execute(query: str, params: Optional[Sequence] = None, db: str = "target") -> None:
    """Run a non-query statement (INSERT/UPDATE/DELETE)."""

    _execute(query, params=params, role=_translate_role(db))


def _qualify_table(table: str, schema: Optional[str]) -> str:
    if schema:
        return f"[{schema}].[{table}]"
    if "." in table:
        return table
    return f"[{DEFAULT_SCHEMA}].[{table}]"


def _prepare_dataframe(df: pd.DataFrame, columns: Sequence[str]) -> Tuple[List[str], List[Tuple]]:
    selected = df.loc[:, columns]
    sanitized = selected.replace({np.nan: None})
    sanitized = sanitized.where(pd.notnull(sanitized), None)
    return list(selected.columns), list(map(tuple, sanitized.to_numpy()))


def _executemany(cursor, sql: str, rows: List[Tuple]) -> None:
    if not rows:
        return
    if hasattr(cursor, "fast_executemany"):
        cursor.fast_executemany = True
    cursor.executemany(sql, rows)


def _delete_conflicts(
    cursor,
    qualified_table: str,
    key_columns: Sequence[str],
    rows: List[Tuple],
) -> None:
    if not key_columns or not rows:
        return

    placeholders = " AND ".join(f"[{col}] = ?" for col in key_columns)
    delete_sql = f"DELETE FROM {qualified_table} WHERE {placeholders}"
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
    """Insert rows into a table, deleting conflicts on the provided keys."""

    if df.empty:
        return 0

    qualified_table = _qualify_table(table, schema)
    insert_columns, prepared_rows = _prepare_dataframe(df, list(df.columns))

    with get_connection(db=db, autocommit=False) as conn:
        cursor = conn.cursor()
        try:
            for chunk in _chunk_iterable(prepared_rows, batch_size):
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
        finally:
            cursor.close()

    return len(prepared_rows)


def table_exists(table: str, schema: Optional[str] = None, db: str = "target") -> bool:
    qualified_table = _qualify_table(table, schema)
    if "." in qualified_table:
        schema_name, table_name = qualified_table.replace("[", "").replace("]", "").split(".")
    else:
        schema_name, table_name = DEFAULT_SCHEMA, qualified_table.strip('[]')

    query = (
        "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?"
    )
    df = read_sql(query, params=[schema_name, table_name], db=db)
    return bool(not df.empty and df.iloc[0, 0])


def fetch_table(table: str, *, schema: Optional[str] = None, db: str = "target") -> pd.DataFrame:
    qualified_table = _qualify_table(table, schema)
    return read_sql(f"SELECT * FROM {qualified_table}", db=db)


__all__ = [
    "get_connection",
    "read_sql",
    "execute",
    "upsert_dataframe",
    "table_exists",
    "fetch_table",
    "create_connection_from_string",
]
