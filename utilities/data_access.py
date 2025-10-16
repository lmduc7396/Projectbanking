"""High-level data loading helpers for reading curated datasets from the warehouse."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

from utilities.db import get_connection

# Ensure environment variables from .env are available before any DB calls
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / 'Data'


@lru_cache(maxsize=1)
def _keycode_mapping() -> dict:
    key_items_path = DATA_DIR / 'Key_items.xlsx'
    key_items = pd.read_excel(key_items_path)
    return dict(zip(key_items['KeyCode'], key_items['Name']))


def _rename_metrics(df: pd.DataFrame) -> pd.DataFrame:
    mapping = _keycode_mapping()
    available = {k: v for k, v in mapping.items() if k in df.columns}
    if available:
        df = df.rename(columns=available)
    return df


def _load_dataframe(query: str, params: Optional[list] = None) -> pd.DataFrame:
    with get_connection(db="target") as conn:
        return pd.read_sql(query, conn, params=params)


def _normalize_period_columns(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Ensure common period columns exist regardless of source schema."""
    period = period.upper()

    if 'BANK_TYPE' in df.columns and 'Type' not in df.columns:
        df['Type'] = df['BANK_TYPE']

    year_source = None
    if 'YEARREPORT' in df.columns:
        year_source = pd.to_numeric(df['YEARREPORT'], errors='coerce')
    elif 'YEAR' in df.columns:
        year_source = pd.to_numeric(df['YEAR'], errors='coerce')

    if year_source is not None:
        df['Year'] = year_source.astype('Int64')

    if period == 'Q':
        if 'LENGTHREPORT' in df.columns and 'Quarter' not in df.columns:
            df['Quarter'] = pd.to_numeric(df['LENGTHREPORT'], errors='coerce').astype('Int64')

        if 'DATE_STRING' in df.columns:
            df['Date_Quarter'] = df['DATE_STRING']
        elif 'Year' in df.columns and 'Quarter' in df.columns:
            df['Date_Quarter'] = (
                df['Year'].astype(str).str.replace('<NA>', '', regex=False)
                + '-Q'
                + df['Quarter'].astype(str).str.replace('<NA>', '', regex=False)
            )
    else:
        if 'DATE_STRING' in df.columns and 'Year' not in df.columns:
            df['Year'] = pd.to_numeric(df['DATE_STRING'], errors='coerce').astype('Int64')

    # Convert Decimal/object numeric columns to floats for downstream math operations
    for column in df.columns:
        if df[column].dtype == 'object':
            converted = pd.to_numeric(df[column], errors='ignore')
            df[column] = converted

    return df


def load_banking_metrics(period: str, *, rename: bool = True) -> pd.DataFrame:
    period = period.upper()
    query = "SELECT * FROM dbo.BankingMetrics WHERE PERIOD_TYPE = %s AND ACTUAL = 1"
    df = _load_dataframe(query, params=[period])

    if rename:
        df = _rename_metrics(df)

    return _normalize_period_columns(df, period)


def load_banking_forecast(period: str = 'Y', *, rename: bool = True) -> pd.DataFrame:
    period = (period or 'Y').upper()
    query = "SELECT * FROM dbo.BankingMetrics WHERE ACTUAL = 0"
    params: list = []
    if period:
        query += " AND PERIOD_TYPE = %s"
        params.append(period)

    df = _load_dataframe(query, params=params or None)
    if df.empty:
        return df

    if rename:
        df = _rename_metrics(df)

    return _normalize_period_columns(df, period)


def load_forecast_consensus() -> pd.DataFrame:
    """Load consensus forecasts from broker houses."""
    query = "SELECT * FROM dbo.Forecast_Consensus"
    df = _load_dataframe(query)
    return df


def load_valuation_banking() -> pd.DataFrame:
    """Load last 5 years of PE/PB for banking tickers only.

    - Source: dbo.Market_Data
    - Columns: TICKER, TRADE_DATE, PE, PB, Type
    - Filters: TRADE_DATE >= GETDATE() - 5 years; TICKER limited to those present in BankingMetrics
    """
    query = """
        SELECT md.TICKER,
               md.TRADE_DATE,
               md.PE,
               md.PB,
               bm.BANK_TYPE AS Type
        FROM dbo.Market_Data AS md
        INNER JOIN (
            SELECT TICKER, MAX(BANK_TYPE) AS BANK_TYPE
            FROM dbo.BankingMetrics
            GROUP BY TICKER
        ) AS bm
            ON md.TICKER = bm.TICKER
        WHERE md.TRADE_DATE >= DATEADD(year, -5, CAST(GETDATE() AS date))
          AND (md.PE IS NOT NULL OR md.PB IS NOT NULL)
    """

    df = _load_dataframe(query)
    return df


