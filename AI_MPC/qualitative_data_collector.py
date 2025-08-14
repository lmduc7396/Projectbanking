#%% Import libraries
from typing import List, Dict, Any
import pandas as pd
import os

def collect_qualitative_data(tickers: List[str], timeframe: List[str], qualitative_handler, need_components: bool = False) -> str:
    """
    Collect qualitative data for all tickers
    
    Args:
        tickers: List of ticker symbols or sector names
        timeframe: List of quarters
        qualitative_handler: QualitativeDataHandler instance
        need_components: If True and ticker is a sector, also get individual bank data
    
    Returns:
        Combined qualitative data string
    """
    
    all_qualitative_data = []
    processed_tickers = set()  # Track processed tickers to avoid duplicates
    
    # If need_components is True and we have a sector, get banks from that sector
    if need_components:
        # Load banking comments to get bank-sector mapping from SECTOR column
        try:
            comments_path = os.path.join(qualitative_handler.data_dir, 'banking_comments.xlsx')
            if os.path.exists(comments_path):
                comments_df = pd.read_excel(comments_path)
                
                # Process each ticker
                for ticker in tickers:
                    if ticker in processed_tickers:
                        continue
                    
                    # Check if it's a sector by checking if this ticker has SECTOR='Sector'
                    is_sector = False
                    if 'SECTOR' in comments_df.columns:
                        sector_entries = comments_df[comments_df['TICKER'] == ticker]
                        if not sector_entries.empty:
                            # If this ticker has SECTOR='Sector', it's a sector-level ticker
                            is_sector = sector_entries['SECTOR'].iloc[0] == 'Sector'
                    
                    if is_sector:
                        # Get sector-level analysis first
                        sector_data = qualitative_handler.format_qualitative_data(
                            ticker=ticker,
                            timeframe=timeframe,
                            is_sector=True
                        )
                        all_qualitative_data.append(f"=== SECTOR OVERVIEW: {ticker} ===\n{sector_data}")
                        processed_tickers.add(ticker)
                        
                        # Get all individual banks in this sector from the SECTOR column
                        # Filter for banks where SECTOR matches the ticker but TICKER is not the sector itself
                        sector_banks = comments_df[
                            (comments_df['SECTOR'] == ticker) & 
                            (comments_df['TICKER'] != ticker)
                        ]['TICKER'].unique()
                        
                        if len(sector_banks) > 0:
                            all_qualitative_data.append(f"\n=== INDIVIDUAL BANKS IN {ticker} ===")
                            for bank in sector_banks:
                                if bank not in processed_tickers:
                                    bank_data = qualitative_handler.format_qualitative_data(
                                        ticker=bank,
                                        timeframe=timeframe,
                                        is_sector=False
                                    )
                                    all_qualitative_data.append(bank_data)
                                    processed_tickers.add(bank)
                    else:
                        # Individual bank - process normally
                        ticker_data = qualitative_handler.format_qualitative_data(
                            ticker=ticker,
                            timeframe=timeframe,
                            is_sector=is_sector  # Use the detected is_sector value
                        )
                        all_qualitative_data.append(ticker_data)
                        processed_tickers.add(ticker)
            else:
                # Fallback if file doesn't exist - process without components
                for ticker in tickers:
                    if ticker not in processed_tickers:
                        # Without the data file, we can't determine if it's a sector
                        ticker_data = qualitative_handler.format_qualitative_data(
                            ticker=ticker,
                            timeframe=timeframe,
                            is_sector=False  # Default to False without data
                        )
                        all_qualitative_data.append(ticker_data)
                        processed_tickers.add(ticker)
        except Exception as e:
            print(f"Error processing with components: {str(e)}")
            # Fallback to simple processing
            for ticker in tickers:
                if ticker not in processed_tickers:
                    ticker_data = qualitative_handler.format_qualitative_data(
                        ticker=ticker,
                        timeframe=timeframe,
                        is_sector=False  # Default to False on error
                    )
                    all_qualitative_data.append(ticker_data)
                    processed_tickers.add(ticker)
    else:
        # Simple processing without components - need to detect if sector
        try:
            comments_path = os.path.join(qualitative_handler.data_dir, 'banking_comments.xlsx')
            if os.path.exists(comments_path):
                comments_df = pd.read_excel(comments_path)
                
                for ticker in tickers:
                    if ticker not in processed_tickers:
                        # Check if it's a sector
                        is_sector = False
                        if 'SECTOR' in comments_df.columns:
                            sector_entries = comments_df[comments_df['TICKER'] == ticker]
                            if not sector_entries.empty:
                                is_sector = sector_entries['SECTOR'].iloc[0] == 'Sector'
                        
                        ticker_data = qualitative_handler.format_qualitative_data(
                            ticker=ticker,
                            timeframe=timeframe,
                            is_sector=is_sector
                        )
                        all_qualitative_data.append(ticker_data)
                        processed_tickers.add(ticker)
            else:
                # No data file available
                for ticker in tickers:
                    if ticker not in processed_tickers:
                        ticker_data = qualitative_handler.format_qualitative_data(
                            ticker=ticker,
                            timeframe=timeframe,
                            is_sector=False
                        )
                        all_qualitative_data.append(ticker_data)
                        processed_tickers.add(ticker)
        except Exception as e:
            print(f"Error in simple processing: {str(e)}")
            # Final fallback
            for ticker in tickers:
                if ticker not in processed_tickers:
                    ticker_data = qualitative_handler.format_qualitative_data(
                        ticker=ticker,
                        timeframe=timeframe,
                        is_sector=False
                    )
                    all_qualitative_data.append(ticker_data)
                    processed_tickers.add(ticker)
    
    # Combine all data
    return "\n\n".join(all_qualitative_data)


