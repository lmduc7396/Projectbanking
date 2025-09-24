"""Central catalog describing warehouse table metadata used by the project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class TableConfig:
    name: str
    key_columns: List[str]
    schema: str = "dbo"


TABLES: Dict[str, TableConfig] = {
    "FA_Quarterly": TableConfig(
        name="FA_Quarterly",
        key_columns=["TICKER", "KEYCODE", "DATE"],
    ),
    "FA_Annual": TableConfig(
        name="FA_Annual",
        key_columns=["TICKER", "KEYCODE", "DATE"],
    ),
    "Valuation": TableConfig(
        name="Valuation",
        key_columns=["TICKER", "TRADE_DATE"],
    ),
    "ValuationBanking": TableConfig(
        name="ValuationBanking",
        key_columns=["TICKER", "TRADE_DATE"],
    ),
    "MarketCap": TableConfig(
        name="MarketCap",
        key_columns=["TICKER", "TRADE_DATE"],
    ),
    "MarketIndex": TableConfig(
        name="MarketIndex",
        key_columns=["COMGROUPCODE", "TRADINGDATE"],
    ),
    "BankingMetrics": TableConfig(
        name="BankingMetrics",
        key_columns=["TICKER", "YEARREPORT", "LENGTHREPORT"],
    ),
    "BankingForecast": TableConfig(
        name="BankingForecast",
        key_columns=["TICKER", "YEARREPORT", "LENGTHREPORT"],
    ),
    "EarningsQualityQuarterly": TableConfig(
        name="EarningsQualityQuarterly",
        key_columns=["TICKER", "Date_Quarter"],
    ),
    "EarningsQualityYearly": TableConfig(
        name="EarningsQualityYearly",
        key_columns=["TICKER", "Year"],
    ),
    "Banking_Comments": TableConfig(
        name="Banking_Comments",
        key_columns=["TICKER", "DATE"],
    ),
    "Sector_Map": TableConfig(
        name="Sector_Map",
        key_columns=["Ticker"],
    ),
    "QuarterlyAnalysis": TableConfig(
        name="QuarterlyAnalysis",
        key_columns=["quarter"],
    ),
}


def get_table(table: str) -> TableConfig:
    try:
        return TABLES[table]
    except KeyError as exc:
        raise KeyError(f"Unknown table '{table}'. Update utilities/data_catalog.TABLES.") from exc
