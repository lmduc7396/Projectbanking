#%% Import libraries
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import os
from typing import Dict, Any, Optional, List

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
        - pb_full_cdf: P/B full history CDF
        - pb_full_zscore: P/B full history Z-score
        - pe_1y_cdf: P/E 1-year CDF
        - pe_1y_zscore: P/E 1-year Z-score
        - pe_full_cdf: P/E full history CDF
        - pe_full_zscore: P/E full history Z-score
        - sector_pb: Sector's current P/B ratio (if ticker provided)
        - sector_pe: Sector's current P/E ratio (if ticker provided)
        - sector_pb_1y_cdf: Sector's P/B 1-year CDF (if ticker provided)
        - sector_pb_1y_zscore: Sector's P/B 1-year Z-score (if ticker provided)
        - sector_pb_full_cdf: Sector's P/B full history CDF (if ticker provided)
        - sector_pb_full_zscore: Sector's P/B full history Z-score (if ticker provided)
        - sector_pe_1y_cdf: Sector's P/E 1-year CDF (if ticker provided)
        - sector_pe_1y_zscore: Sector's P/E 1-year Z-score (if ticker provided)
        - sector_pe_full_cdf: Sector's P/E full history CDF (if ticker provided)
        - sector_pe_full_zscore: Sector's P/E full history Z-score (if ticker provided)
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
    
    # Initialize result dictionary
    result = {
        'ticker': ticker_or_sector,
        'latest_date': latest_date.strftime('%Y-%m-%d'),
        'current_pb': round(current_pb, 4),
        'current_pe': round(current_pe, 4)
    }
    
    # Calculate metrics for P/B ratio
    pb_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PX_TO_BOOK_RATIO'].dropna()
    pb_full = filtered_df['PX_TO_BOOK_RATIO'].dropna()
    
    # P/B 1-year metrics
    if len(pb_1y) > 1:
        result['pb_1y_cdf'] = round(stats.percentileofscore(pb_1y, current_pb, kind='rank') / 100, 4)
        result['pb_1y_zscore'] = round((current_pb - pb_1y.mean()) / pb_1y.std() if pb_1y.std() > 0 else 0, 4)
    else:
        result['pb_1y_cdf'] = None
        result['pb_1y_zscore'] = None
    
    # P/B full history metrics
    if len(pb_full) > 1:
        result['pb_full_cdf'] = round(stats.percentileofscore(pb_full, current_pb, kind='rank') / 100, 4)
        result['pb_full_zscore'] = round((current_pb - pb_full.mean()) / pb_full.std() if pb_full.std() > 0 else 0, 4)
    else:
        result['pb_full_cdf'] = None
        result['pb_full_zscore'] = None
    
    # Calculate metrics for P/E ratio
    pe_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PE_RATIO'].dropna()
    pe_full = filtered_df['PE_RATIO'].dropna()
    
    # P/E 1-year metrics
    if len(pe_1y) > 1:
        result['pe_1y_cdf'] = round(stats.percentileofscore(pe_1y, current_pe, kind='rank') / 100, 4)
        result['pe_1y_zscore'] = round((current_pe - pe_1y.mean()) / pe_1y.std() if pe_1y.std() > 0 else 0, 4)
    else:
        result['pe_1y_cdf'] = None
        result['pe_1y_zscore'] = None
    
    # P/E full history metrics
    if len(pe_full) > 1:
        result['pe_full_cdf'] = round(stats.percentileofscore(pe_full, current_pe, kind='rank') / 100, 4)
        result['pe_full_zscore'] = round((current_pe - pe_full.mean()) / pe_full.std() if pe_full.std() > 0 else 0, 4)
    else:
        result['pe_full_cdf'] = None
        result['pe_full_zscore'] = None
    
    # Calculate sector valuation if ticker is provided (not a sector)
    if ticker_or_sector not in ['Private_1', 'Private_2', 'Private_3', 'SOCB', 'Sector']:
        # Get the sector type for this ticker
        ticker_sector = df[df['TICKER'] == ticker_or_sector]['Type'].iloc[0] if not df[df['TICKER'] == ticker_or_sector].empty else None
        
        if ticker_sector:
            # Get sector data
            sector_df = df[df['Type'] == ticker_sector].copy()
            sector_df = sector_df.sort_values('TRADE_DATE')
            
            # Get sector's latest values
            sector_latest = sector_df[sector_df['TRADE_DATE'] == latest_date]
            if not sector_latest.empty:
                # Calculate average P/B and P/E for the sector
                sector_pb_current = sector_latest['PX_TO_BOOK_RATIO'].mean()
                sector_pe_current = sector_latest['PE_RATIO'].mean()
                
                result['sector'] = ticker_sector
                result['sector_pb'] = round(sector_pb_current, 4)
                result['sector_pe'] = round(sector_pe_current, 4)
                
                # Calculate historical sector averages for different periods
                sector_1y = sector_df[sector_df['TRADE_DATE'] >= one_year_ago]
                sector_full = sector_df
                
                # Group by date and calculate average P/B and P/E for each date
                sector_pb_1y = sector_1y.groupby('TRADE_DATE')['PX_TO_BOOK_RATIO'].mean().dropna()
                sector_pb_full = sector_full.groupby('TRADE_DATE')['PX_TO_BOOK_RATIO'].mean().dropna()
                sector_pe_1y = sector_1y.groupby('TRADE_DATE')['PE_RATIO'].mean().dropna()
                sector_pe_full = sector_full.groupby('TRADE_DATE')['PE_RATIO'].mean().dropna()
                
                # Calculate sector P/B metrics
                if len(sector_pb_1y) > 1:
                    result['sector_pb_1y_cdf'] = round(stats.percentileofscore(sector_pb_1y, sector_pb_current, kind='rank') / 100, 4)
                    result['sector_pb_1y_zscore'] = round((sector_pb_current - sector_pb_1y.mean()) / sector_pb_1y.std() if sector_pb_1y.std() > 0 else 0, 4)
                else:
                    result['sector_pb_1y_cdf'] = None
                    result['sector_pb_1y_zscore'] = None
                
                if len(sector_pb_full) > 1:
                    result['sector_pb_full_cdf'] = round(stats.percentileofscore(sector_pb_full, sector_pb_current, kind='rank') / 100, 4)
                    result['sector_pb_full_zscore'] = round((sector_pb_current - sector_pb_full.mean()) / sector_pb_full.std() if sector_pb_full.std() > 0 else 0, 4)
                else:
                    result['sector_pb_full_cdf'] = None
                    result['sector_pb_full_zscore'] = None
                
                # Calculate sector P/E metrics
                if len(sector_pe_1y) > 1:
                    result['sector_pe_1y_cdf'] = round(stats.percentileofscore(sector_pe_1y, sector_pe_current, kind='rank') / 100, 4)
                    result['sector_pe_1y_zscore'] = round((sector_pe_current - sector_pe_1y.mean()) / sector_pe_1y.std() if sector_pe_1y.std() > 0 else 0, 4)
                else:
                    result['sector_pe_1y_cdf'] = None
                    result['sector_pe_1y_zscore'] = None
                
                if len(sector_pe_full) > 1:
                    result['sector_pe_full_cdf'] = round(stats.percentileofscore(sector_pe_full, sector_pe_current, kind='rank') / 100, 4)
                    result['sector_pe_full_zscore'] = round((sector_pe_current - sector_pe_full.mean()) / sector_pe_full.std() if sector_pe_full.std() > 0 else 0, 4)
                else:
                    result['sector_pe_full_cdf'] = None
                    result['sector_pe_full_zscore'] = None
    
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


