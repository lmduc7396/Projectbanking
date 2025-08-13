#%% Import libraries
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import os
from typing import Dict, Any, Optional

#%% Main function to calculate valuation metrics
def calculate_valuation_metrics(ticker_or_sector: str, 
                               data_path: str = 'Data/Valuation_banking.csv') -> Dict[str, Any]:
    """
    Calculate valuation percentiles (CDF) and Z-scores for P/B and P/E ratios
    
    Args:
        ticker_or_sector: Stock ticker (e.g., 'ACB') or sector name (e.g., 'Private_1', 'SOCB')
        data_path: Path to valuation data file
    
    Returns:
        Dictionary with:
        - current_pb: Current P/B ratio
        - current_pe: Current P/E ratio
        - pb_1y_cdf: P/B 1-year cumulative distribution factor (0-1)
        - pb_1y_zscore: P/B 1-year Z-score
        - pb_3y_cdf: P/B 3-year CDF
        - pb_3y_zscore: P/B 3-year Z-score
        - pb_full_cdf: P/B full history CDF
        - pb_full_zscore: P/B full history Z-score
        - pe_1y_cdf: P/E 1-year CDF
        - pe_1y_zscore: P/E 1-year Z-score
        - pe_3y_cdf: P/E 3-year CDF
        - pe_3y_zscore: P/E 3-year Z-score
        - pe_full_cdf: P/E full history CDF
        - pe_full_zscore: P/E full history Z-score
    """
    
    # Check if data file exists
    if not os.path.exists(data_path):
        return {'error': f'Data file not found: {data_path}'}
    
    # Load data
    df = pd.read_csv(data_path)
    df['TRADE_DATE'] = pd.to_datetime(df['TRADE_DATE'])
    df = df.sort_values(['TICKER', 'TRADE_DATE'])
    
    # Filter data based on input type
    if ticker_or_sector in ['Private_1', 'Private_2', 'Private_3', 'SOCB', 'Sector']:
        # It's a sector - filter by Type column
        filtered_df = df[df['Type'] == ticker_or_sector].copy()
    else:
        # It's an individual ticker
        filtered_df = df[df['TICKER'] == ticker_or_sector].copy()
    
    if filtered_df.empty:
        return {'error': f'No data found for {ticker_or_sector}'}
    
    # Get latest date and current values
    latest_date = filtered_df['TRADE_DATE'].max()
    current_data = filtered_df[filtered_df['TRADE_DATE'] == latest_date].iloc[0]
    current_pb = current_data['PX_TO_BOOK_RATIO']
    current_pe = current_data['PE_RATIO']
    
    # Define time periods
    one_year_ago = latest_date - timedelta(days=365)
    three_years_ago = latest_date - timedelta(days=365*3)
    
    # Initialize result dictionary
    result = {
        'ticker': ticker_or_sector,
        'latest_date': latest_date.strftime('%Y-%m-%d'),
        'current_pb': round(current_pb, 4),
        'current_pe': round(current_pe, 4)
    }
    
    # Calculate metrics for P/B ratio
    pb_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PX_TO_BOOK_RATIO'].dropna()
    pb_3y = filtered_df[filtered_df['TRADE_DATE'] >= three_years_ago]['PX_TO_BOOK_RATIO'].dropna()
    pb_full = filtered_df['PX_TO_BOOK_RATIO'].dropna()
    
    # P/B 1-year metrics
    if len(pb_1y) > 1:
        result['pb_1y_cdf'] = round(stats.percentileofscore(pb_1y, current_pb, kind='rank') / 100, 4)
        result['pb_1y_zscore'] = round((current_pb - pb_1y.mean()) / pb_1y.std() if pb_1y.std() > 0 else 0, 4)
    else:
        result['pb_1y_cdf'] = None
        result['pb_1y_zscore'] = None
    
    # P/B 3-year metrics
    if len(pb_3y) > 1:
        result['pb_3y_cdf'] = round(stats.percentileofscore(pb_3y, current_pb, kind='rank') / 100, 4)
        result['pb_3y_zscore'] = round((current_pb - pb_3y.mean()) / pb_3y.std() if pb_3y.std() > 0 else 0, 4)
    else:
        result['pb_3y_cdf'] = None
        result['pb_3y_zscore'] = None
    
    # P/B full history metrics
    if len(pb_full) > 1:
        result['pb_full_cdf'] = round(stats.percentileofscore(pb_full, current_pb, kind='rank') / 100, 4)
        result['pb_full_zscore'] = round((current_pb - pb_full.mean()) / pb_full.std() if pb_full.std() > 0 else 0, 4)
    else:
        result['pb_full_cdf'] = None
        result['pb_full_zscore'] = None
    
    # Calculate metrics for P/E ratio
    pe_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PE_RATIO'].dropna()
    pe_3y = filtered_df[filtered_df['TRADE_DATE'] >= three_years_ago]['PE_RATIO'].dropna()
    pe_full = filtered_df['PE_RATIO'].dropna()
    
    # P/E 1-year metrics
    if len(pe_1y) > 1:
        result['pe_1y_cdf'] = round(stats.percentileofscore(pe_1y, current_pe, kind='rank') / 100, 4)
        result['pe_1y_zscore'] = round((current_pe - pe_1y.mean()) / pe_1y.std() if pe_1y.std() > 0 else 0, 4)
    else:
        result['pe_1y_cdf'] = None
        result['pe_1y_zscore'] = None
    
    # P/E 3-year metrics
    if len(pe_3y) > 1:
        result['pe_3y_cdf'] = round(stats.percentileofscore(pe_3y, current_pe, kind='rank') / 100, 4)
        result['pe_3y_zscore'] = round((current_pe - pe_3y.mean()) / pe_3y.std() if pe_3y.std() > 0 else 0, 4)
    else:
        result['pe_3y_cdf'] = None
        result['pe_3y_zscore'] = None
    
    # P/E full history metrics
    if len(pe_full) > 1:
        result['pe_full_cdf'] = round(stats.percentileofscore(pe_full, current_pe, kind='rank') / 100, 4)
        result['pe_full_zscore'] = round((current_pe - pe_full.mean()) / pe_full.std() if pe_full.std() > 0 else 0, 4)
    else:
        result['pe_full_cdf'] = None
        result['pe_full_zscore'] = None
    
    return result

