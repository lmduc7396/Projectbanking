#%% Import libraries
from typing import List

def collect_qualitative_data(tickers: List[str], timeframe: List[str], qualitative_handler) -> str:
    """
    Collect qualitative data for all tickers
    
    Args:
        tickers: List of ticker symbols or sector names
        timeframe: List of quarters
        qualitative_handler: QualitativeDataHandler instance
    
    Returns:
        Combined qualitative data string
    """
    
    all_qualitative_data = []
    
    for ticker in tickers:
        # Determine if this specific ticker is a sector
        is_sector = ticker in ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
        
        ticker_data = qualitative_handler.format_qualitative_data(
            ticker=ticker,
            timeframe=timeframe,
            is_sector=is_sector
        )
        all_qualitative_data.append(ticker_data)
    
    # Combine all data
    return "\n\n".join(all_qualitative_data)


def collect_qualitative_data_batch(tickers: List[str], timeframe: List[str], qualitative_handler) -> str:
    """
    Collect qualitative data for all tickers using batch processing
    Retrieves all data in one pass and processes together
    
    Args:
        tickers: List of ticker symbols or sector names
        timeframe: List of quarters
        qualitative_handler: QualitativeDataHandler instance
    
    Returns:
        Combined qualitative data string
    """
    if not tickers or not qualitative_handler:
        return ""
    
    import pandas as pd
    
    # Load comments data once
    try:
        comments_path = qualitative_handler.data_dir + '/banking_comments.xlsx'
        comments_df = pd.read_excel(comments_path)
        
        # Normalize tickers for matching
        tickers_upper = [t.upper() for t in tickers]
        sector_tickers = ['SECTOR', 'SOCB', 'PRIVATE_1', 'PRIVATE_2', 'PRIVATE_3']
        
        # Filter for all relevant tickers at once
        mask = comments_df['TICKER'].str.upper().isin(tickers_upper)
        if timeframe:
            mask = mask & comments_df['QUARTER'].isin(timeframe)
        
        filtered_df = comments_df[mask]
        
        # Group by ticker and format
        all_qualitative_data = []
        
        for ticker in tickers:
            ticker_upper = ticker.upper()
            is_sector = ticker_upper in sector_tickers
            
            # Get data for this ticker
            ticker_data = filtered_df[filtered_df['TICKER'].str.upper() == ticker_upper]
            
            if ticker_data.empty:
                all_qualitative_data.append(f"No data available for {ticker} in quarters: {', '.join(timeframe) if timeframe else 'all'}")
                continue
            
            # Format data based on type
            if is_sector:
                # Sector-level analysis
                formatted_text = f"=== {ticker} Sector Analysis ===\n"
                
                # Get quarterly analysis if available
                analysis_path = qualitative_handler.data_dir + '/quarterly_analysis_results.xlsx'
                try:
                    analysis_df = pd.read_excel(analysis_path)
                    if timeframe:
                        analysis_df = analysis_df[analysis_df['QUARTER'].isin(timeframe)]
                    
                    for _, row in analysis_df.iterrows():
                        formatted_text += f"\n{row.get('QUARTER', 'N/A')}:\n"
                        formatted_text += f"Key Changes: {row.get('KEY_CHANGES', 'N/A')}\n"
                        formatted_text += f"Individual Highlights: {row.get('INDIVIDUAL_HIGHLIGHTS', 'N/A')}\n"
                        formatted_text += f"Forward Outlook: {row.get('FORWARD_OUTLOOK', 'N/A')}\n"
                        formatted_text += f"Full Analysis: {row.get('FULL_ANALYSIS', 'N/A')}\n"
                        formatted_text += "-" * 50 + "\n"
                except:
                    pass
                
                # Add sector comments
                for _, row in ticker_data.iterrows():
                    formatted_text += f"\n{row.get('QUARTER', 'N/A')} Comment: {row.get('COMMENT', 'N/A')}\n"
            else:
                # Individual bank comments
                formatted_text = f"=== {ticker} Bank Analysis ===\n"
                
                # Sort by quarter for chronological order
                ticker_data = ticker_data.sort_values('QUARTER')
                
                for _, row in ticker_data.iterrows():
                    formatted_text += f"\n{row.get('QUARTER', 'N/A')}: {row.get('COMMENT', 'N/A')}\n"
            
            all_qualitative_data.append(formatted_text)
        
        return "\n\n".join(all_qualitative_data)
        
    except Exception as e:
        print(f"Error in batch qualitative data collection: {str(e)}")
        # Fallback to original method
        return collect_qualitative_data(tickers, timeframe, qualitative_handler)