def calculate_valuation_metrics_batch(tickers: List[str], 
                                     data_path: str = 'Data/Valuation_banking.csv') -> Dict[str, Dict[str, Any]]:
    """
    Calculate valuation metrics for multiple tickers in batch
    Loads data once and processes all tickers together
    
    Args:
        tickers: List of stock tickers or sector names
        data_path: Path to valuation data file
    
    Returns:
        Dictionary with ticker as key and metrics dictionary as value
    """
    
    if not tickers:
        return {}
    
    # Check if data file exists
    if not os.path.exists(data_path):
        return {'error': f'Data file not found: {data_path}'}
    
    # Load data once
    df = pd.read_csv(data_path)
    df['TRADE_DATE'] = pd.to_datetime(df['TRADE_DATE'])
    df = df.sort_values(['TICKER', 'TRADE_DATE'])
    
    # Get latest date
    latest_date = df['TRADE_DATE'].max()
    one_year_ago = latest_date - timedelta(days=365)
    
    results = {}
    
    # Process all tickers
    for ticker_or_sector in tickers:
        # Filter data based on input type
        if ticker_or_sector in ['Private_1', 'Private_2', 'Private_3', 'SOCB', 'Sector']:
            filtered_df = df[df['Type'] == ticker_or_sector].copy()
        else:
            filtered_df = df[df['TICKER'] == ticker_or_sector].copy()
        
        if filtered_df.empty:
            results[ticker_or_sector] = {'error': f'No data found for {ticker_or_sector}'}
            continue
        
        # Get current values
        current_data = filtered_df[filtered_df['TRADE_DATE'] == latest_date]
        if current_data.empty:
            results[ticker_or_sector] = {'error': f'No current data for {ticker_or_sector}'}
            continue
            
        current_data = current_data.iloc[0]
        current_pb = current_data['PX_TO_BOOK_RATIO']
        current_pe = current_data['PE_RATIO']
        
        # Initialize result dictionary
        result = {
            'ticker': ticker_or_sector,
            'latest_date': latest_date.strftime('%Y-%m-%d'),
            'current_pb': round(current_pb, 4),
            'current_pe': round(current_pe, 4)
        }
        
        # Calculate metrics for P/B ratio
        pb_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PX_TO_BOOK_RATIO'].dropna()
        pb_full = filtered_df['PX_TO_BOOK_RATIO'].dropna()
        
        # P/B metrics
        if len(pb_1y) > 1:
            result['pb_1y_cdf'] = round(stats.percentileofscore(pb_1y, current_pb, kind='rank') / 100, 4)
            result['pb_1y_zscore'] = round((current_pb - pb_1y.mean()) / pb_1y.std() if pb_1y.std() > 0 else 0, 4)
        else:
            result['pb_1y_cdf'] = None
            result['pb_1y_zscore'] = None
        
        if len(pb_full) > 1:
            result['pb_full_cdf'] = round(stats.percentileofscore(pb_full, current_pb, kind='rank') / 100, 4)
            result['pb_full_zscore'] = round((current_pb - pb_full.mean()) / pb_full.std() if pb_full.std() > 0 else 0, 4)
        else:
            result['pb_full_cdf'] = None
            result['pb_full_zscore'] = None
        
        # Calculate metrics for P/E ratio
        pe_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PE_RATIO'].dropna()
        pe_full = filtered_df['PE_RATIO'].dropna()
        
        # P/E metrics
        if len(pe_1y) > 1:
            result['pe_1y_cdf'] = round(stats.percentileofscore(pe_1y, current_pe, kind='rank') / 100, 4)
            result['pe_1y_zscore'] = round((current_pe - pe_1y.mean()) / pe_1y.std() if pe_1y.std() > 0 else 0, 4)
        else:
            result['pe_1y_cdf'] = None
            result['pe_1y_zscore'] = None
        
        if len(pe_full) > 1:
            result['pe_full_cdf'] = round(stats.percentileofscore(pe_full, current_pe, kind='rank') / 100, 4)
            result['pe_full_zscore'] = round((current_pe - pe_full.mean()) / pe_full.std() if pe_full.std() > 0 else 0, 4)
        else:
            result['pe_full_cdf'] = None
            result['pe_full_zscore'] = None
        
        # Calculate sector valuation if ticker is provided (not a sector)
        if ticker_or_sector not in ['Private_1', 'Private_2', 'Private_3', 'SOCB', 'Sector']:
            # Get the sector type for this ticker
            ticker_sector = df[df['TICKER'] == ticker_or_sector]['Type'].iloc[0] if not df[df['TICKER'] == ticker_or_sector].empty else None
            
            if ticker_sector:
                # Get sector data
                sector_df = df[df['Type'] == ticker_sector].copy()
                sector_df = sector_df.sort_values('TRADE_DATE')
                
                # Get sector's latest values
                sector_latest = sector_df[sector_df['TRADE_DATE'] == latest_date]
                if not sector_latest.empty:
                    # Calculate average P/B and P/E for the sector
                    sector_pb_current = sector_latest['PX_TO_BOOK_RATIO'].mean()
                    sector_pe_current = sector_latest['PE_RATIO'].mean()
                    
                    result['sector'] = ticker_sector
                    result['sector_pb'] = round(sector_pb_current, 4)
                    result['sector_pe'] = round(sector_pe_current, 4)
                    
                    # Calculate historical sector averages for different periods
                    sector_1y = sector_df[sector_df['TRADE_DATE'] >= one_year_ago]
                    sector_full = sector_df
                    
                    # Group by date and calculate average P/B and P/E for each date
                    sector_pb_1y = sector_1y.groupby('TRADE_DATE')['PX_TO_BOOK_RATIO'].mean().dropna()
                    sector_pb_full = sector_full.groupby('TRADE_DATE')['PX_TO_BOOK_RATIO'].mean().dropna()
                    sector_pe_1y = sector_1y.groupby('TRADE_DATE')['PE_RATIO'].mean().dropna()
                    sector_pe_full = sector_full.groupby('TRADE_DATE')['PE_RATIO'].mean().dropna()
                    
                    # Calculate sector P/B metrics
                    if len(sector_pb_1y) > 1:
                        result['sector_pb_1y_cdf'] = round(stats.percentileofscore(sector_pb_1y, sector_pb_current, kind='rank') / 100, 4)
                        result['sector_pb_1y_zscore'] = round((sector_pb_current - sector_pb_1y.mean()) / sector_pb_1y.std() if sector_pb_1y.std() > 0 else 0, 4)
                    else:
                        result['sector_pb_1y_cdf'] = None
                        result['sector_pb_1y_zscore'] = None
                    
                    if len(sector_pb_full) > 1:
                        result['sector_pb_full_cdf'] = round(stats.percentileofscore(sector_pb_full, sector_pb_current, kind='rank') / 100, 4)
                        result['sector_pb_full_zscore'] = round((sector_pb_current - sector_pb_full.mean()) / sector_pb_full.std() if sector_pb_full.std() > 0 else 0, 4)
                    else:
                        result['sector_pb_full_cdf'] = None
                        result['sector_pb_full_zscore'] = None
                    
                    # Calculate sector P/E metrics
                    if len(sector_pe_1y) > 1:
                        result['sector_pe_1y_cdf'] = round(stats.percentileofscore(sector_pe_1y, sector_pe_current, kind='rank') / 100, 4)
                        result['sector_pe_1y_zscore'] = round((sector_pe_current - sector_pe_1y.mean()) / sector_pe_1y.std() if sector_pe_1y.std() > 0 else 0, 4)
                    else:
                        result['sector_pe_1y_cdf'] = None
                        result['sector_pe_1y_zscore'] = None
                    
                    if len(sector_pe_full) > 1:
                        result['sector_pe_full_cdf'] = round(stats.percentileofscore(sector_pe_full, sector_pe_current, kind='rank') / 100, 4)
                        result['sector_pe_full_zscore'] = round((sector_pe_current - sector_pe_full.mean()) / sector_pe_full.std() if sector_pe_full.std() > 0 else 0, 4)
                    else:
                        result['sector_pe_full_cdf'] = None
                        result['sector_pe_full_zscore'] = None
        
        results[ticker_or_sector] = result
    
    return results
