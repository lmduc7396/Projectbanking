#%% Import libraries
from typing import List, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utilities.valuation_tool import calculate_valuation_metrics

def format_valuation_data(tickers: List[str]) -> str:
    """
    Format valuation data for given tickers
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Formatted string with valuation metrics
    """
    valuation_data_text = "\n\nValuation Metrics:\n"
    
    for ticker in tickers:
        try:
            val_metrics = calculate_valuation_metrics(ticker)
            if 'error' not in val_metrics:
                valuation_data_text += f"""
{ticker}:
- Current P/B: {val_metrics['current_pb']}
- Current P/E: {val_metrics['current_pe']}
- P/B 1Y CDF: {val_metrics.get('pb_1y_cdf', 'N/A')}
- P/B 1Y Z-score: {val_metrics.get('pb_1y_zscore', 'N/A')}
- P/B Full CDF: {val_metrics.get('pb_full_cdf', 'N/A')}
- P/B Full Z-score: {val_metrics.get('pb_full_zscore', 'N/A')}
- P/E 1Y CDF: {val_metrics.get('pe_1y_cdf', 'N/A')}
- P/E 1Y Z-score: {val_metrics.get('pe_1y_zscore', 'N/A')}
- P/E Full CDF: {val_metrics.get('pe_full_cdf', 'N/A')}
- P/E Full Z-score: {val_metrics.get('pe_full_zscore', 'N/A')}

Sector ({val_metrics.get('sector', 'N/A')}) Comparison:
- Sector P/B: {val_metrics.get('sector_pb', 'N/A')}
- Sector P/E: {val_metrics.get('sector_pe', 'N/A')}
- Sector P/B 1Y CDF: {val_metrics.get('sector_pb_1y_cdf', 'N/A')}
- Sector P/B 1Y Z-score: {val_metrics.get('sector_pb_1y_zscore', 'N/A')}
- Sector P/B Full CDF: {val_metrics.get('sector_pb_full_cdf', 'N/A')}
- Sector P/B Full Z-score: {val_metrics.get('sector_pb_full_zscore', 'N/A')}
- Sector P/E 1Y CDF: {val_metrics.get('sector_pe_1y_cdf', 'N/A')}
- Sector P/E 1Y Z-score: {val_metrics.get('sector_pe_1y_zscore', 'N/A')}
- Sector P/E Full CDF: {val_metrics.get('sector_pe_full_cdf', 'N/A')}
- Sector P/E Full Z-score: {val_metrics.get('sector_pe_full_zscore', 'N/A')}
"""
        except:
            pass
    
    return valuation_data_text if valuation_data_text != "\n\nValuation Metrics:\n" else ""