def load_earnings_quality(period: str) -> pd.DataFrame:
    """Load earnings driver datasets.

    Prefers the consolidated dbo.Banking_Drivers table and falls back to
    legacy materialized tables when necessary so existing workflows continue
    to operate during the migration window.
    """

    if not period:
        raise ValueError('period must be provided ("Q" or "Y")')

    period = period.upper()
    if period not in {"Q", "Y"}:
        raise ValueError("period must be 'Q' for quarterly or 'Y' for yearly")

    query = "SELECT * FROM dbo.Banking_Drivers WHERE PERIOD_TYPE = %s"

    try:
        df = _load_dataframe(query, params=[period])
    except Exception:
        table = 'EarningsQualityQuarterly' if period == 'Q' else 'EarningsQualityYearly'
        df = _load_dataframe(f"SELECT * FROM dbo.{table}")

    if df.empty:
        return df

    # Ensure downstream consumers have consistent period helper columns
    if period == 'Q' and 'Date_Quarter' not in df.columns:
        if 'DATE_STRING' in df.columns:
            df['Date_Quarter'] = df['DATE_STRING']
        elif 'DATE' in df.columns:
            df['Date_Quarter'] = df['DATE']

    if period == 'Y' and 'Year' not in df.columns:
        if 'DATE_STRING' in df.columns:
            df['Year'] = pd.to_numeric(df['DATE_STRING'], errors='ignore')
        elif 'DATE' in df.columns:
            df['Year'] = pd.to_numeric(df['DATE'], errors='ignore')

    return df


def load_comments() -> pd.DataFrame:
    df = _load_dataframe("SELECT * FROM dbo.Banking_Comments")
    if 'DATE' in df.columns and 'QUARTER' not in df.columns:
        df = df.rename(columns={'DATE': 'QUARTER'})
    return df


def _determine_period_column() -> Optional[str]:
    """Inspect the Banking_Comments table to determine the quarter column name."""
    try:
        preview = _load_dataframe("SELECT TOP 0 * FROM dbo.Banking_Comments")
    except Exception:
        return None

    candidates = ['QUARTER', 'Quarter', 'quarter', 'DATE', 'Date', 'date', 'Date_Quarter']
    columns = {col.lower(): col for col in preview.columns}
    for candidate in candidates:
        key = candidate.lower()
        if key in columns:
            return columns[key]
    return None


def load_quarterly_analysis() -> pd.DataFrame:
    period_column = _determine_period_column()
    period_column = period_column or 'QUARTER'

    def _wrap(col: str) -> str:
        return col if col.startswith('[') and col.endswith(']') else f'[{col}]'

    wrapped_period_col = _wrap(period_column)

    sector_query = (
        "SELECT "
        f"{wrapped_period_col} AS quarter_label, "
        "COMMENT AS analysis_text, "
        "GENERATED_DATE, GENERATED_AT "
        "FROM dbo.Banking_Comments "
        "WHERE LOWER(TICKER) = 'sector'"
    )

    try:
        sector_df = _load_dataframe(sector_query)
    except Exception:
        sector_df = pd.DataFrame()

    if not sector_df.empty:
        sector_df = sector_df.rename(columns={'quarter_label': 'quarter'})
        sector_df['quarter'] = sector_df['quarter'].astype(str)

        # Normalise generated timestamp
        generated_cols = [col for col in ['GENERATED_DATE', 'generated_date', 'GENERATED_AT', 'generated_at'] if col in sector_df.columns]
        generated_series = pd.Series(pd.NaT, index=sector_df.index)
        for col in generated_cols:
            generated_series = generated_series.fillna(pd.to_datetime(sector_df[col], errors='coerce'))
        sector_df['generated_date'] = generated_series

        sector_df = sector_df[['quarter', 'analysis_text', 'generated_date']]

        # Fetch bank counts excluding sector aggregate
        bank_count_query = (
            "SELECT "
            f"{wrapped_period_col} AS quarter_label, "
            "COUNT(*) AS bank_count "
            "FROM dbo.Banking_Comments "
            "WHERE LOWER(TICKER) <> 'sector' "
            f"GROUP BY {wrapped_period_col}"
        )
        try:
            bank_counts = _load_dataframe(bank_count_query)
            bank_counts = bank_counts.rename(columns={'quarter_label': 'quarter'})
            bank_counts['quarter'] = bank_counts['quarter'].astype(str)
        except Exception:
            bank_counts = pd.DataFrame(columns=['quarter', 'bank_count'])

        df = sector_df.merge(bank_counts, on='quarter', how='left')
        df['status'] = 'success'
    else:
        # Attempt legacy consolidated table if available
        try:
            legacy_query = (
                "SELECT quarter, analysis_text, bank_count, generated_date, status "
                "FROM dbo.QuarterlyAnalysis"
            )
            df = _load_dataframe(legacy_query)
        except Exception:
            df = pd.DataFrame()

        if df.empty:
            # Final fallback for local development environments
            fallback_path = DATA_DIR / 'quarterly_analysis_results.parquet'
            if fallback_path.exists():
                df = pd.read_parquet(fallback_path)
            else:
                fallback_csv = DATA_DIR / 'quarterly_analysis_results.csv'
                if fallback_csv.exists():
                    df = pd.read_csv(fallback_csv)

        if df.empty:
            return df

        rename_map = {
            'QUARTER': 'quarter',
            'Quarter': 'quarter',
            'DATE': 'quarter',
            'Date': 'quarter',
            'analysis_text': 'analysis_text',
            'ANALYSIS_TEXT': 'analysis_text',
            'BANK_COUNT': 'bank_count',
            'bank_count': 'bank_count',
            'GENERATED_DATE': 'generated_date',
            'generated_date': 'generated_date',
            'status': 'status',
            'STATUS': 'status',
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        if 'generated_date' in df.columns:
            df['generated_date'] = pd.to_datetime(df['generated_date'], errors='coerce')

        if 'status' not in df.columns:
            df['status'] = 'success'

        if 'bank_count' not in df.columns:
            df['bank_count'] = pd.NA

    df = df[['quarter', 'analysis_text', 'bank_count', 'generated_date', 'status']].copy()
    df = df.sort_values('quarter', ascending=False).reset_index(drop=True)
    return df
