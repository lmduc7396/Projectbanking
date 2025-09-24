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


def load_banking_metrics(period: str, *, rename: bool = True) -> pd.DataFrame:
    query = "SELECT * FROM dbo.BankingMetrics WHERE PERIOD_TYPE = %s"
    df = _load_dataframe(query, params=[period])

    if rename:
        df = _rename_metrics(df)

    if 'BANK_TYPE' in df.columns and 'Type' not in df.columns:
        df['Type'] = df['BANK_TYPE']

    if 'DATE_STRING' in df.columns:
        label = 'Date_Quarter' if period.upper() == 'Q' else 'Year'
        df[label] = df['DATE_STRING']

    return df


def load_banking_forecast(*, rename: bool = True) -> pd.DataFrame:
    df = _load_dataframe("SELECT * FROM dbo.BankingForecast")
    if rename:
        df = _rename_metrics(df)
    if 'BANK_TYPE' in df.columns and 'Type' not in df.columns:
        df['Type'] = df['BANK_TYPE']
    if 'DATE_STRING' in df.columns and 'Year' not in df.columns:
        df['Year'] = df['DATE_STRING']
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
