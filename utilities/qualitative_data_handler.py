#%% Import libraries
import pandas as pd
import os
from typing import Dict, List, Any, Optional

class QualitativeDataHandler:
    
    def __init__(self, data_dir: str = 'Data'):
        self.data_dir = data_dir
        self.comments_cache = None
        self.analysis_cache = None
    
    def get_banking_comment(self, ticker: str, timeframe: List[str]) -> Dict[str, Any]:
        """Get banking comments for a specific bank and timeframe"""
        try:
            # Load banking_comments.xlsx if not cached
            if self.comments_cache is None:
                comments_path = os.path.join(self.data_dir, 'banking_comments.xlsx')
                if os.path.exists(comments_path):
                    self.comments_cache = pd.read_excel(comments_path)
                else:
                    return {'found': False, 'error': 'banking_comments.xlsx not found'}
            
            df = self.comments_cache
            
            # Filter by ticker
            if ticker and 'TICKER' in df.columns:
                df = df[df['TICKER'] == ticker]
            
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
    
    def get_quarterly_analysis(self, timeframe: List[str]) -> Dict[str, Any]:
        """Get quarterly analysis for sector-level data"""
        try:
            # Load quarterly_analysis_results.xlsx if not cached
            if self.analysis_cache is None:
                analysis_path = os.path.join(self.data_dir, 'quarterly_analysis_results.xlsx')
                if os.path.exists(analysis_path):
                    self.analysis_cache = pd.read_excel(analysis_path)
                else:
                    return {'found': False, 'error': 'quarterly_analysis_results.xlsx not found'}
            
            df = self.analysis_cache
            
            # Filter by timeframe (quarters)
            if timeframe and 'QUARTER' in df.columns:
                df = df[df['QUARTER'].isin(timeframe)]
            
            if df.empty:
                return {
                    'found': False,
                    'message': f'No analysis found for quarters {timeframe}'
                }
            
            # Get the analysis
            analyses = []
            for _, row in df.iterrows():
                analyses.append({
                    'quarter': row.get('QUARTER', ''),
                    'bank_count': row.get('BANK_COUNT', ''),
                    'key_changes': row.get('KEY_CHANGES', ''),
                    'individual_highlights': row.get('INDIVIDUAL_HIGHLIGHTS', ''),
                    'forward_outlook': row.get('FORWARD_OUTLOOK', ''),
                    'full_analysis': row.get('FULL_ANALYSIS', ''),
                    'generated_at': str(row.get('GENERATED_AT', ''))
                })
            
            return {
                'found': True,
                'analyses': analyses,
                'count': len(analyses)
            }
            
        except Exception as e:
            return {'found': False, 'error': str(e)}
    
    def format_qualitative_data(self, ticker: str, timeframe: List[str], is_sector: bool = False) -> str:
        """Format qualitative data for OpenAI prompt"""
        
        if is_sector or ticker in ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']:
            # Get sector analysis
            result = self.get_quarterly_analysis(timeframe)
            
            if result['found']:
                formatted = "QUARTERLY SECTOR ANALYSIS:\n\n"
                for analysis in result['analyses']:
                    formatted += f"Quarter: {analysis['quarter']}\n"
                    formatted += f"Bank Count: {analysis['bank_count']}\n\n"
                    formatted += f"Key Changes:\n{analysis['key_changes']}\n\n"
                    formatted += f"Individual Highlights:\n{analysis['individual_highlights']}\n\n"
                    formatted += f"Forward Outlook:\n{analysis['forward_outlook']}\n\n"
                    formatted += f"Full Analysis:\n{analysis['full_analysis']}\n"
                    formatted += "-" * 80 + "\n\n"
                return formatted
            else:
                return f"No sector analysis available for quarters: {timeframe}"
        
        else:
            # Get individual bank comments
            result = self.get_banking_comment(ticker, timeframe)
            
            if result['found']:
                formatted = f"BANKING COMMENTS FOR {ticker}:\n\n"
                for comment in result['comments']:
                    formatted += f"Quarter: {comment['quarter']}\n"
                    formatted += f"Analysis:\n{comment['comment']}\n"
                    formatted += "-" * 80 + "\n\n"
                return formatted
            else:
                return f"No comments available for {ticker} in quarters: {timeframe}"