#%% Function to get historical statistics
def get_valuation_statistics(ticker_or_sector: str, 
                            metric: str = 'PB',
                            data_path: str = 'Data/Valuation_banking.csv') -> Dict[str, Any]:
    """
    Get detailed statistics for a specific valuation metric
    
    Args:
        ticker_or_sector: Stock ticker or sector name
        metric: 'PB' or 'PE'
        data_path: Path to valuation data file
    
    Returns:
        Dictionary with detailed statistics
    """
    
    # Load data
    df = pd.read_csv(data_path)
    df['TRADE_DATE'] = pd.to_datetime(df['TRADE_DATE'])
    
    # Filter data
    if ticker_or_sector in ['Private_1', 'Private_2', 'Private_3', 'SOCB', 'Sector']:
        filtered_df = df[df['Type'] == ticker_or_sector].copy()
    else:
        filtered_df = df[df['TICKER'] == ticker_or_sector].copy()
    
    if filtered_df.empty:
        return {'error': f'No data found for {ticker_or_sector}'}
    
    # Select metric column
    metric_col = 'PX_TO_BOOK_RATIO' if metric == 'PB' else 'PE_RATIO'
    values = filtered_df[metric_col].dropna()
    
    if len(values) < 2:
        return {'error': 'Insufficient data for statistics'}
    
    # Calculate statistics
    return {
        'ticker': ticker_or_sector,
        'metric': metric,
        'count': len(values),
        'mean': round(values.mean(), 4),
        'median': round(values.median(), 4),
        'std': round(values.std(), 4),
        'min': round(values.min(), 4),
        'max': round(values.max(), 4),
        'percentile_25': round(values.quantile(0.25), 4),
        'percentile_75': round(values.quantile(0.75), 4),
        'current': round(values.iloc[-1], 4),
        'date_range': f"{filtered_df['TRADE_DATE'].min().date()} to {filtered_df['TRADE_DATE'].max().date()}"
    }