def collect_qualitative_data_batch(tickers: List[str], timeframe: List[str], qualitative_handler, need_components: bool = False) -> str:
    """
    Collect qualitative data for all tickers using batch processing
    Retrieves all data in one pass and processes together
    
    Args:
        tickers: List of ticker symbols or sector names
        timeframe: List of quarters
        qualitative_handler: QualitativeDataHandler instance
        need_components: If True and ticker is a sector, also get individual bank data
    
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
        
        # First, determine which tickers to fetch
        tickers_to_fetch = list(tickers)  # Start with original tickers
        
        # If need_components, expand tickers to include banks in sectors
        if need_components:
            expanded_tickers = []
            for ticker in tickers:
                expanded_tickers.append(ticker)
                
                # Check if this ticker is a sector
                is_sector = False
                if 'SECTOR' in comments_df.columns:
                    sector_entries = comments_df[comments_df['TICKER'] == ticker]
                    if not sector_entries.empty:
                        is_sector = sector_entries['SECTOR'].iloc[0] == 'Sector'
                
                if is_sector:
                    # Get all banks with this sector in SECTOR column
                    sector_banks = comments_df[
                        (comments_df['SECTOR'] == ticker) & 
                        (comments_df['TICKER'] != ticker)
                    ]['TICKER'].unique().tolist()
                    expanded_tickers.extend(sector_banks)
            
            # Remove duplicates
            tickers_to_fetch = list(dict.fromkeys(expanded_tickers))
        
        # Normalize tickers for matching
        tickers_upper = [t.upper() for t in tickers_to_fetch]
        
        # Filter for all relevant tickers at once
        mask = comments_df['TICKER'].str.upper().isin(tickers_upper)
        if timeframe:
            mask = mask & comments_df['QUARTER'].isin(timeframe)
        
        filtered_df = comments_df[mask]
        
        # Group by ticker and format
        all_qualitative_data = []
        
        # Process sectors first if need_components
        if need_components:
            for ticker in tickers:
                ticker_upper = ticker.upper()
                
                # Check if it's a sector dynamically
                is_sector = False
                if 'SECTOR' in comments_df.columns:
                    sector_entries = comments_df[comments_df['TICKER'] == ticker]
                    if not sector_entries.empty:
                        is_sector = sector_entries['SECTOR'].iloc[0] == 'Sector'
                
                if is_sector:
                    # Add sector overview
                    sector_data = filtered_df[filtered_df['TICKER'].str.upper() == ticker_upper]
                    if not sector_data.empty:
                        formatted_text = f"=== SECTOR OVERVIEW: {ticker} ===\n"
                        for _, row in sector_data.iterrows():
                            formatted_text += f"\n{row.get('QUARTER', 'N/A')}: {row.get('COMMENT', 'N/A')}\n"
                        all_qualitative_data.append(formatted_text)
                    
                    # Add individual banks in sector
                    sector_banks = filtered_df[
                        (filtered_df['SECTOR'] == ticker) & 
                        (filtered_df['TICKER'] != ticker)
                    ]['TICKER'].unique()
                    
                    if len(sector_banks) > 0:
                        all_qualitative_data.append(f"\n=== INDIVIDUAL BANKS IN {ticker} ===")
                        for bank in sector_banks:
                            bank_data = filtered_df[filtered_df['TICKER'] == bank]
                            if not bank_data.empty:
                                formatted_text = f"\n=== {bank} Bank Analysis ===\n"
                                bank_data = bank_data.sort_values('QUARTER')
                                for _, row in bank_data.iterrows():
                                    formatted_text += f"\n{row.get('QUARTER', 'N/A')}: {row.get('COMMENT', 'N/A')}\n"
                                all_qualitative_data.append(formatted_text)
        else:
            # Normal processing without components
            for ticker in tickers:
                ticker_upper = ticker.upper()
                
                # Check if it's a sector dynamically
                is_sector = False
                if 'SECTOR' in comments_df.columns:
                    sector_entries = comments_df[comments_df['TICKER'] == ticker]
                    if not sector_entries.empty:
                        is_sector = sector_entries['SECTOR'].iloc[0] == 'Sector'
                
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
        return collect_qualitative_data(tickers, timeframe, qualitative_handler, need_components)