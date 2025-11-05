#%%
"""Data extraction pipeline for migrating legacy pulls into the analytics warehouse.

This module reads from the legacy SQL Server (SOURCE_DB_CONNECTION_STRING) and
upserts curated datasets into the target warehouse
(TARGET_DB_CONNECTION_STRING). The transformation logic aligns each dataset
with the schemas defined in DATABASE_SCHEMA.md.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd

from utilities.data_catalog import get_table
from utilities.db import get_connection, read_sql, upsert_dataframe

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def fetch_from_source(query: str, params: Optional[Dict] = None) -> pd.DataFrame:
    """Execute a query against the legacy source database."""
    return read_sql(query, params=params, db="source")


def _clean_ticker(value: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    match = re.match(r"^([A-Z]{3})\s+VN\s+Equity$", value.strip())
    return match.group(1) if match else None


def _quarter_numeric(label: str) -> Optional[int]:
    match = re.match(r"^(?P<year>\d{4})Q(?P<quarter>[1-4])$", str(label).strip())
    if not match:
        return None
    return int(match.group("year")) * 10 + int(match.group("quarter"))


def _extract_year(label: str) -> Optional[int]:
    match = re.search(r"(20\d{2})", str(label))
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Financial statements (quarterly + annual)
# ---------------------------------------------------------------------------

def transform_financial_statements(raw_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if raw_df.empty:
        return {"FA_Quarterly": raw_df, "FA_Annual": raw_df}

    df = raw_df.copy()
    df['DATE'] = df['DATE'].astype(str).str.strip()
    df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce')
    df = df.dropna(subset=['TICKER', 'KEYCODE', 'DATE'])

    quarter_mask = df['DATE'].str.contains('Q', na=False)

    quarterly = df[quarter_mask].copy()
    quarterly['YEAR'] = quarterly['DATE'].str[:4].astype('Int64', errors='ignore')
    quarterly['quarter_numeric'] = quarterly['DATE'].apply(_quarter_numeric)
    quarterly = quarterly.dropna(subset=['quarter_numeric'])
    quarterly = quarterly.sort_values(['TICKER', 'KEYCODE', 'quarter_numeric'])
    quarterly['YoY'] = (
        quarterly.groupby(['TICKER', 'KEYCODE'])['VALUE']
        .transform(lambda s: s.pct_change(4))
    )
    quarterly = quarterly.drop(columns=['quarter_numeric'])
    quarterly = quarterly[['TICKER', 'KEYCODE', 'DATE', 'VALUE', 'YEAR', 'YoY']]

    annual = df[~quarter_mask].copy()
    annual['YEAR'] = annual['DATE'].apply(_extract_year).astype('Int64')
    annual = annual.dropna(subset=['YEAR'])
    annual = annual.sort_values(['TICKER', 'KEYCODE', 'YEAR'])
    annual['YoY'] = (
        annual.groupby(['TICKER', 'KEYCODE'])['VALUE']
        .transform(lambda s: s.pct_change())
    )
    annual['DATE'] = annual['YEAR'].astype(str)
    annual = annual[['TICKER', 'KEYCODE', 'DATE', 'VALUE', 'YEAR', 'YoY']]

    return {
        'FA_Quarterly': quarterly,
        'FA_Annual': annual,
    }


def load_financial_statements() -> Dict[str, pd.DataFrame]:
    query = """
        SELECT KEYCODE, TICKER, DATE, VALUE
        FROM SIL.W_F_FIN_FINANCIAL_STATEMENT
        WHERE DATE >= '2016'
    """
    raw = fetch_from_source(query)
    logger.info("Loaded %s financial statement rows", len(raw))
    return transform_financial_statements(raw)


# ---------------------------------------------------------------------------
# Market data (valuation, market cap, index)
# ---------------------------------------------------------------------------

def transform_valuation(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    valuation = df.copy()
    valuation['TICKER'] = valuation['PRIMARYSECID'].apply(_clean_ticker)
    valuation = valuation.dropna(subset=['TICKER'])
    valuation['TRADE_DATE'] = pd.to_datetime(valuation['TRADE_DATE']).dt.tz_localize(None)

    valuation = valuation.rename(
        columns={
            'PE_RATIO': 'P/E',
            'PX_TO_BOOK_RATIO': 'P/B',
            'PX_TO_SALES_RATIO': 'P/S',
        }
    )

    for col in ['P/E', 'P/B', 'P/S', 'EV/EBITDA']:
        if col not in valuation.columns:
            valuation[col] = np.nan
        valuation[col] = pd.to_numeric(valuation[col], errors='coerce')

    return valuation[['TICKER', 'TRADE_DATE', 'P/E', 'P/B', 'P/S', 'EV/EBITDA']]


def load_valuation() -> pd.DataFrame:
    query = """
        SELECT PRIMARYSECID, TRADE_DATE, PE_RATIO, PX_TO_BOOK_RATIO, PX_TO_SALES_RATIO
        FROM SIL.S_BBG_DATA_DWH_ADJUSTED
        WHERE PRIMARYSECID LIKE '%VN Equity%'
          AND TRADE_DATE >= '2018-01-01'
    """
    df = fetch_from_source(query)
    logger.info("Loaded %s valuation rows", len(df))
    return transform_valuation(df)


def transform_market_cap(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    mc = df.copy()
    mc['TICKER'] = mc['PRIMARYSECID'].apply(_clean_ticker)
    mc = mc.dropna(subset=['TICKER'])
    mc['TRADE_DATE'] = pd.to_datetime(mc['TRADE_DATE']).dt.tz_localize(None)
    mc['CUR_MKT_CAP'] = pd.to_numeric(mc['CUR_MKT_CAP'], errors='coerce')
    return mc[['TICKER', 'TRADE_DATE', 'CUR_MKT_CAP']]


def load_market_cap() -> pd.DataFrame:
    query = """
        SELECT PRIMARYSECID, CUR_MKT_CAP, TRADE_DATE
        FROM SIL.S_BBG_DATA_DWH_ADJUSTED
        WHERE PRIMARYSECID LIKE '%VN Equity%'
          AND TRADE_DATE >= DATEADD(year, -5, GETDATE())
    """
    df = fetch_from_source(query)
    logger.info("Loaded %s market cap rows", len(df))
    return transform_market_cap(df)


def transform_market_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    idx = df.copy()
    idx['TRADINGDATE'] = pd.to_datetime(idx['TRADINGDATE']).dt.tz_localize(None)

    rename_map = {
        'HIGHESTINDEX': 'HIGHEST',
        'LOWESTINDEX': 'LOWEST',
        'TOTALMATCHVOLUME': 'TOTALSHARE',
        'TOTALMATCHVALUE': 'TOTALVALUE',
        'FOREIGNBUYVOLUMEMATCHED': 'FOREIGNBUYVOLUME',
        'FOREIGNSELLVOLUMEMATCHED': 'FOREIGNSELLVOLUME',
    }
    for src, dest in rename_map.items():
        if src in idx.columns and dest not in idx.columns:
            idx = idx.rename(columns={src: dest})

    keep_columns = [
        'COMGROUPCODE', 'TRADINGDATE', 'INDEXVALUE', 'PRIORINDEXVALUE',
        'HIGHEST', 'LOWEST', 'TOTALSHARE', 'TOTALVALUE',
        'FOREIGNBUYVOLUME', 'FOREIGNSELLVOLUME'
    ]
    existing = [col for col in keep_columns if col in idx.columns]
    return idx[existing]


def load_market_index() -> pd.DataFrame:
    query = """
        SELECT COMGROUPCODE, INDEXVALUE, PRIORINDEXVALUE,
               HIGHESTINDEX, LOWESTINDEX,
               TOTALMATCHVOLUME, TOTALMATCHVALUE,
               FOREIGNBUYVOLUMEMATCHED, FOREIGNSELLVOLUMEMATCHED,
               TRADINGDATE
        FROM dbo.S_SPS_HOSEINDEX
        WHERE TRADINGDATE >= '2016-01-01'
    """
    df = fetch_from_source(query)
    logger.info("Loaded %s market index rows", len(df))
    return transform_market_index(df)


# ---------------------------------------------------------------------------
# Pipeline execution helpers
# ---------------------------------------------------------------------------

@dataclass
class DatasetTask:
    name: str
    loader: Callable[[], pd.DataFrame]


DATASET_TASKS: Dict[str, DatasetTask] = {
    'FA_Quarterly': DatasetTask('FA_Quarterly', lambda: load_financial_statements()['FA_Quarterly']),
    'FA_Annual': DatasetTask('FA_Annual', lambda: load_financial_statements()['FA_Annual']),
    'Valuation': DatasetTask('Valuation', load_valuation),
    'MarketCap': DatasetTask('MarketCap', load_market_cap),
    'MarketIndex': DatasetTask('MarketIndex', load_market_index),
}


def _persist_dataframe(table_name: str, df: pd.DataFrame) -> None:
    config = get_table(table_name)
    if df.empty:
        logger.warning("No data returned for %s; skipping", table_name)
        return
    inserted = upsert_dataframe(df, table=config.name, key_columns=config.key_columns)
    logger.info("Upserted %s rows into %s", inserted, config.name)


def full_refresh(table: Optional[str] = None) -> None:
    if table:
        task = DATASET_TASKS.get(table)
        if not task:
            available = ', '.join(DATASET_TASKS.keys())
            raise ValueError(f"Unknown dataset '{table}'. Available: {available}")
        logger.info("Starting full refresh for %s", table)
        df = task.loader()
        _persist_dataframe(task.name, df)
        return

    logger.info("Starting full refresh for all datasets")
    # Avoid re-running the financial statement query twice
    financial = load_financial_statements()
    _persist_dataframe('FA_Quarterly', financial['FA_Quarterly'])
    _persist_dataframe('FA_Annual', financial['FA_Annual'])

    for name in ['Valuation', 'MarketCap', 'MarketIndex']:
        df = DATASET_TASKS[name].loader()
        _persist_dataframe(name, df)

    logger.info("Full refresh complete")


if __name__ == "__main__":
    full_refresh()
