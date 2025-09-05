"""
Utility functions for determining forecast years dynamically based on available data.
"""
import pandas as pd
import os
from typing import Tuple, List

def get_forecast_years(dfcompaniesyear: pd.DataFrame = None) -> Tuple[int, int, int]:
    """
    Dynamically determine forecast years based on the most recent full year data.
    
    Full year data is identified by LENGTHREPORT=5 or by checking yearly aggregated data.
    The forecast years are set as +1 and +2 from the most recent full year.
    
    Args:
        dfcompaniesyear: DataFrame with yearly data. If None, will try to load from BS_Bank.csv
    
    Returns:
        Tuple of (most_recent_full_year, forecast_year_1, forecast_year_2)
    """
    
    if dfcompaniesyear is None:
        # Load prepared Parquet data to determine most recent historical year
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            year_path = os.path.join(project_root, 'Data', 'dfsectoryear.parquet')
            if os.path.exists(year_path):
                df_year = pd.read_parquet(year_path)
                years = pd.to_numeric(df_year['Year'], errors='coerce').dropna().astype(int)
                years_with_full_data = sorted(years.unique())
            else:
                quarter_path = os.path.join(project_root, 'Data', 'dfsectorquarter.parquet')
                df_quarter = pd.read_parquet(quarter_path)
                years = pd.to_numeric(df_quarter['Date_Quarter'].astype(str).str.extract(r'(\d{4})')[0], errors='coerce').dropna().astype(int)
                years_with_full_data = sorted(years.unique())
        except Exception:
            # Flexible fallback: current year - 1
            from datetime import datetime
            years_with_full_data = [datetime.now().year - 1]
    else:
        # Use provided dataframe: expect a yearly DataFrame with a 'Year' column
        if 'Year' in dfcompaniesyear.columns:
            years = pd.to_numeric(dfcompaniesyear['Year'], errors='coerce').dropna().astype(int)
        else:
            years = pd.to_numeric(dfcompaniesyear.astype(str).str.extract(r'(\d{4})')[0], errors='coerce').dropna().astype(int)
        years_with_full_data = sorted(years.unique())

    # Get most recent full year from available data
    most_recent_full_year = years_with_full_data[-1]
    
    # Calculate forecast years as +1 and +2
    forecast_year_1 = most_recent_full_year + 1
    forecast_year_2 = most_recent_full_year + 2
    
    return most_recent_full_year, forecast_year_1, forecast_year_2

def get_forecast_year_list() -> List[int]:
    """
    Get list of forecast years.
    
    Returns:
        List of forecast years [forecast_year_1, forecast_year_2]
    """
    _, year1, year2 = get_forecast_years()
    return [year1, year2]

def is_forecast_year(year: int) -> bool:
    """
    Check if a given year is a forecast year.
    
    Args:
        year: Year to check
        
    Returns:
        True if year is a forecast year, False otherwise
    """
    forecast_years = get_forecast_year_list()
    return year in forecast_years

def get_historical_years_range() -> str:
    """
    Get a string representation of the historical years range.
    
    Returns:
        String like "2018-2024" representing the historical data range
    """
    most_recent, _, _ = get_forecast_years()
    # Derive start year from available Parquet if possible
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        year_path = os.path.join(project_root, 'Data', 'dfsectoryear.parquet')
        if os.path.exists(year_path):
            df_year = pd.read_parquet(year_path)
            start = int(pd.to_numeric(df_year['Year'], errors='coerce').dropna().astype(int).min())
        else:
            quarter_path = os.path.join(project_root, 'Data', 'dfsectorquarter.parquet')
            df_quarter = pd.read_parquet(quarter_path)
            years = pd.to_numeric(df_quarter['Date_Quarter'].astype(str).str.extract(r'(\d{4})')[0], errors='coerce').dropna().astype(int)
            start = int(years.min())
    except Exception:
        start = most_recent - 6  # flexible 7-year default window
    return f"{start}-{most_recent}"

def get_forecast_years_range() -> str:
    """
    Get a string representation of the forecast years range.
    
    Returns:
        String like "2025-2026" representing the forecast years
    """
    _, year1, year2 = get_forecast_years()
    return f"{year1}-{year2}"
