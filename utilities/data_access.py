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
    """Load daily market/valuation data and enrich with bank Type.

    Migrated to dbo.Market_Data schema with columns like PE, PB, PS, PX_*, MKT_CAP.
    This function filters to banking tickers and attaches their Type classification.
    """
    df = _load_dataframe("SELECT * FROM dbo.Market_Data")

    # Ensure expected columns exist
    if 'TICKER' not in df.columns:
        return df

    # Attach bank Type by merging with quarterly banking metrics mapping
    try:
        banks_q = load_banking_metrics('Q')
        if not banks_q.empty:
            type_map = banks_q[['TICKER', 'Type']].dropna().drop_duplicates()
            df = df.merge(type_map, on='TICKER', how='left')
            # Keep only banking tickers (those that have a Type)
            df = df[df['Type'].notna()].copy()
    except Exception:
        # If mapping fails, proceed without Type (downstream should handle)
        pass

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
