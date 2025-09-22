#%%
import pyodbc
import pandas as pd
import re
from pathlib import Path
import platform
from typing import Optional

# Helper functions
def get_base_path():
    if platform.system() == 'Windows':
        return Path("C:/Users/ducle/OneDrive/Work-related/VS - Code Project")
    else:
        return Path("OneDrive/Work-related/VS - Code Project")

# Connection string
DB_AILAB_STR = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=tcp:dcdwhprod.database.windows.net,1433;DATABASE=dclab;UID=dclab_readonly;PWD=DHS#@vGESADdf!;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _format_identifier(identifier: str) -> str:
    if not VALID_IDENTIFIER.match(identifier):
        raise ValueError(f"Invalid identifier: {identifier}")
    return f"[{identifier}]"


def get_connection(connection_str: str = DB_AILAB_STR) -> pyodbc.Connection:
    """Return a live pyodbc connection using the provided connection string."""
    return pyodbc.connect(connection_str)


def fetch_tables(schema: Optional[str] = None) -> pd.DataFrame:
    """Return a DataFrame of base tables available in the target database."""
    query = (
        "SELECT TABLE_SCHEMA, TABLE_NAME "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE'"
    )
    params = None
    if schema:
        query += " AND TABLE_SCHEMA = ?"
        params = (schema,)

    with get_connection() as conn:
        tables = pd.read_sql(query, conn, params=params)

    return tables.sort_values(["TABLE_SCHEMA", "TABLE_NAME"]).reset_index(drop=True)


def print_tables(schema: Optional[str] = None) -> None:
    """Print the list of available tables, optionally filtered by schema."""
    tables = fetch_tables(schema)
    if tables.empty:
        message = "No tables found in the database." if not schema else f"No tables found for schema '{schema}'."
        print(message)
        return

    for _, row in tables.iterrows():
        print(f"{row['TABLE_SCHEMA']}.{row['TABLE_NAME']}")


def fetch_top_rows(table: str, schema: Optional[str] = None, limit: Optional[int] = 100) -> pd.DataFrame:
    """Return up to limit rows for the requested table; pass None for all rows."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer or None")

    qualified_table = _format_identifier(table)
    if schema:
        qualified_table = f"{_format_identifier(schema)}.{qualified_table}"

    if limit is None:
        query = f"SELECT * FROM {qualified_table}"
    else:
        query = f"SELECT TOP {limit} * FROM {qualified_table}"

    with get_connection() as conn:
        return pd.read_sql(query, conn)


def top_rows_dataframe(table: str, schema: Optional[str] = None, limit: Optional[int] = 100) -> pd.DataFrame:
    """Return the top rows from a table as a DataFrame; pass None for no row limit."""
    return fetch_top_rows(table, schema=schema, limit=limit)


def fetch_table_columns(table: str, schema: Optional[str] = None) -> pd.DataFrame:
    """Return column metadata for the requested table."""
    params = [table]
    query = (
        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = ?"
    )
    if schema:
        query += " AND TABLE_SCHEMA = ?"
        params.append(schema)

    query += " ORDER BY ORDINAL_POSITION"

    with get_connection() as conn:
        columns = pd.read_sql(query, conn, params=params)

    return columns.rename(columns={"CHARACTER_MAXIMUM_LENGTH": "MAX_LENGTH"})


def table_columns_dataframe(table: str, schema: Optional[str] = None) -> pd.DataFrame:
    """Convenience wrapper returning column headers and metadata as a DataFrame."""
    return fetch_table_columns(table, schema=schema)


if __name__ == "__main__":
    # for getting table-list
    print_tables() 
    # Pick a table
    table = 'FA_Quarterly'

    # Checking the scheme of each table
    cols = table_columns_dataframe(table, schema="dbo")
    # Extracting top n-rows of a table
    df = top_rows_dataframe(table, schema="dbo", limit=None)