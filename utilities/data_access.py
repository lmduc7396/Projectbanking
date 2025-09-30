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
    table = 'EarningsQualityQuarterly' if period.upper() == 'Q' else 'EarningsQualityYearly'
    df = _load_dataframe(f"SELECT * FROM dbo.{table}")
    return df


def load_comments() -> pd.DataFrame:
    df = _load_dataframe("SELECT * FROM dbo.Banking_Comments")
    if 'DATE' in df.columns and 'QUARTER' not in df.columns:
        df = df.rename(columns={'DATE': 'QUARTER'})
    return df


def load_quarterly_analysis() -> pd.DataFrame:
    return _load_dataframe("SELECT * FROM dbo.QuarterlyAnalysis")
