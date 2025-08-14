#%% Import libraries
import pandas as pd
import os
from typing import Dict, List, Any, Optional

class QualitativeDataHandler:
    
    def __init__(self, data_dir: str = 'Data'):
        self.data_dir = data_dir
        self.comments_cache = None
    
    def normalize_ticker(self, ticker: str) -> str:
        """Normalize ticker for case-insensitive matching"""
        if not ticker:
            return ticker
        
        # Handle common variations
        ticker_upper = ticker.upper()
        
        # Map common variations to standard format
        ticker_map = {
            'SECTOR': 'Sector',
            'SOCB': 'SOCB',
            'PRIVATE_1': 'Private_1',
            'PRIVATE_2': 'Private_2',
            'PRIVATE_3': 'Private_3'
        }
        
        # Return mapped version if it exists, otherwise return uppercase
        return ticker_map.get(ticker_upper, ticker_upper)
    
    def get_banking_comment(self, ticker: str, timeframe: List[str]) -> Dict[str, Any]:
        """Get banking comments for a specific bank/sector and timeframe"""
        try:
            # Load banking_comments.xlsx if not cached
            if self.comments_cache is None:
                comments_path = os.path.join(self.data_dir, 'banking_comments.xlsx')
                if os.path.exists(comments_path):
                    self.comments_cache = pd.read_excel(comments_path)
                else:
                    return {'found': False, 'error': 'banking_comments.xlsx not found'}
            
            df = self.comments_cache
            
            # Normalize ticker for case-insensitive matching
            normalized_ticker = self.normalize_ticker(ticker)
            
            # Filter by ticker (case-insensitive)
            if normalized_ticker and 'TICKER' in df.columns:
                # Try exact match first
                df_filtered = df[df['TICKER'] == normalized_ticker]
                
                # If no exact match, try case-insensitive match
                if df_filtered.empty:
                    df_filtered = df[df['TICKER'].str.upper() == normalized_ticker.upper()]
                
                df = df_filtered
            
            # Filter by timeframe (quarters)
            if timeframe and 'QUARTER' in df.columns:
                df = df[df['QUARTER'].isin(timeframe)]
            
            if df.empty:
                return {
                    'found': False,
                    'message': f'No comments found for {ticker} in quarters {timeframe}'
                }
            
            # Get the comments
            comments = []
            for _, row in df.iterrows():
                comments.append({
                    'ticker': row.get('TICKER', ''),
                    'quarter': row.get('QUARTER', ''),
                    'comment': row.get('COMMENT', ''),
                    'generated_at': str(row.get('GENERATED_AT', ''))
                })
            
            return {
                'found': True,
                'comments': comments,
                'count': len(comments)
            }
            
        except Exception as e:
            return {'found': False, 'error': str(e)}
    
    def format_qualitative_data(self, ticker: str, timeframe: List[str], is_sector: bool = False) -> str:
        """Format qualitative data for OpenAI prompt - uses banking_comments for all entities"""
        
        # Normalize ticker for comparison
        normalized_ticker = self.normalize_ticker(ticker)
        
        # List of sector tickers (case-insensitive check)
        sector_tickers = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
        sector_tickers_upper = [s.upper() for s in sector_tickers]
        
        # Determine if it's a sector (case-insensitive)
        is_sector_ticker = normalized_ticker.upper() in sector_tickers_upper
        
        # Always use banking_comments for both individual banks and sectors
        result = self.get_banking_comment(ticker, timeframe)
        
        if result['found']:
            # Determine entity type for formatting
            entity_type = "SECTOR" if (is_sector or is_sector_ticker) else "BANK"
            
            # Use the normalized ticker for display
            display_ticker = normalized_ticker if normalized_ticker else ticker
            
            formatted = f"{entity_type} ANALYSIS FOR {display_ticker}:\n\n"
            for comment in result['comments']:
                formatted += f"Quarter: {comment['quarter']}\n"
                formatted += f"Analysis:\n{comment['comment']}\n"
                formatted += "-" * 80 + "\n\n"
            return formatted
        else:
            return f"No analysis available for {ticker} in quarters: {timeframe}"