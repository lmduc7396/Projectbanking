#%%
"""
Banking MCP Tool System
Provides modular tools for OpenAI to access and analyze banking data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import json
from functools import wraps, lru_cache
from scipy import stats
import requests
import os
import re
from .tech_analysis import analyze_tickers
from .data_access import (
    load_banking_metrics,
    load_banking_forecast,
    load_comments as load_comments_table,
    load_quarterly_analysis as load_quarterly_analysis_table,
    load_valuation_banking,
    load_earnings_quality,
    load_forecast_consensus,
)


BROKER_STOPWORDS = {
    'BUY', 'SELL', 'HOLD', 'OUTPERFORM', 'UNDERPERFORM', 'NEUTRAL', 'ADD', 'TRADING',
    'OVERWEIGHT', 'UNDERWEIGHT', 'ACCUMULATE', 'REDUCE', 'OUTLOOK', 'FORECAST', 'TARGET',
    'PRICE', 'CONSENSUS', 'ESTIMATE', 'BASE', 'SCENARIO', 'NPATMI', 'PBT', 'NIM', 'NPL',
    'LOAN', 'ROA', 'ROE', 'CIR', 'TOI', 'EBIT', 'EBITDA'
}


def _normalize_metric_label(value: Any) -> str:
    label = str(value) if value is not None else ""
    label = label.replace("_", " ").strip()
    return label if label else "Unknown"


def _normalize_metric_key(value: Any) -> str:
    label = str(value) if value is not None else ""
    return re.sub(r"[^A-Za-z0-9]", "", label).upper()


def _tokenize_candidate(*values: str) -> List[str]:
    tokens: List[str] = []
    for value in values:
        if not value:
            continue
        parts = re.split(r'[^A-Z]', value.upper())
        tokens.extend([p for p in parts if p])
    return tokens


def _derive_broker_code(row: pd.Series) -> str:
    ticker_upper = str(row.get('TICKER') or '').strip().upper()
    raw_org = str(row.get('ORGANCODE') or '').strip()
    candidates: List[str] = []

    if raw_org:
        cleaned = re.sub(rf'\b{ticker_upper}\b', '', raw_org.upper())
        candidates.extend(_tokenize_candidate(cleaned))
        if cleaned.strip() and cleaned.strip() != raw_org.upper():
            candidates.append(cleaned.strip())

    keycodename = str(row.get('KEYCODENAME') or '')
    keycode = str(row.get('KEYCODE') or '')
    candidates.extend(_tokenize_candidate(keycodename, keycode))

    for token in reversed(candidates):
        if token == ticker_upper:
            continue
        if token in BROKER_STOPWORDS:
            continue
        if token.isalpha() and 2 <= len(token) <= 6:
            return token

    if raw_org:
        return raw_org
    return 'Unknown'


class BankingToolSystem:
    """
    Modular tool system for banking analysis
    Easy to extend with new tools using decorator pattern
    """
    
    def __init__(self):
        """Initialize the tool system with lazy loading"""
        self.tools = {}
        self.tool_schemas = []

        # Result cache (per-tool) with TTL
        self.result_cache: Dict[str, Dict[str, Any]] = {}
        self.RESULT_TTL_SECONDS = int(os.getenv("MCP_RESULT_TTL", "300"))

        # External API cache (e.g., stock performance)
        self._stock_cache: Dict[str, Dict[str, Any]] = {}
        self.STOCK_CACHE_TTL_SECONDS = int(os.getenv("MCP_STOCK_TTL", "1800"))  # 30 minutes default

        # Register all tools
        self._register_tools()

    @lru_cache(maxsize=1)
    def _load_historical_year(self) -> pd.DataFrame:
        df = load_banking_metrics('Y')
        if df.empty:
            return df
        if 'Year' in df.columns:
            df = df.copy()
            df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
        return df

    @lru_cache(maxsize=32)
    def _load_historical_year_cols(self, columns_key: str) -> pd.DataFrame:
        cols = json.loads(columns_key)
        base = self._load_historical_year()
        if base.empty:
            return base
        available = [c for c in cols if c in base.columns]
        if not available:
            return base
        return base[available].copy()

    @lru_cache(maxsize=1)
    def _load_historical_quarter(self) -> pd.DataFrame:
        df = load_banking_metrics('Q')
        df = df.copy()
        if 'Date_Quarter' in df.columns:
            df['Date_Quarter'] = df['Date_Quarter'].astype(str)
        return df

    @lru_cache(maxsize=32)
    def _load_historical_quarter_cols(self, columns_key: str) -> pd.DataFrame:
        cols = json.loads(columns_key)
        base = self._load_historical_quarter()
        if base.empty:
            return base
        available = [c for c in cols if c in base.columns]
        if not available:
            return base
        return base[available].copy()

    @lru_cache(maxsize=1)
    def _load_forecast(self) -> pd.DataFrame:
        df = load_banking_forecast()
        if df.empty:
            return df
        if 'Year' in df.columns:
            df = df.copy()
            df['Year'] = pd.to_numeric(df['Year'], errors='coerce').astype('Int64')
        return df

    @lru_cache(maxsize=1)
    def _load_consensus(self) -> pd.DataFrame:
        df = load_forecast_consensus()
        if df.empty:
            return df

        df = df.copy()
        df['FORECASTDATE'] = pd.to_datetime(df['FORECASTDATE'], errors='coerce')
        df['DATE'] = pd.to_datetime(df['DATE'], errors='coerce')
        df['KEYCODE'] = df['KEYCODE'].astype(str)
        df['Metric'] = df['KEYCODE'].str.split('.', n=1).str[-1]
        df.loc[df['Metric'] == df['KEYCODE'], 'Metric'] = df['KEYCODENAME']
        df['Metric'] = df['Metric'].fillna(df['KEYCODENAME'])
        df['Metric'] = df['Metric'].apply(_normalize_metric_label)
        df['MetricKey'] = df['Metric'].apply(_normalize_metric_key)

        keycode_year = pd.to_numeric(df['KEYCODE'].str.extract(r'(\d{4})')[0], errors='coerce')
        df['ForecastYear'] = keycode_year.astype('Int64')
        needs_year = df['ForecastYear'].isna() & df['DATE'].notna()
        df.loc[needs_year, 'ForecastYear'] = df.loc[needs_year, 'DATE'].dt.year
        df['ForecastYear'] = df['ForecastYear'].astype('Int64')

        df['EffectiveDate'] = df['FORECASTDATE'].where(df['FORECASTDATE'].notna(), df['DATE'])
        df['EffectiveDate'] = df['EffectiveDate'].fillna(pd.Timestamp.min)

        return df

    def _melt_metrics(self, df: pd.DataFrame, tickers: List[str], drop_numeric: set, value_name: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        subset = df[df['TICKER'].isin(tickers)].copy()
        if subset.empty:
            return pd.DataFrame()

        if 'Year' not in subset.columns:
            subset['Year'] = pd.NA
        subset['Year'] = pd.to_numeric(subset['Year'], errors='coerce').astype('Int64')
        numeric_cols = subset.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if c not in drop_numeric]
        if not numeric_cols:
            return pd.DataFrame()

        id_vars = ['TICKER', 'Year']
        melted = subset[id_vars + numeric_cols].melt(id_vars=id_vars, var_name='Metric', value_name=value_name)
        melted = melted.dropna(subset=['Year', value_name])
        melted['MetricKey'] = melted['Metric'].apply(_normalize_metric_key)
        return melted

    def _prepare_inhouse_forecast_long(self, tickers: List[str]) -> pd.DataFrame:
        df = self._load_forecast()
        return self._melt_metrics(df, tickers, drop_numeric={'Year', 'Quarter'}, value_name='OurForecast')

    def _prepare_actuals_long(self, tickers: List[str]) -> pd.DataFrame:
        df = self._load_historical_year()
        return self._melt_metrics(df, tickers, drop_numeric={'Year', 'Quarter'}, value_name='ActualValue')

    def _latest_consensus_per_broker(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        work = df.copy()
        if 'BrokerCode' not in work.columns:
            work['BrokerCode'] = work.apply(_derive_broker_code, axis=1)

        group_cols = ['TICKER', 'BrokerCode', 'MetricKey', 'ForecastYear']
        idx = work.groupby(group_cols, dropna=False)['EffectiveDate'].idxmax()
        latest = work.loc[idx].copy()
        latest['VALUE'] = pd.to_numeric(latest['VALUE'], errors='coerce')
        return latest

    def _build_consensus_summary(self, tickers: tuple) -> Dict[str, Any]:
        consensus = self._load_consensus()
        if consensus.empty:
            return {"status": "failed", "error": "Consensus dataset is empty"}

        data = consensus[consensus['TICKER'].isin(tickers)].copy()
        if data.empty:
            return {"status": "failed", "error": "No consensus records for requested tickers"}

        latest = self._latest_consensus_per_broker(data)
        latest = latest[latest['MetricKey'] == 'NPATMI']
        if latest.empty:
            return {"status": "failed", "error": "Consensus NPATMI data is unavailable for requested tickers"}

        summary = latest.groupby(['TICKER', 'Metric', 'MetricKey', 'ForecastYear']).agg(
            brokers=('BrokerCode', 'nunique'),
            consensus_median=('VALUE', 'median')
        ).reset_index()

        forecast_long = self._prepare_inhouse_forecast_long(list(tickers))
        if not forecast_long.empty:
            forecast_long = forecast_long[forecast_long['MetricKey'] == 'NPATMI']
            summary = summary.merge(
                forecast_long[['TICKER', 'MetricKey', 'Year', 'OurForecast']],
                left_on=['TICKER', 'MetricKey', 'ForecastYear'],
                right_on=['TICKER', 'MetricKey', 'Year'],
                how='left'
            ).drop(columns=['Year'], errors='ignore')
        else:
            summary['OurForecast'] = np.nan

        actuals_long = self._prepare_actuals_long(list(tickers))
        actual_lookup = {}
        if not actuals_long.empty:
            actuals_long = actuals_long[actuals_long['MetricKey'] == 'NPATMI']
            actual_lookup = actuals_long.set_index(['TICKER', 'MetricKey', 'Year'])['ActualValue'].to_dict()

        summary['Consensus YoY %'] = np.nan
        summary['In-house YoY %'] = np.nan

        for ticker in tickers:
            ticker_slice = summary[summary['TICKER'] == ticker].sort_values('ForecastYear')
            prev_consensus = None
            prev_inhouse = None

            for idx, row in ticker_slice.iterrows():
                year = row['ForecastYear']
                consensus_value = pd.to_numeric(row['consensus_median'], errors='coerce')
                inhouse_value = pd.to_numeric(row.get('OurForecast'), errors='coerce')

                base_consensus = actual_lookup.get((ticker, 'NPATMI', year - 1))
                base_inhouse = actual_lookup.get((ticker, 'NPATMI', year - 1))

                if base_consensus is None and prev_consensus is not None:
                    base_consensus = prev_consensus
                if base_inhouse is None and prev_inhouse is not None:
                    base_inhouse = prev_inhouse

                if pd.notna(consensus_value) and pd.notna(base_consensus) and base_consensus not in (None, 0):
                    summary.loc[idx, 'Consensus YoY %'] = (consensus_value - base_consensus) / base_consensus * 100
                if pd.notna(inhouse_value) and pd.notna(base_inhouse) and base_inhouse not in (None, 0):
                    summary.loc[idx, 'In-house YoY %'] = (inhouse_value - base_inhouse) / base_inhouse * 100

                if pd.notna(consensus_value):
                    prev_consensus = consensus_value
                if pd.notna(inhouse_value):
                    prev_inhouse = inhouse_value

        def _safe_number(value: Any, decimals: Optional[int] = None) -> Optional[float]:
            if value is None or pd.isna(value):
                return None
            number = float(value)
            if decimals is not None:
                return round(number, decimals)
            return number

        result_data: List[Dict[str, Any]] = []
        missing: List[str] = []

        for ticker in tickers:
            ticker_rows = summary[summary['TICKER'] == ticker].sort_values('ForecastYear')
            if ticker_rows.empty:
                missing.append(ticker)
                continue

            years: List[Dict[str, Any]] = []
            for _, row in ticker_rows.iterrows():
                years.append({
                    "year": int(row['ForecastYear']),
                    "consensus_median": _safe_number(row['consensus_median']),
                    "inhouse_forecast": _safe_number(row.get('OurForecast')),
                    "consensus_yoy_pct": _safe_number(row.get('Consensus YoY %'), 2),
                    "inhouse_yoy_pct": _safe_number(row.get('In-house YoY %'), 2),
                    "brokers": int(row['brokers']) if not pd.isna(row['brokers']) else None
                })

            result_data.append({
                "ticker": ticker,
                "metric": "NPATMI",
                "years": years
            })

        response: Dict[str, Any] = {
            "status": "success",
            "metric": "NPATMI",
            "units": "VND",
            "description": "Consensus median and in-house NPATMI forecasts with YoY change (vs prior actual or latest forecast).",
            "data": result_data
        }

        if missing:
            response["warnings"] = [f"No consensus NPATMI data for: {', '.join(sorted(set(missing)))}"]

        return response

    @lru_cache(maxsize=1)
    def _load_bank_types(self) -> pd.DataFrame:
        df = self._load_historical_quarter()
        if df.empty or 'Type' not in df.columns:
            return pd.DataFrame(columns=['TICKER', 'Type'])
        return df[['TICKER', 'Type']].dropna().drop_duplicates().copy()

    @lru_cache(maxsize=1)
    def _load_comments(self) -> pd.DataFrame:
        df = load_comments_table()
        if df.empty:
            return df
        df = df.copy()
        if 'quarter' in df.columns and 'QUARTER' not in df.columns:
            df['QUARTER'] = df['quarter']
        # Standardize on GENERATED_DATE only
        if 'generated_at' in df.columns and 'GENERATED_DATE' not in df.columns:
            df['GENERATED_DATE'] = df['generated_at']
        return df

    @lru_cache(maxsize=1)
    def _load_quarterly_analysis(self) -> pd.DataFrame:
        df = load_quarterly_analysis_table()
        if df.empty:
            return df
        df = df.copy()
        if 'quarter' in df.columns and 'QUARTER' not in df.columns:
            df['QUARTER'] = df['quarter']
        return df

    @lru_cache(maxsize=1)
    def _load_valuation(self) -> pd.DataFrame:
        df = load_valuation_banking()
        if df.empty:
            return df
        if 'TRADE_DATE' in df.columns:
            df = df.copy()
            df['TRADE_DATE'] = pd.to_datetime(df['TRADE_DATE'])
        return df

    @lru_cache(maxsize=1)
    def _load_earnings_quality_quarterly(self) -> pd.DataFrame:
        return load_earnings_quality('Q')

    @lru_cache(maxsize=1)
    def _load_earnings_quality_yearly(self) -> pd.DataFrame:
        return load_earnings_quality('Y')
    
    def tool(self, name: str, description: str, parameters: Dict = None):
        """
        Decorator to register a tool with OpenAI schema
        Makes it easy to add new tools
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    return {
                        "error": f"Error in {name}: {str(e)}",
                        "status": "failed"
                    }
            
            # Register the tool
            self.tools[name] = wrapper
            
            # Create OpenAI function schema
            # Clean parameters by removing 'required' field from individual params
            clean_params = {}
            required_params = []
            
            if parameters:
                for param_name, param_def in parameters.items():
                    # Check if this parameter is required (default True if not specified)
                    is_required = param_def.get("required", True)
                    if is_required:
                        required_params.append(param_name)
                    
                    # Create clean parameter definition without 'required' field
                    clean_param = {k: v for k, v in param_def.items() if k != "required"}
                    clean_params[param_name] = clean_param
            
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": clean_params,
                        "required": required_params
                    }
                }
            }
            self.tool_schemas.append(schema)
            
            return wrapper
        return decorator
    
    def _register_tools(self):
        """Register all available tools"""
        
        # Tool 1: Get Data Availability
        @self.tool(
            name="get_data_availability",
            description="MANDATORY: You MUST call this first for ANY query about 'latest', 'recent', 'current' to determine actual data periods",
            parameters={}
        )
        def get_data_availability() -> Dict:
            """Get available data periods"""
            quarterly = self._load_historical_quarter()
            yearly = self._load_historical_year()
            forecast = self._load_forecast()

            # Get unique periods with safeguards for empty datasets
            if not quarterly.empty and 'Date_Quarter' in quarterly.columns:
                q_periods = (
                    pd.Series(quarterly['Date_Quarter'].dropna().astype(str).unique())
                    .sort_values()
                    .tolist()
                )[-8:]
            else:
                q_periods = []

            if not yearly.empty and 'Year' in yearly.columns:
                y_periods = (
                    pd.Series(yearly['Year'].dropna().astype(int).unique())
                    .sort_values()
                    .tolist()
                )[-5:]
            else:
                y_periods = []

            if not forecast.empty and 'Year' in forecast.columns:
                f_periods = (
                    pd.Series(forecast['Year'].dropna().astype(int).unique())
                    .sort_values()
                    .tolist()
                )
            else:
                f_periods = []
            
            return {
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "latest_quarterly": q_periods[-1] if q_periods else None,
                "latest_yearly": str(y_periods[-1]) if y_periods else None,
                "recent_quarters": q_periods,
                "recent_years": [str(y) for y in y_periods],
                "forecast_years": [str(y) for y in f_periods],
                "status": "success"
            }
        
        @self.tool(
            name="get_consensus_forecast_summary",
            description="Return NPATMI consensus medians versus in-house forecasts with YoY change for selected tickers.",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers (e.g., ['VCB', 'ACB']).",
                    "required": True
                }
            }
        )
        def get_consensus_forecast_summary(tickers: List[str]) -> Dict:
            if not tickers:
                return {"status": "failed", "error": "Provide at least one ticker."}

            normalized = sorted({str(t).strip().upper() for t in tickers if str(t).strip()})
            if not normalized:
                return {"status": "failed", "error": "No valid tickers supplied."}

            return self._build_consensus_summary(tuple(normalized))
        
        
        # Tool 2: List All Banks (Deprecated - merged into get_bank_info)
        # Use get_bank_info() with no parameters instead
        
        def normalize_metric_name(metric: str, available_columns: list) -> str:
            """Find the best matching column name for a given metric
            Handles underscores vs spaces, case variations, and common aliases"""
            # Direct match first
            if metric in available_columns:
                return metric
            
            # Try case-insensitive match
            metric_lower = metric.lower()
            for col in available_columns:
                if col.lower() == metric_lower:
                    return col
            
            # Try with spaces replaced by underscores and vice versa
            metric_with_space = metric.replace('_', ' ')
            metric_with_underscore = metric.replace(' ', '_')
            
            for col in available_columns:
                col_lower = col.lower()
                if col_lower == metric_with_space.lower() or col_lower == metric_with_underscore.lower():
                    return col
            
            # Common mappings for frequently used metrics
            metric_aliases = {
                # Yield metrics
                'loan_yield': 'Loan yield',
                'deposit_yield': 'Deposit yield',
                
                # Asset quality metrics
                'npl_coverage': 'NPL Coverage ratio',
                'npl_coverage_ratio': 'NPL Coverage ratio',
                'new_npl': 'New NPL',
                'new_g2': 'New G2',
                'group_2': 'GROUP 2',
                'provision_total_loan': 'Provision/ Total Loan',
                'provision_on_bs': 'Provision on Balance Sheet',
                'provision_on_balance_sheet': 'Provision on Balance Sheet',
                
                # Balance sheet metrics
                'total_assets': 'Total Assets',
                'total_equity': 'Total Equity',
                'leverage_multiple': 'Leverage Multiple',
                'overdue_loan': 'Overdue_loan',
                
                # Income statement metrics
                'net_interest_income': 'Net Interest Income',
                'provision_expense': 'Provision expense',
                'provision': 'Provision expense',
                
                # Other metrics
                'individual_percent': 'Individual %',
                'individual_%': 'Individual %',
                'fees_total_asset': 'Fees/ Total asset',
                'fees_total_assets': 'Fees/ Total asset',
            }
            
            # Check aliases
            if metric.lower() in metric_aliases:
                alias_col = metric_aliases[metric.lower()]
                if alias_col in available_columns:
                    return alias_col
            
            # Try removing common suffixes/prefixes
            metric_variations = [
                metric.replace('_ratio', ''),
                metric.replace('ratio', ''),
                metric + '_ratio',
                metric + ' ratio'
            ]
            
            for variation in metric_variations:
                for col in available_columns:
                    if col.lower() == variation.lower():
                        return col
            
            return None  # No match found
        
        # Tool 4: Query Historical Data (Universal - handles single or multiple)
        @self.tool(
            name="query_historical_data",
            description="Query simple historical banking metrics for one or multiple banks. For detailed fundamental analysis, use get_ai_commentary tool",
            parameters={
                "frequency": {
                    "type": "string",
                    "description": "Data frequency - specify 'quarterly' for quarterly data or 'yearly' for yearly data",
                    "enum": ["quarterly", "yearly"],
                    "required": True
                },
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple",
                    "required": False
                },
                "period": {"type": "string", "description": "Single period like 2024-Q3, 2024, or YTD format like 2025-YTD", "required": False},
                "periods": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Multiple periods like [\"2025-Q1\", \"2025-Q2\", \"2025-Q3\"] for getting multiple quarters at once",
                    "required": False
                },
                "metric": {
                    "type": "string",
                    "description": "Single metric to query (e.g., 'NIM', 'NPL', 'PBT', 'ROA'). Use this OR metric_group for efficiency.",
                    "required": False
                },
                "metric_group": {
                    "type": "string", 
                    "description": "Metric group: all, profitability, asset_quality, growth. Use metric for single indicators to save cost.",
                    "enum": ["all", "profitability", "asset_quality", "growth"],
                    "required": False
                }
            }
        )
        def query_historical_data(frequency: str, tickers = None, period: str = None, periods = None, metric: str = None, metric_group: str = "all") -> Dict:
            """Query historical data for one or multiple banks"""
            # Check if YTD format is being used - force quarterly if so
            has_ytd = (period and "YTD" in period) or (periods and any("YTD" in str(p) for p in periods if p))

            # Determine frequency (YTD implies quarterly)
            is_quarterly = True if has_ytd else (frequency == "quarterly")

            # Minimal required columns
            id_col = 'Date_Quarter' if is_quarterly else 'Year'
            required_cols = ['TICKER', id_col]

            # Decide projected vs full load
            df = None
            normalized_metric = None
            if metric:
                # Need to normalize against full column list once
                df_full = self._load_historical_quarter() if is_quarterly else self._load_historical_year()
                normalized_metric = normalize_metric_name(metric, df_full.columns.tolist())
                if normalized_metric:
                    cols = sorted(set(required_cols + [normalized_metric]))
                    key = json.dumps(cols, sort_keys=True)
                    df = self._load_historical_quarter_cols(key) if is_quarterly else self._load_historical_year_cols(key)
                else:
                    # Fallback to full for better error message downstream
                    df = df_full
            elif metric_group and metric_group != "all":
                group_map = {
                    "profitability": ["ROA", "ROE", "NIM", "CIR", "PBT", "TOI", "Loan yield", "Deposit yield"],
                    "asset_quality": ["NPL", "New NPL", "NPL Coverage ratio", "GROUP 2", "Provision/ Total Loan"],
                    "growth": ["Loan", "Deposit", "Total Assets", "NPATMI", "PBT"]
                }
                cols = sorted(set(required_cols + group_map.get(metric_group, [])))
                key = json.dumps(cols, sort_keys=True)
                df = self._load_historical_quarter_cols(key) if is_quarterly else self._load_historical_year_cols(key)
            else:
                df = self._load_historical_quarter() if is_quarterly else self._load_historical_year()
            
            # Apply ticker filter if specified
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                # Special handling for sector tickers which use mixed case
                processed_tickers = []
                for t in tickers:
                    if t.lower() == 'sector':
                        processed_tickers.append('Sector')
                    elif t.upper() == 'SOCB':
                        processed_tickers.append('SOCB')
                    elif t.upper() in ['PRIVATE_1', 'PRIVATE_2', 'PRIVATE_3']:
                        # Private sectors use underscore format
                        processed_tickers.append(t.title())  # Converts to Private_1, Private_2, etc.
                    else:
                        processed_tickers.append(t.upper())
                df = df[df['TICKER'].isin(processed_tickers)]
            
            # Handle YTD format in period
            if period and "YTD" in period and is_quarterly:
                # Data-driven YTD: include all available quarters for that year in the dataset
                year = period.split("-")[0]
                mask = df['Date_Quarter'].astype(str).str.startswith(f"{year}-Q")
                periods = (
                    pd.Series(df.loc[mask, 'Date_Quarter'].astype(str).unique())
                    .sort_values()
                    .tolist()
                )
            
            
            # Handle multiple periods
            if periods and is_quarterly:
                df = df[df['Date_Quarter'].isin(periods)]
            elif period:
                if is_quarterly:
                    df = df[df['Date_Quarter'] == period]
                else:
                    # For yearly, period should be a year number
                    # Skip if it contains YTD (should have been handled above)
                    if "YTD" not in period:
                        df = df[df['Year'] == int(period)]
            
            if df.empty:
                return {"error": "No data found", "status": "failed"}
            
            # Select metrics - single metric takes precedence over metric_group
            if metric:
                # Query single metric for efficiency - normalize the metric name first
                normalized_metric = normalized_metric or normalize_metric_name(metric, df.columns.tolist())
                if normalized_metric:
                    id_cols = ['TICKER', 'Year' if 'Year' in df.columns else 'Date_Quarter']
                    df = df[id_cols + [normalized_metric]]
                else:
                    # Provide helpful error with available similar columns
                    similar_cols = [col for col in df.columns if metric.lower() in col.lower() or col.lower() in metric.lower()]
                    if similar_cols:
                        return {"error": f"Metric '{metric}' not found. Did you mean one of these: {similar_cols[:5]}", "status": "failed"}
                    else:
                        return {"error": f"Metric '{metric}' not found in data", "status": "failed"}
            elif metric_group != "all":
                # Query metric group
                metric_groups = {
                    "profitability": ["ROA", "ROE", "NIM", "CIR", "PBT", "TOI", "Loan yield", "Deposit yield"],
                    "asset_quality": ["NPL", "New NPL", "NPL Coverage ratio", "GROUP 2", "Provision/ Total Loan"],
                    "growth": ["Loan", "Deposit", "Total Assets", "NPATMI", "PBT"]
                }
                metrics = metric_groups.get(metric_group, [])
                available_metrics = [m for m in metrics if m in df.columns]
                if available_metrics:
                    id_cols = ['TICKER', 'Year' if 'Year' in df.columns else 'Date_Quarter']
                    df = df[id_cols + available_metrics]
            
            # Return summary
            result = {
                "records": len(df),
                "data": df.to_dict('records'),  # Return all records, not just head
                "columns": df.columns.tolist(),
                "status": "success"
            }
            
            # Add period information if multiple periods were queried
            if periods:
                result["periods_included"] = periods
            
            return result
        
        # Tool 5: Query Forecast Data (Universal - handles single or multiple)
        @self.tool(
            name="query_forecast_data",
            description="Get simple forecast metrics with historical context for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple",
                    "required": False
                }
            }
        )
        def query_forecast_data(tickers = None) -> Dict:
            """Query all forecast data with historical context for one or multiple banks"""
            # Get forecast data
            forecast_df = self._load_forecast().copy()
            historical_df = self._load_historical_year().copy()

            if forecast_df.empty or 'Year' not in forecast_df.columns:
                return {"error": "No forecast data found", "status": "failed"}
            if historical_df.empty or 'Year' not in historical_df.columns:
                return {"error": "Historical data not available", "status": "failed"}

            forecast_df = forecast_df[forecast_df['Year'].notna()].copy()
            historical_df = historical_df[historical_df['Year'].notna()].copy()

            if forecast_df.empty or historical_df.empty:
                return {"error": "Insufficient forecast or historical data", "status": "failed"}

            forecast_df['Year'] = forecast_df['Year'].astype(int)
            historical_df['Year'] = historical_df['Year'].astype(int)

            # Dynamically determine the latest historical year
            latest_historical_year = historical_df['Year'].max()

            # Handle single ticker or array
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                tickers = [t.upper() for t in tickers]
                forecast_df = forecast_df[forecast_df['TICKER'].isin(tickers)]
                historical_df = historical_df[historical_df['TICKER'].isin(tickers)]
                if forecast_df.empty:
                    return {"error": "No forecast data found for requested tickers", "status": "failed"}

            # Determine forecast years (post-filter)
            forecast_years = sorted(forecast_df['Year'].unique())

            # ALWAYS get ALL forecast years - no year filtering

            # Get latest historical data for comparison
            latest_historical = historical_df[historical_df['Year'] == latest_historical_year]
            
            # Only simple key metrics - for detailed analysis use get_ai_commentary
            key_metrics = ["Loan", "NPL", "ROA", "ROE", "NIM", "PBT"]
            available_metrics = [m for m in key_metrics if m in forecast_df.columns and m in historical_df.columns]
            if not available_metrics:
                return {"error": "Forecast metrics not available", "status": "failed"}
            
            # Prepare response
            response = {
                "latest_actual_year": int(latest_historical_year),
                "forecast_years": [int(y) for y in forecast_years],
                "requested_tickers": tickers if tickers else "All",
                "metrics_included": available_metrics
            }
            
            # Add actual historical data
            if not latest_historical.empty:
                historical_data = latest_historical[['TICKER', 'Year'] + available_metrics].to_dict('records')
                response["actual_data"] = {
                    "year": int(latest_historical_year),
                    "records": len(historical_data),
                    "data": historical_data
                }
            
            # Add forecast data
            forecast_data = forecast_df[['TICKER', 'Year'] + available_metrics].to_dict('records')
            response["forecast_data"] = {
                "years": sorted(forecast_df['Year'].unique().tolist()),
                "records": len(forecast_data),
                "data": forecast_data
            }
            
            # Calculate growth rates if single ticker
            if tickers and len(tickers) == 1 and not latest_historical.empty and len(forecast_data) > 0:
                comparison = {}
                historical_record = latest_historical.iloc[0] if len(latest_historical) > 0 else None
                
                for forecast_record in forecast_data:
                    forecast_year = forecast_record['Year']
                    year_comparison = {}
                    
                    for metric in available_metrics:
                        if historical_record is not None and metric in historical_record:
                            hist_val = historical_record[metric]
                            forecast_val = forecast_record.get(metric)
                            
                            if hist_val and forecast_val and hist_val != 0:
                                growth = ((forecast_val - hist_val) / hist_val) * 100
                                year_comparison[metric] = {
                                    "actual": float(hist_val),
                                    "forecast": float(forecast_val),
                                    "growth_pct": round(growth, 2)
                                }
                    
                    if year_comparison:
                        comparison[f"year_{forecast_year}"] = year_comparison
                
                if comparison:
                    response["comparison"] = comparison
            
            response["status"] = "success"
            response["note"] = "For comprehensive forecast analysis and insights, use get_ai_commentary tool"
            return response
        
        
        # Tool 10 removed - get_sector_performance is now redundant
        # Use query_historical_data with sector tickers instead:
        # - 'Sector' for overall banking sector
        # - 'SOCB' for state-owned banks
        # - 'Private_1', 'Private_2', 'Private_3' for private bank tiers
        
        # Helper function for single stock performance (internal use)
        def get_stock_performance_single(ticker: str, start_date: str, end_date: str) -> Dict:
            """Get stock price performance for a single ticker"""
            ticker = ticker.upper()
            
            try:
                # Parse dates
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                
                # Calculate days between dates (add some buffer days)
                days_diff = (end_dt - start_dt).days + 30
                
                # TCBS API endpoint
                url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
                
                # Calculate timestamps
                from_timestamp = int((end_dt - timedelta(days=days_diff)).timestamp())
                to_timestamp = int((end_dt + timedelta(days=5)).timestamp())  # Add buffer for end date
                
                # API parameters
                params = {
                    "ticker": ticker,
                    "type": "stock",
                    "resolution": "D",
                    "from": str(from_timestamp),
                    "to": str(to_timestamp)
                }
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                }
                
                # Fetch data
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if 'data' in data and data['data']:
                    # Convert to DataFrame
                    df = pd.DataFrame(data['data'])
                    
                    # Convert timestamp to datetime
                    if 'tradingDate' in df.columns:
                        if df['tradingDate'].dtype == 'object' and isinstance(df['tradingDate'].iloc[0], str) and 'T' in df['tradingDate'].iloc[0]:
                            df['tradingDate'] = pd.to_datetime(df['tradingDate'])
                        else:
                            df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms')
                    
                    # Convert to date only for comparison
                    df['date'] = df['tradingDate'].dt.date
                    
                    # Sort by date
                    df = df.sort_values('date')
                    
                    # Find closest dates to requested dates
                    start_date_obj = start_dt.date()
                    end_date_obj = end_dt.date()
                    
                    # Get data for start date (or closest available)
                    start_data = df[df['date'] <= start_date_obj].tail(1)
                    if start_data.empty:
                        start_data = df.head(1)  # Use first available if no earlier data
                    
                    # Get data for end date (or closest available)
                    end_data = df[df['date'] <= end_date_obj].tail(1)
                    if end_data.empty:
                        end_data = df.tail(1)  # Use last available if no data up to end date
                    
                    if not start_data.empty and not end_data.empty:
                        start_price = float(start_data.iloc[0]['close'])
                        end_price = float(end_data.iloc[0]['close'])
                        start_actual_date = str(start_data.iloc[0]['date'])
                        end_actual_date = str(end_data.iloc[0]['date'])
                        
                        # Calculate performance
                        if start_price > 0:
                            performance_pct = ((end_price - start_price) / start_price) * 100
                        else:
                            performance_pct = 0
                        
                        return {
                            "ticker": ticker,
                            "start_date": start_actual_date,
                            "start_price": start_price,
                            "end_date": end_actual_date,
                            "end_price": end_price,
                            "performance_pct": round(performance_pct, 2),
                            "status": "success"
                        }
                    else:
                        return {"error": "Insufficient data for the requested date range", "status": "failed"}
                else:
                    return {"error": f"No price data available for {ticker}", "status": "failed"}
                    
            except ValueError as e:
                return {"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}", "status": "failed"}
            except requests.exceptions.RequestException as e:
                return {"error": f"Error fetching stock data: {str(e)}", "status": "failed"}
            except Exception as e:
                return {"error": f"Unexpected error: {str(e)}", "status": "failed"}
        
        # Tool 7: Get Commentary (Universal - handles single or multiple)
        @self.tool(
            name="get_commentary",
            description="Get detailed commentary by analysts for one or multiple banks for fundamental insights",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single or [\"Sector\"] for sector analysis"
                },
                "quarter": {"type": "string", "description": "Quarter like 2024-Q3"}
            }
        )
        def get_ai_commentary(tickers, quarter: str) -> Dict:
            """Get AI commentary for one or multiple banks"""
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            results = {}
            errors = []
            
            comments_df_cache: Optional[pd.DataFrame] = None
            ticker_col: Optional[str] = None
            quarter_col: Optional[str] = None
            comment_col: Optional[str] = None
            generated_col: Optional[str] = None

            def ensure_comments_loaded() -> bool:
                nonlocal comments_df_cache, ticker_col, quarter_col, comment_col, generated_col
                if comments_df_cache is not None:
                    return True

                df = self._load_comments()
                if df is None or df.empty:
                    return False

                comments_df_cache = df.copy()

                ticker_candidates = ['TICKER', 'ticker']
                quarter_candidates = ['QUARTER', 'quarter']
                comment_candidates = ['COMMENT', 'comment']
                generated_candidates = ['GENERATED_DATE', 'generated_date', 'GENERATED_AT', 'generated_at']

                ticker_col = next((col for col in ticker_candidates if col in comments_df_cache.columns), None)
                quarter_col = next((col for col in quarter_candidates if col in comments_df_cache.columns), None)
                comment_col = next((col for col in comment_candidates if col in comments_df_cache.columns), None)
                generated_col = next((col for col in generated_candidates if col in comments_df_cache.columns), None)

                if ticker_col is None or quarter_col is None:
                    comments_df_cache = None
                    return False

                comments_df_cache[ticker_col] = comments_df_cache[ticker_col].astype(str)
                comments_df_cache[quarter_col] = comments_df_cache[quarter_col].astype(str)
                comments_df_cache['_ticker_lower'] = comments_df_cache[ticker_col].str.lower()
                comments_df_cache['_quarter_str'] = comments_df_cache[quarter_col].astype(str)

                if generated_col:
                    comments_df_cache['_generated_dt'] = pd.to_datetime(comments_df_cache[generated_col], errors='coerce')

                return True

            for ticker in tickers:
                ticker = ticker.upper()

                if not ensure_comments_loaded():
                    errors.append("Comments data not available")
                    continue

                if comments_df_cache is None:
                    errors.append("Comments data unavailable")
                    continue

                quarter_str = str(quarter)
                ticker_mask = comments_df_cache['_ticker_lower'] == ticker.lower()
                quarter_mask = comments_df_cache['_quarter_str'] == quarter_str
                subset = comments_df_cache[ticker_mask & quarter_mask].copy()

                if subset.empty:
                    errors.append(f"No commentary for {ticker} in {quarter}")
                    continue

                if '_generated_dt' in subset.columns:
                    subset = subset.sort_values('_generated_dt', ascending=False, na_position='last')
                else:
                    subset = subset.sort_index(ascending=False)

                latest_row = subset.iloc[0]

                comment_value: Any = latest_row.get(comment_col) if comment_col else ""
                if pd.isna(comment_value):
                    comment_value = ""
                comment_text = str(comment_value)

                generated_value = latest_row.get(generated_col) if generated_col else None
                if generated_value is not None and not pd.isna(generated_value):
                    if isinstance(generated_value, (pd.Timestamp, datetime)):
                        generated_str = generated_value.isoformat()
                    else:
                        generated_str = str(generated_value)
                else:
                    generated_str = ""

                entry_type = "sector" if ticker == "SECTOR" else "bank"

                result_payload = {
                    "type": entry_type,
                    "ticker": ticker,
                    "quarter": quarter,
                    "comment": comment_text,
                    "generated_date": generated_str
                }

                results[ticker] = result_payload
            
            # Return simplified format for single ticker
            if len(tickers) == 1:
                if len(results) == 1:
                    single_result = list(results.values())[0]
                    single_result["status"] = "success"
                    return single_result
                elif errors:
                    return {"error": errors[0], "status": "failed"}
            
            # Return batch format for multiple tickers
            return {
                "results": results,
                "requested": len(tickers),
                "found": len(results),
                "errors": errors if errors else None,
                "status": "success" if results else "failed"
            }
        
        # Tool 8: Get Valuation Analysis (Universal - handles single or multiple)
        @self.tool(
            name="get_valuation_analysis",
            description="Get valuation analysis with Z-score and percentiles for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                },
                "metric": {
                    "type": "string", 
                    "description": "Valuation metric",
                    "enum": ["PE", "PB"],
                    "required": False
                }
            }
        )
        def get_valuation_analysis(tickers, metric: str = "PB") -> Dict:
            """Get valuation analysis for one or multiple banks"""
            # Lazy load the large valuation file only when needed
            df = self._load_valuation()
            if df is None:
                return {"error": "Valuation data not available", "status": "failed"}
            
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            # df already loaded above
            
            # Map metric names to Market_Data schema
            metric_map = {
                "PE": "PE",
                "PB": "PB"
            }
            
            col_name = metric_map.get(metric, "PB")
            
            if col_name not in df.columns:
                return {"error": f"Metric {metric} not found", "status": "failed"}
            
            results = {}
            comparison_data = []

            # Precompute available sector types
            available_types = set(df['Type'].dropna().unique().tolist()) if 'Type' in df.columns else set()

            def series_for(name: str) -> pd.Series:
                """Return a clean valuation series for a bank ticker or an aggregate name.

                - If name is an actual ticker in df, return its series.
                - If name equals 'Sector', return median across all banks by date.
                - If name matches a Type (e.g., 'SOCB', 'Private_1'), return median of that Type by date.
                """
                # Exact ticker
                sel = df[df['TICKER'] == name][['TRADE_DATE', col_name]].dropna()
                if not sel.empty:
                    return sel.sort_values('TRADE_DATE')[col_name]

                # Aggregates
                if name == 'Sector':
                    grp = (
                        df[['TRADE_DATE', col_name]]
                        .dropna()
                        .groupby('TRADE_DATE')[col_name]
                        .median()
                        .sort_index()
                    )
                    return grp
                if name in available_types and 'Type' in df.columns:
                    sub = df[df['Type'] == name][['TRADE_DATE', col_name]].dropna()
                    if not sub.empty:
                        grp = sub.groupby('TRADE_DATE')[col_name].median().sort_index()
                        return grp
                return pd.Series(dtype=float)

            for ticker in tickers:
                ticker = str(ticker).upper()
                series = series_for(ticker)

                if not series.empty:
                    current = float(series.iloc[-1])
                    mean = float(series.mean())
                    median = float(series.median())
                    std = float(series.std())
                    z_score = float((current - mean) / std) if std != 0 else 0.0
                    percentile = float(stats.percentileofscore(series.values, current))

                    interp = "Undervalued" if z_score < -1 else ("Overvalued" if z_score > 1 else "Fair valued")

                    results[ticker] = {
                        "current_value": current,
                        "mean": mean,
                        "median": median,
                        "std": std,
                        "z_score": z_score,
                        "percentile_rank": percentile,
                        "min": float(series.min()),
                        "max": float(series.max()),
                        "interpretation": interp,
                    }

                    comparison_data.append({
                        "ticker": ticker,
                        "current": current,
                        "z_score": z_score,
                        "percentile": percentile,
                        "interpretation": interp,
                    })
            
            # Sort by z_score for ranking
            comparison_data = sorted(comparison_data, key=lambda x: x["z_score"])
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and len(results) == 1:
                ticker = tickers[0]
                single_result = results[ticker].copy()
                single_result["ticker"] = ticker
                single_result["metric"] = metric
                single_result["status"] = "success"
                return single_result
            
            # Return batch format for multiple tickers
            return {
                "metric": metric,
                "detailed_results": results,
                "comparison": comparison_data,
                "most_undervalued": comparison_data[0]["ticker"] if comparison_data else None,
                "most_overvalued": comparison_data[-1]["ticker"] if comparison_data else None,
                "requested": len(tickers),
                "found": len(results),
                "status": "success" if results else "failed"
            }
        
        # Tool 9: Get Stock Performance (Universal - handles single or multiple)
        @self.tool(
            name="get_stock_performance",
            description="Get stock price performance between two dates for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                },
                "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"}
            }
        )
        def get_stock_performance(tickers, start_date: str, end_date: str) -> Dict:
            """Get stock performance for one or multiple banks"""
            import concurrent.futures
            
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            def fetch_single_stock(ticker):
                """Helper function to fetch single stock data"""
                # In-memory cache per ticker/date range
                cache_key = f"{ticker}|{start_date}|{end_date}"
                now_ts = datetime.now().timestamp()
                cached = self._stock_cache.get(cache_key)
                if cached and (now_ts - cached.get('ts', 0)) <= self.STOCK_CACHE_TTL_SECONDS:
                    return ticker, cached['result']
                return ticker, get_stock_performance_single(ticker, start_date, end_date)
            
            results = {}
            performance_comparison = []
            
            # Use ThreadPoolExecutor for parallel API calls
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks
                futures = [executor.submit(fetch_single_stock, ticker.upper()) for ticker in tickers]
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(futures):
                    ticker, result = future.result()
                    results[ticker] = result
                    
                    if result.get("status") == "success":
                        performance_comparison.append({
                            "ticker": ticker,
                            "start_price": result["start_price"],
                            "end_price": result["end_price"],
                            "performance_pct": result["performance_pct"]
                        })
                    # Update cache
                    cache_key = f"{ticker}|{start_date}|{end_date}"
                    self._stock_cache[cache_key] = {"result": result, "ts": datetime.now().timestamp()}
            
            # Sort by performance
            performance_comparison = sorted(performance_comparison, 
                                          key=lambda x: x["performance_pct"], 
                                          reverse=True)
            
            # Calculate summary statistics
            if performance_comparison:
                performances = [p["performance_pct"] for p in performance_comparison]
                summary = {
                    "best_performer": performance_comparison[0]["ticker"],
                    "worst_performer": performance_comparison[-1]["ticker"],
                    "average_performance": round(sum(performances) / len(performances), 2),
                    "median_performance": round(sorted(performances)[len(performances)//2], 2)
                }
            else:
                summary = None
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and tickers[0] in results:
                single_result = results[tickers[0]].copy()
                return single_result
            
            # Return batch format for multiple tickers
            return {
                "period": {"start": start_date, "end": end_date},
                "detailed_results": results,
                "ranking": performance_comparison,
                "summary": summary,
                "requested": len(tickers),
                "successful": len(performance_comparison),
                "status": "success" if performance_comparison else "failed"
            }
        
        # Tool 2: Get Bank/Sector Information (handles banks, sectors, and component queries)
        @self.tool(
            name="get_bank_sector_info",
            description="Get bank sector information. Can: 1) List all banks by sector (no params), 2) Get sector for specific banks, 3) Get component banks within a sector (pass SOCB, Private_1, Private_2, Private_3, or Sector)",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Bank tickers OR sector names (SOCB, Private_1, etc.) - omit to list all banks by sector",
                    "required": False
                }
            }
        )
        def get_bank_sector_info(tickers=None) -> Dict:
            """Get bank/sector information with component bank queries"""
            bank_types = self._load_bank_types()
            if bank_types.empty or bank_types['Type'].dropna().empty:
                return {"error": "Bank sector information not available", "status": "failed"}

            bank_types = bank_types.copy()
            bank_types['TICKER'] = bank_types['TICKER'].astype(str)
            bank_types['Type'] = bank_types['Type'].astype(str)

            # Define known sector names
            sector_names = ['SOCB', 'Private_1', 'Private_2', 'Private_3', 'Sector']
            actual_banks = bank_types[bank_types['TICKER'].str.len() == 3]

            # If no tickers provided, return all banks grouped by sector
            if tickers is None:
                sectors: Dict[str, List[str]] = {}
                for sector, subset in actual_banks.groupby('Type'):
                    components = sorted(subset['TICKER'].unique().tolist())
                    sectors[sector] = components

                total_banks = sum(len(v) for v in sectors.values())
                return {
                    "sectors": sectors,
                    "total_banks": total_banks,
                    "status": "success"
                }

            # Normalize requested tickers
            if isinstance(tickers, str):
                tickers = [tickers]
            tickers = [t.strip() for t in tickers]

            results = []
            sector_lookup = {s.upper(): s for s in sector_names}

            for ticker in tickers:
                ticker_upper = ticker.upper()

                if ticker_upper in sector_lookup:
                    sector_key = sector_lookup[ticker_upper]
                    if sector_key == 'Sector':
                        component_banks = sorted(actual_banks['TICKER'].unique().tolist())
                        results.append({
                            "query": ticker,
                            "type": "sector",
                            "sector_name": "Sector (All Banks)",
                            "component_banks": component_banks,
                            "bank_count": len(component_banks)
                        })
                    else:
                        sector_banks = actual_banks[actual_banks['Type'] == sector_key]['TICKER'].unique().tolist()
                        results.append({
                            "query": ticker,
                            "type": "sector",
                            "sector_name": sector_key,
                            "component_banks": sorted(sector_banks),
                            "bank_count": len(sector_banks)
                        })
                    continue

                bank_info = actual_banks[actual_banks['TICKER'] == ticker_upper]
                if not bank_info.empty:
                    sector = bank_info.iloc[0]['Type']
                    results.append({
                        "query": ticker,
                        "type": "bank",
                        "ticker": ticker_upper,
                        "sector": sector
                    })
                else:
                    results.append({
                        "query": ticker,
                        "type": "error",
                        "error": f"'{ticker}' not found"
                    })

            # Return simplified format for single query
            if len(results) == 1:
                result = results[0]
                if result["type"] == "error":
                    return {"error": result["error"], "status": "failed"}
                if result["type"] == "sector":
                    return {
                        "sector": result["sector_name"],
                        "component_banks": result["component_banks"],
                        "bank_count": result["bank_count"],
                        "status": "success"
                    }
                return {
                    "ticker": result["ticker"],
                    "sector": result["sector"],
                    "status": "success"
                }

            return {
                "results": results,
                "requested": len(tickers),
                "successful": len([r for r in results if r["type"] != "error"]),
                "status": "success" if any(r["type"] != "error" for r in results) else "failed"
            }

        # Tool: Technical Analysis (STS/LTS/OBOS)
        @self.tool(
            name="technical_analysis",
            description="Compute technical scores (Short-Term Trend, Long-Term Trend, Overbought/Oversold) for tickers.",
            parameters={
                "tickers": {"type": "array", "items": {"type": "string"}, "description": "Array of tickers", "required": True}
            }
        )
        def technical_analysis(tickers: list) -> Dict:
            tickers = [str(t).upper() for t in tickers or []]
            if not tickers:
                return {"status": "failed", "error": "No tickers provided"}
            return analyze_tickers(tickers, days=365)
            
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            results = []
            
            for ticker in tickers:
                # Handle case variations for sectors
                if ticker.upper() in [s.upper() for s in sector_names]:
                    # Find the correct case version
                    correct_sector = next((s for s in sector_names if s.upper() == ticker.upper()), ticker)
                    
                    if correct_sector == 'Sector':
                        # Special case: 'Sector' means all banks
                        all_banks = bank_types['TICKER'].tolist()
                        component_banks = [b for b in all_banks if b not in sector_names]
                        results.append({
                            "query": ticker,
                            "type": "sector",
                            "sector_name": "Sector (All Banks)",
                            "component_banks": component_banks,
                            "bank_count": len(component_banks)
                        })
                    else:
                        # Get banks in this specific sector
                        sector_banks = bank_types[bank_types['Type'] == correct_sector]['TICKER'].tolist()
                        # Remove the sector aggregate ticker itself
                        component_banks = [b for b in sector_banks if b != correct_sector]
                        results.append({
                            "query": ticker,
                            "type": "sector",
                            "sector_name": correct_sector,
                            "component_banks": component_banks,
                            "bank_count": len(component_banks)
                        })
                else:
                    # It's a bank ticker - get its sector
                    ticker_upper = ticker.upper()
                    bank_info = bank_types[bank_types['TICKER'] == ticker_upper]
                    
                    if not bank_info.empty:
                        sector = bank_info.iloc[0]['Type']
                        results.append({
                            "query": ticker,
                            "type": "bank",
                            "ticker": ticker_upper,
                            "sector": sector
                        })
                    else:
                        results.append({
                            "query": ticker,
                            "type": "error",
                            "error": f"'{ticker}' not found"
                        })
            
        
        
        # Tool 6: Calculate Growth Metrics (Removed - redundant)
        # OpenAI can calculate growth from raw data returned by query_historical_data
        # For pre-calculated growth metrics, use get_earnings_drivers which has QoQ, YoY, T12M impacts
        
        # Tool 10: Get Earnings Drivers
        @self.tool(
            name="get_earnings_drivers",
            description="Get detailed earnings drivers impact analysis showing what's driving profit changes for one or multiple banks. For cost items, positive score means less cost (good), negative means more cost (bad).",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                },
                "period": {
                    "type": "string",
                    "description": "Period in format YYYY-Q# for quarterly (e.g., 2025-Q2) or YYYY for yearly (e.g., 2024)"
                },
                "timeframe": {
                    "type": "string",
                    "description": "Comparison timeframe",
                    "enum": ["QoQ", "YoY", "T12M"],
                    "required": False
                },
                "frequency": {
                    "type": "string",
                    "description": "Data frequency",
                    "enum": ["quarterly", "yearly"],
                    "required": False
                }
            }
        )
        def get_earnings_drivers(tickers, period: str, timeframe: str = "QoQ", frequency: str = "quarterly") -> Dict:
            """Get earnings drivers analysis for one or multiple banks"""
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            # Load appropriate data based on frequency
            if frequency == "yearly":
                df = self._load_earnings_quality_yearly()
                period_col = 'Year'
                # Yearly data doesn't have QoQ/YoY/T12M suffixes
                suffix = ""
            else:
                df = self._load_earnings_quality_quarterly()
                period_col = 'Date_Quarter'
                # Map timeframe to column suffix
                suffix_map = {
                    "QoQ": "_QoQ",
                    "YoY": "_YoY", 
                    "T12M": "_T12M"
                }
                suffix = suffix_map.get(timeframe, "_QoQ")
            
            if df is None:
                return {"error": "Earnings quality data not available", "status": "failed"}
            
            results = {}
            
            for ticker in tickers:
                ticker = ticker.upper()
                
                # Filter data for ticker and period
                ticker_data = df[(df['TICKER'] == ticker) & (df[period_col] == period)]
                
                if ticker_data.empty:
                    results[ticker] = {
                        "error": f"No data found for {ticker} in {period}",
                        "status": "failed"
                    }
                    continue
                
                # Extract impact columns based on suffix
                data_row = ticker_data.iloc[0]
                
                # Helper function to get value with suffix
                def get_value(col_base, use_suffix=True):
                    col_name = f"{col_base}{suffix}" if use_suffix and suffix else col_base
                    if col_name in data_row.index:
                        value = data_row[col_name]
                        if pd.notna(value):
                            return float(value)
                    return None
                
                # Extract all impact values (return numeric values directly)
                pbt_growth = get_value('PBT_Growth_%')
                revenue_impact = get_value('Top_Line_Impact')
                cost_impact = get_value('Cost_Cutting_Impact')
                nonrec_impact = get_value('Non_Recurring_Impact')
                nii_impact = get_value('NII_Impact')
                fee_impact = get_value('Fee_Impact')
                opex_impact = get_value('OPEX_Impact')
                provision_impact = get_value('Provision_Impact')
                loan_impact = get_value('Loan_Impact')
                nim_impact = get_value('NIM_Impact')
                total_impact = get_value('Total_Impact')
                
                # Helper to round values for cleaner JSON
                def clean_value(value):
                    if value is None:
                        return None
                    return round(value, 1)
                
                # Create simplified, flat structure
                earnings_analysis = {
                    "ticker": ticker,
                    "period": period,
                    "timeframe": timeframe if frequency == "quarterly" else "YoY",
                    "pbt_growth": clean_value(pbt_growth),
                    "revenue_impact": clean_value(revenue_impact),
                    "cost_impact": clean_value(cost_impact),
                    "non_recurring": clean_value(nonrec_impact),
                    "details": {
                        "nii": clean_value(nii_impact),
                        "loan": clean_value(loan_impact),
                        "nim": clean_value(nim_impact),
                        "fees": clean_value(fee_impact),
                        "opex": clean_value(opex_impact),
                        "provisions": clean_value(provision_impact)
                    },
                    "status": "success"
                }
                
                results[ticker] = earnings_analysis
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and len(results) == 1:
                return results[tickers[0]]
            
            # Return batch format for multiple tickers
            return {
                "period": period,
                "timeframe": timeframe if frequency == "quarterly" else "YoY",
                "frequency": frequency,
                "results": results,
                "requested": len(tickers),
                "successful": sum(1 for r in results.values() if r.get("status") == "success"),
                "status": "success" if any(r.get("status") == "success" for r in results.values()) else "failed"
            }
        
        # Tool 11: Render Chart
        @self.tool(
            name="render_chart",
            description="""Create a chart visualization from processed data. 
            INSTRUCTIONS FOR USE:
            1. ALWAYS gather data first using other tools (get_financial_data, get_valuation_metrics, etc.)
            2. Structure data with clear x-axis labels and y-values
            3. Specify y_format: 'percent' for rates/ratios, 'number' for counts, 'currency' for monetary values
            4. Available chart types: line, bar, scatter, area

            IMPORTANT:
            - Only pass processed, chart-ready data
            - Do NOT include raw data tables in your text response
            """,
            parameters={
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "scatter", "area"],
                    "description": "Type of chart to render"
                },
                "data": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "array",
                            "description": "X-axis labels (dates, categories, etc.)",
                            "items": {"type": "string"}
                        },
                        "series": {
                            "type": "array",
                            "description": "Data series to plot",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Series name for legend"},
                                    "y": {
                                        "type": "array", 
                                        "description": "Y-axis values",
                                        "items": {"type": "number"}
                                    }
                                }
                            }
                        }
                    },
                    "required": ["x", "series"]
                },
                "title": {
                    "type": "string",
                    "description": "Chart title"
                },
                "x_label": {
                    "type": "string",
                    "description": "X-axis label",
                    "required": False
                },
                "y_label": {
                    "type": "string",
                    "description": "Y-axis label",
                    "required": False
                },
                "y_format": {
                    "type": "string",
                    "enum": ["percent", "number", "currency"],
                    "description": "Format for y-axis values",
                    "required": False
                }
            }
        )
        def render_chart(chart_type: str, data: Dict, title: str, x_label: str = "", y_label: str = "", y_format: str = "number") -> Dict:
            """Prepare chart specification for rendering"""
            import uuid
            
            # Validate data structure
            if not data or "x" not in data or "series" not in data:
                return {"error": "Invalid data structure. Must have 'x' and 'series' fields", "status": "failed"}
            
            if not data["series"] or len(data["series"]) == 0:
                return {"error": "No data series provided", "status": "failed"}
            
            # Generate unique chart ID
            chart_id = str(uuid.uuid4())[:8]
            
            # Prepare chart specification
            chart_spec = {
                "chart_id": chart_id,
                "chart_type": chart_type,
                "data": data,
                "title": title,
                "x_label": x_label or "",
                "y_label": y_label or "",
                "y_format": y_format,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store chart spec in class attribute for retrieval
            if not hasattr(self, '_pending_charts'):
                self._pending_charts = {}
            self._pending_charts[chart_id] = chart_spec
            
            # Return marker for the chat interface to detect
            return {
                "type": "chart",
                "chart_id": chart_id,
                "chart_spec": chart_spec,  # Include spec in response
                "message": f"Chart '{title}' prepared for rendering",
                "status": "success"
            }
        
        # Tool 12: Forecast Scenario Analysis
        @self.tool(
            name="forecast_scenario",
            description="""Analyze PBT forecast impact from metric changes (NIM, NPL, loan growth, OPEX growth).
            This tool performs what-if analysis to show how PBT changes when key metrics are adjusted.
            
            Example: "What will PBT be if VPB NIM increases by 10bps in 2025?"
            Output: Original PBT forecast, new PBT forecast, percentage change
            
            Metric adjustment formats:
            - NIM/NPL: Use basis points (e.g., 10 means +10bps = +0.1%)
            - Loan/OPEX growth: Use percentage points (e.g., 5 means +5pp to growth rate)
            """,
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of bank tickers (e.g., ['VCB']) or sectors (['SOCB', 'Private_1'])"
                },
                "metric": {
                    "type": "string",
                    "enum": ["NIM", "NPL", "loan_growth", "OPEX_growth", "NPL_coverage", "new_NPL"],
                    "description": "Metric to adjust"
                },
                "adjustment": {
                    "type": "number",
                    "description": "Adjustment value (bps for NIM/NPL, pp for growth rates)"
                },
                "year": {
                    "type": "integer",
                    "description": "Forecast year (e.g., 2025 or 2026)"
                }
            }
        )
        def forecast_scenario(tickers: List[str], metric: str, adjustment: float, year: int) -> Dict:
            """Calculate PBT impact from metric adjustments for multiple banks"""
            
            # Load required data
            historical_year = self._load_historical_year().copy()
            forecast_data = self._load_forecast().copy()

            if historical_year.empty or forecast_data.empty:
                return {
                    "error": "Historical or forecast data unavailable",
                    "status": "failed"
                }

            if 'Year' in historical_year.columns:
                historical_year['Year'] = pd.to_numeric(historical_year['Year'], errors='coerce').astype('Int64')
            forecast_data['Year'] = pd.to_numeric(forecast_data['Year'], errors='coerce').astype('Int64')
            forecast_data = forecast_data.dropna(subset=['Year'])
            historical_year = historical_year.dropna(subset=['Year'])

            if forecast_data.empty:
                return {
                    "error": "Forecast data missing year values",
                    "status": "failed"
                }

            forecast_data['Year'] = forecast_data['Year'].astype(int)
            historical_year['Year'] = historical_year['Year'].astype(int)
            
            # Process each ticker
            results = {}
            total_original_pbt = 0
            total_new_pbt = 0
            
            for ticker in tickers:
                # Validate ticker and get forecast data
                if len(ticker) == 3:
                    # Individual bank
                    bank_forecast = forecast_data[(forecast_data['TICKER'] == ticker) & 
                                                 (forecast_data['Year'] == year)]
                    if bank_forecast.empty:
                        results[ticker] = {
                            "error": f"No forecast data for {ticker} in {year}",
                            "status": "failed"
                        }
                        continue
                    forecast_row = bank_forecast.iloc[0]
                else:
                    # Sector analysis
                    if ticker == 'Sector':
                        # Aggregate all banks with forecast
                        banks = forecast_data[(forecast_data['Year'] == year) & 
                                             (forecast_data['TICKER'].str.len() == 3)]['TICKER'].unique()
                        sector_data = forecast_data[(forecast_data['TICKER'].isin(banks)) & 
                                                   (forecast_data['Year'] == year)]
                    else:
                        # Specific sector (SOCB, Private_1, etc.)
                        sector_data = forecast_data[(forecast_data['TICKER'] == ticker) & 
                                                   (forecast_data['Year'] == year)]
                    
                    if sector_data.empty:
                        results[ticker] = {
                            "error": f"No forecast data for {ticker} in {year}",
                            "status": "failed"
                        }
                        continue
                    
                    # For sectors, aggregate or use pre-calculated values
                    if ticker == 'Sector':
                        # Aggregate metrics
                        forecast_row = pd.Series({
                            'PBT': sector_data['PBT'].sum(),
                            'Net Interest Income': sector_data['Net Interest Income'].sum(),
                            'OPEX': sector_data['OPEX'].sum(),
                            'Provision expense': sector_data['Provision expense'].sum(),
                            'Loan': sector_data['Loan'].sum(),
                            'NIM': (sector_data['NIM'] * sector_data['Loan']).sum() / sector_data['Loan'].sum(),
                            'NPL': (sector_data['NPL'] * sector_data['Loan']).sum() / sector_data['Loan'].sum(),
                            'Provision on Balance Sheet': sector_data['Provision on Balance Sheet'].sum(),
                            'New NPL': (sector_data.get('New NPL', 0) * sector_data['Loan']).sum() / sector_data['Loan'].sum() if 'New NPL' in sector_data.columns else 0
                        })
                    else:
                        forecast_row = sector_data.iloc[0]
                
                # Get original values
                original_pbt = forecast_row['PBT']
                nii = forecast_row['Net Interest Income']
                loan = forecast_row['Loan']
                original_nim = forecast_row.get('NIM', 0)
                original_npl = forecast_row.get('NPL', 0)
                opex = forecast_row.get('OPEX', 0)
                provision_expense = forecast_row.get('Provision expense', 0)
                
                # Get previous year data for growth calculations
                prev_year = year - 1
                if len(ticker) == 3:
                    prev_data = historical_year[(historical_year['TICKER'] == ticker) & 
                                               (historical_year['Year'] == prev_year)]
                else:
                    if ticker == 'Sector':
                        banks = historical_year[(historical_year['Year'] == prev_year) & 
                                               (historical_year['TICKER'].str.len() == 3)]['TICKER'].unique()
                        prev_data = historical_year[(historical_year['TICKER'].isin(banks)) & 
                                                   (historical_year['Year'] == prev_year)]
                        if not prev_data.empty:
                            prev_data = pd.DataFrame([{
                                'Loan': prev_data['Loan'].sum(),
                                'OPEX': prev_data['OPEX'].sum()
                            }])
                    else:
                        prev_data = historical_year[(historical_year['TICKER'] == ticker) & 
                                                   (historical_year['Year'] == prev_year)]
                
                prev_loan = prev_data.iloc[0]['Loan'] if not prev_data.empty else loan * 0.85
                prev_opex = prev_data.iloc[0]['OPEX'] if not prev_data.empty else opex * 0.9
                
                # Calculate PBT change based on metric
                pbt_change = 0
                new_value = None
                original_value = None
                
                if metric == "NIM":
                    # NIM change in basis points
                    nim_change_ratio = adjustment / 10000  # Convert bps to ratio
                    new_nim = original_nim + nim_change_ratio
                    # PBT impact = NIM change * Loan
                    pbt_change = nim_change_ratio * loan
                    new_value = new_nim * 100  # Convert to percentage for display
                    original_value = original_nim * 100
                    
                elif metric == "NPL":
                    # NPL change in basis points
                    npl_change_ratio = adjustment / 10000  # Convert bps to ratio
                    new_npl = original_npl + npl_change_ratio
                    # Simplified: Higher NPL increases provisions
                    # Assume provision = NPL * Loan * Coverage ratio (simplified to 1.0)
                    pbt_change = -(npl_change_ratio * loan)  # Higher NPL reduces PBT
                    new_value = new_npl * 100
                    original_value = original_npl * 100
                    
                elif metric == "loan_growth":
                    # Loan growth change in percentage points
                    original_growth = ((loan / prev_loan) - 1) * 100 if prev_loan != 0 else 15
                    new_growth = original_growth + adjustment
                    new_loan = prev_loan * (1 + new_growth / 100)
                    loan_change = new_loan - loan
                    # PBT impact from loan growth (simplified: assume NIM on new loans)
                    pbt_change = (loan_change / loan) * nii if loan != 0 else 0
                    new_value = new_growth
                    original_value = original_growth
                    
                elif metric == "OPEX_growth":
                    # OPEX growth change in percentage points
                    # OPEX is negative in data (expense)
                    opex_positive = abs(opex)
                    prev_opex_positive = abs(prev_opex)
                    original_growth = ((opex_positive / prev_opex_positive) - 1) * 100 if prev_opex_positive != 0 else 10
                    new_growth = original_growth + adjustment
                    new_opex = prev_opex_positive * (1 + new_growth / 100)
                    opex_change = new_opex - opex_positive
                    # Higher OPEX reduces PBT
                    pbt_change = -opex_change
                    new_value = new_growth
                    original_value = original_growth
                    
                elif metric == "NPL_coverage":
                    # NPL coverage change in percentage points
                    npl_amount = original_npl * loan
                    original_coverage = abs(forecast_row['Provision on Balance Sheet']) / npl_amount * 100 if npl_amount != 0 else 100
                    new_coverage = original_coverage + adjustment
                    # Higher coverage means more provisions
                    coverage_change_ratio = adjustment / 100
                    pbt_change = -(coverage_change_ratio * npl_amount)
                    new_value = new_coverage
                    original_value = original_coverage
                    
                elif metric == "new_NPL":
                    # New NPL formation in basis points
                    new_npl_change_ratio = adjustment / 10000
                    # New NPL directly impacts provisions
                    pbt_change = -(new_npl_change_ratio * loan)
                    new_value = adjustment / 100  # Convert to percentage
                    original_value = forecast_row.get('New NPL', 0) * 100
                
                else:
                    results[ticker] = {
                        "error": f"Unsupported metric: {metric}",
                        "status": "failed"
                    }
                    continue
                
                # Calculate new PBT
                new_pbt = original_pbt + pbt_change
                pbt_change_percent = (pbt_change / original_pbt * 100) if original_pbt != 0 else 0
                
                # Store results for this ticker
                results[ticker] = {
                    "original_value": round(original_value, 2) if original_value is not None else None,
                    "new_value": round(new_value, 2) if new_value is not None else None,
                    "original_pbt": round(original_pbt / 1e12, 2),  # Convert to trillion
                    "new_pbt": round(new_pbt / 1e12, 2),  # Convert to trillion
                    "pbt_change": round(pbt_change / 1e12, 2),  # Convert to trillion
                    "pbt_change_percent": round(pbt_change_percent, 1),
                    "status": "success"
                }
                
                # Accumulate totals
                total_original_pbt += original_pbt
                total_new_pbt += new_pbt
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and len(results) == 1:
                result = results[tickers[0]]
                if result.get("status") == "success":
                    result.update({
                        "ticker": tickers[0],
                        "year": year,
                        "metric": metric,
                        "adjustment": adjustment,
                        "unit": "trillion VND"
                    })
                return result
            
            # Return batch format for multiple tickers
            successful_results = {k: v for k, v in results.items() if v.get("status") == "success"}
            
            # Calculate summary statistics if there are successful results
            summary = None
            if successful_results:
                total_pbt_change = total_new_pbt - total_original_pbt
                avg_change_percent = (total_pbt_change / total_original_pbt * 100) if total_original_pbt != 0 else 0
                
                summary = {
                    "total_original_pbt": round(total_original_pbt / 1e12, 2),
                    "total_new_pbt": round(total_new_pbt / 1e12, 2),
                    "total_pbt_change": round(total_pbt_change / 1e12, 2),
                    "average_change_percent": round(avg_change_percent, 1)
                }
            
            return {
                "year": year,
                "metric": metric,
                "adjustment": adjustment,
                "unit": "trillion VND",
                "results": results,
                "summary": summary,
                "requested": len(tickers),
                "successful": len(successful_results),
                "status": "success" if successful_results else "failed"
            }
        
    
    def execute_tool(self, tool_name: str, arguments: Dict = None) -> Dict:
        """Execute a tool by name with arguments"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}", "status": "failed"}
        
        tool_func = self.tools[tool_name]
        
        # Get the actual function (unwrapped) to inspect parameters
        import inspect
        sig = inspect.signature(tool_func)
        
        # Filter arguments to only include those the function accepts
        filtered_args = {}
        for param_name in sig.parameters:
            if param_name != 'self' and arguments and param_name in arguments:
                filtered_args[param_name] = arguments[param_name]
        # Build cache key
        try:
            cache_key = f"{tool_name}:{json.dumps(filtered_args, sort_keys=True)}"
        except Exception:
            cache_key = f"{tool_name}:{str(filtered_args)}"

        # Result cache check
        now_ts = datetime.now().timestamp()
        cached = self.result_cache.get(cache_key)
        if cached and (now_ts - cached.get('ts', 0)) <= self.RESULT_TTL_SECONDS:
            return cached['result']

        try:
            result = tool_func(**filtered_args)
            # Cache only successful results
            if isinstance(result, dict) and result.get('status') == 'success':
                self.result_cache[cache_key] = {"result": result, "ts": now_ts}
            return result
        except Exception as e:
            return {"error": f"Error executing {tool_name}: {str(e)}", "status": "failed"}
    
    def get_openai_tools(self) -> List[Dict]:
        """Get tool schemas for OpenAI"""
        return self.tool_schemas
    
    def get_tool_list(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())


# Helper function to create a singleton instance
_tool_system_instance = None

def get_tool_system() -> BankingToolSystem:
    """Get or create the banking tool system instance"""
    global _tool_system_instance
    if _tool_system_instance is None:
        _tool_system_instance = BankingToolSystem()
    return _tool_system_instance
