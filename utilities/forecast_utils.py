"""
Utility functions for determining forecast years dynamically based on available data.
"""
import pandas as pd
import os
from typing import Tuple, List
from .path_utils import get_data_path

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
        # Try to load BS_Bank data to find most recent full year
        try:
            bs_bank_path = get_data_path('BS_Bank.csv')
            if os.path.exists(bs_bank_path):
                bs_bank = pd.read_csv(bs_bank_path)
                # Filter for full year data (LENGTHREPORT=5)
                full_year_data = bs_bank[bs_bank['LENGTHREPORT'] == 5]
                years_with_full_data = full_year_data['YEARREPORT'].unique()
                years_with_full_data = sorted(years_with_full_data)
            else:
                # Default fallback
                years_with_full_data = [2024]
        except Exception:
            # Default fallback
            years_with_full_data = [2024]
    else:
        # Use provided dataframe
        years_with_full_data = dfcompaniesyear['Date_Quarter'].astype(int).unique()
        years_with_full_data = sorted(years_with_full_data)
    
    # Get most recent full year
    most_recent_full_year = years_with_full_data[-1] if years_with_full_data else 2024
    
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
    # Assuming historical data starts from 2018 based on the data
    return f"2018-{most_recent}"

def get_forecast_years_range() -> str:
    """
    Get a string representation of the forecast years range.
    
    Returns:
        String like "2025-2026" representing the forecast years
    """
    _, year1, year2 = get_forecast_years()
    return f"{year1}-{year2}"