def format_valuation_data_batch(tickers: List[str]) -> str:
    """
    Format valuation data for given tickers using batch processing
    Loads data once and processes all tickers together
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Formatted string with valuation metrics
    """
    if not tickers:
        return ""
    
    import pandas as pd
    from datetime import timedelta
    from scipy import stats
    
    valuation_data_text = "\n\nValuation Metrics:\n"
    
    # Load data once
    data_path = 'Data/Valuation_banking.csv'
    try:
        df = pd.read_csv(data_path)
        df['TRADE_DATE'] = pd.to_datetime(df['TRADE_DATE'])
        df = df.sort_values(['TICKER', 'TRADE_DATE'])
        
        # Get latest date
        latest_date = df['TRADE_DATE'].max()
        one_year_ago = latest_date - timedelta(days=365)
        
        # Process all tickers at once
        results = {}
        
        for ticker in tickers:
            # Determine if it's a sector or individual ticker
            if ticker in ['Private_1', 'Private_2', 'Private_3', 'SOCB', 'Sector']:
                filtered_df = df[df['Type'] == ticker].copy()
            else:
                filtered_df = df[df['TICKER'] == ticker].copy()
            
            if filtered_df.empty:
                continue
            
            # Get current values
            current_data = filtered_df[filtered_df['TRADE_DATE'] == latest_date]
            if current_data.empty:
                continue
                
            current_data = current_data.iloc[0]
            current_pb = current_data['PX_TO_BOOK_RATIO']
            current_pe = current_data['PE_RATIO']
            
            # Calculate metrics using vectorized operations
            pb_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PX_TO_BOOK_RATIO'].dropna()
            pb_full = filtered_df['PX_TO_BOOK_RATIO'].dropna()
            pe_1y = filtered_df[filtered_df['TRADE_DATE'] >= one_year_ago]['PE_RATIO'].dropna()
            pe_full = filtered_df['PE_RATIO'].dropna()
            
            result = {
                'ticker': ticker,
                'current_pb': round(current_pb, 4),
                'current_pe': round(current_pe, 4)
            }
            
            # P/B metrics
            if len(pb_1y) > 1:
                result['pb_1y_cdf'] = round(stats.percentileofscore(pb_1y, current_pb, kind='rank') / 100, 4)
                result['pb_1y_zscore'] = round((current_pb - pb_1y.mean()) / pb_1y.std() if pb_1y.std() > 0 else 0, 4)
            
            if len(pb_full) > 1:
                result['pb_full_cdf'] = round(stats.percentileofscore(pb_full, current_pb, kind='rank') / 100, 4)
                result['pb_full_zscore'] = round((current_pb - pb_full.mean()) / pb_full.std() if pb_full.std() > 0 else 0, 4)
            
            # P/E metrics
            if len(pe_1y) > 1:
                result['pe_1y_cdf'] = round(stats.percentileofscore(pe_1y, current_pe, kind='rank') / 100, 4)
                result['pe_1y_zscore'] = round((current_pe - pe_1y.mean()) / pe_1y.std() if pe_1y.std() > 0 else 0, 4)
            
            if len(pe_full) > 1:
                result['pe_full_cdf'] = round(stats.percentileofscore(pe_full, current_pe, kind='rank') / 100, 4)
                result['pe_full_zscore'] = round((current_pe - pe_full.mean()) / pe_full.std() if pe_full.std() > 0 else 0, 4)
            
            # Add sector comparison if it's an individual ticker
            if ticker not in ['Private_1', 'Private_2', 'Private_3', 'SOCB', 'Sector']:
                ticker_sector = df[df['TICKER'] == ticker]['Type'].iloc[0] if not df[df['TICKER'] == ticker].empty else None
                
                if ticker_sector:
                    sector_df = df[df['Type'] == ticker_sector].copy()
                    sector_latest = sector_df[sector_df['TRADE_DATE'] == latest_date]
                    
                    if not sector_latest.empty:
                        sector_pb_current = sector_latest['PX_TO_BOOK_RATIO'].mean()
                        sector_pe_current = sector_latest['PE_RATIO'].mean()
                        
                        result['sector'] = ticker_sector
                        result['sector_pb'] = round(sector_pb_current, 4)
                        result['sector_pe'] = round(sector_pe_current, 4)
                        
                        # Calculate sector metrics
                        sector_1y = sector_df[sector_df['TRADE_DATE'] >= one_year_ago]
                        sector_pb_1y = sector_1y.groupby('TRADE_DATE')['PX_TO_BOOK_RATIO'].mean().dropna()
                        sector_pb_full = sector_df.groupby('TRADE_DATE')['PX_TO_BOOK_RATIO'].mean().dropna()
                        sector_pe_1y = sector_1y.groupby('TRADE_DATE')['PE_RATIO'].mean().dropna()
                        sector_pe_full = sector_df.groupby('TRADE_DATE')['PE_RATIO'].mean().dropna()
                        
                        if len(sector_pb_1y) > 1:
                            result['sector_pb_1y_cdf'] = round(stats.percentileofscore(sector_pb_1y, sector_pb_current, kind='rank') / 100, 4)
                            result['sector_pb_1y_zscore'] = round((sector_pb_current - sector_pb_1y.mean()) / sector_pb_1y.std() if sector_pb_1y.std() > 0 else 0, 4)
                        
                        if len(sector_pb_full) > 1:
                            result['sector_pb_full_cdf'] = round(stats.percentileofscore(sector_pb_full, sector_pb_current, kind='rank') / 100, 4)
                            result['sector_pb_full_zscore'] = round((sector_pb_current - sector_pb_full.mean()) / sector_pb_full.std() if sector_pb_full.std() > 0 else 0, 4)
                        
                        if len(sector_pe_1y) > 1:
                            result['sector_pe_1y_cdf'] = round(stats.percentileofscore(sector_pe_1y, sector_pe_current, kind='rank') / 100, 4)
                            result['sector_pe_1y_zscore'] = round((sector_pe_current - sector_pe_1y.mean()) / sector_pe_1y.std() if sector_pe_1y.std() > 0 else 0, 4)
                        
                        if len(sector_pe_full) > 1:
                            result['sector_pe_full_cdf'] = round(stats.percentileofscore(sector_pe_full, sector_pe_current, kind='rank') / 100, 4)
                            result['sector_pe_full_zscore'] = round((sector_pe_current - sector_pe_full.mean()) / sector_pe_full.std() if sector_pe_full.std() > 0 else 0, 4)
            
            results[ticker] = result
        
        # Format results
        for ticker, metrics in results.items():
            valuation_data_text += f"""
{ticker}:
- Current P/B: {metrics['current_pb']}
- Current P/E: {metrics['current_pe']}
- P/B 1Y CDF: {metrics.get('pb_1y_cdf', 'N/A')}
- P/B 1Y Z-score: {metrics.get('pb_1y_zscore', 'N/A')}
- P/B Full CDF: {metrics.get('pb_full_cdf', 'N/A')}
- P/B Full Z-score: {metrics.get('pb_full_zscore', 'N/A')}
- P/E 1Y CDF: {metrics.get('pe_1y_cdf', 'N/A')}
- P/E 1Y Z-score: {metrics.get('pe_1y_zscore', 'N/A')}
- P/E Full CDF: {metrics.get('pe_full_cdf', 'N/A')}
- P/E Full Z-score: {metrics.get('pe_full_zscore', 'N/A')}
"""
            
            if 'sector' in metrics:
                valuation_data_text += f"""
Sector ({metrics.get('sector', 'N/A')}) Comparison:
- Sector P/B: {metrics.get('sector_pb', 'N/A')}
- Sector P/E: {metrics.get('sector_pe', 'N/A')}
- Sector P/B 1Y CDF: {metrics.get('sector_pb_1y_cdf', 'N/A')}
- Sector P/B 1Y Z-score: {metrics.get('sector_pb_1y_zscore', 'N/A')}
- Sector P/B Full CDF: {metrics.get('sector_pb_full_cdf', 'N/A')}
- Sector P/B Full Z-score: {metrics.get('sector_pb_full_zscore', 'N/A')}
- Sector P/E 1Y CDF: {metrics.get('sector_pe_1y_cdf', 'N/A')}
- Sector P/E 1Y Z-score: {metrics.get('sector_pe_1y_zscore', 'N/A')}
- Sector P/E Full CDF: {metrics.get('sector_pe_full_cdf', 'N/A')}
- Sector P/E Full Z-score: {metrics.get('sector_pe_full_zscore', 'N/A')}
"""
        
    except Exception as e:
        print(f"Error in batch valuation processing: {str(e)}")
        return ""
    
    return valuation_data_text if valuation_data_text != "\n\nValuation Metrics:\n" else ""