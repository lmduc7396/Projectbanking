"""High-level data loading helpers for reading curated datasets from the warehouse."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from utilities.db import get_connection

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
    query = "SELECT * FROM dbo.BankingMetrics WHERE PERIOD_TYPE = ?"
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
    df = _load_dataframe("SELECT * FROM dbo.ValuationBanking")
    if 'BANK_TYPE' in df.columns and 'Type' not in df.columns:
        df['Type'] = df['BANK_TYPE']
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
