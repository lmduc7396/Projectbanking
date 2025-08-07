#%% Import libraries
import pandas as pd
import os
from typing import Dict, List, Any, Optional

class DataDiscoveryAgent:
    
    def __init__(self, data_dir: str = 'Data'):
        self.data_dir = data_dir
        self.data_cache = {}
    
    def find_relevant_data(self, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant data based on query analysis
        - Load either dfsectorquarter.csv or dfsectoryear.csv
        - Filter by tickers, keycodes, and timeframe
        - Return the filtered data
        """
        result = {
            'data_found': False,
            'data_table': None,
            'row_count': 0,
            'column_count': 0,
            'summary': {},
            'error': None
        }
        
        try:
            # Determine which file to load
            data_source = query_analysis.get('data_source', 'dfsectorquarter.csv')
            filepath = os.path.join(self.data_dir, data_source)
            
            # Load the data
            if filepath in self.data_cache:
                df = self.data_cache[filepath].copy()
            else:
                if os.path.exists(filepath):
                    df = pd.read_csv(filepath)
                    self.data_cache[filepath] = df.copy()
                else:
                    result['error'] = f"Data file not found: {filepath}"
                    return result
            
            # Apply filters
            df_filtered = self._apply_filters(df, query_analysis)
            
            if df_filtered is not None and not df_filtered.empty:
                # Select relevant columns
                df_final = self._select_columns(df_filtered, query_analysis)
                
                if not df_final.empty:
                    result['data_found'] = True
                    result['data_table'] = df_final.to_string()
                    result['row_count'] = len(df_final)
                    result['column_count'] = len(df_final.columns)
                    result['summary'] = self._create_summary(df_final, query_analysis)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _apply_filters(self, df: pd.DataFrame, query_analysis: Dict[str, Any]) -> pd.DataFrame:
        """Apply filters for tickers and timeframe"""
        
        # Filter by tickers
        tickers = query_analysis.get('tickers', [])
        if tickers and 'ALL' not in tickers and 'TICKER' in df.columns:
            df = df[df['TICKER'].isin(tickers)]
            print(f"Filtered to {len(tickers)} tickers: {tickers}, rows: {len(df)}")
        
        # Filter by timeframe
        timeframe = query_analysis.get('timeframe', 'LATEST')
        
        if 'Date_Quarter' in df.columns:
            # Quarterly data
            if timeframe != 'LATEST' and 'Q' in timeframe:
                df = df[df['Date_Quarter'] == timeframe]
                print(f"Filtered to quarter {timeframe}, rows: {len(df)}")
            elif timeframe == 'LATEST':
                # Get the latest quarter
                df['_quarter_sort'] = df['Date_Quarter'].apply(self._quarter_to_numeric)
                latest_quarter = df['_quarter_sort'].max()
                df = df[df['_quarter_sort'] == latest_quarter]
                df = df.drop('_quarter_sort', axis=1)
                print(f"Filtered to latest quarter, rows: {len(df)}")
            elif timeframe.isdigit() and len(timeframe) == 4:
                # Year specified but quarterly data - get all quarters of that year
                year_suffix = timeframe[-2:]
                quarters = [f"1Q{year_suffix}", f"2Q{year_suffix}", f"3Q{year_suffix}", f"4Q{year_suffix}"]
                df = df[df['Date_Quarter'].isin(quarters)]
                print(f"Filtered to year {timeframe}, rows: {len(df)}")
        
        elif 'Year' in df.columns:
            # Yearly data
            if timeframe != 'LATEST' and timeframe.isdigit():
                df = df[df['Year'] == int(timeframe)]
                print(f"Filtered to year {timeframe}, rows: {len(df)}")
            elif timeframe == 'LATEST':
                # Get the latest year
                latest_year = df['Year'].max()
                df = df[df['Year'] == latest_year]
                print(f"Filtered to latest year, rows: {len(df)}")
        
        return df
    
    def _select_columns(self, df: pd.DataFrame, query_analysis: Dict[str, Any]) -> pd.DataFrame:
        """Select only relevant columns"""
        
        # Always include identifier columns
        id_cols = []
        for col in ['TICKER', 'Date_Quarter', 'Year', 'Type']:
            if col in df.columns:
                id_cols.append(col)
        
        # Add keycode columns
        keycodes = query_analysis.get('keycodes', [])
        selected_cols = id_cols.copy()
        
        if keycodes:
            # Only include specified keycodes
            for keycode in keycodes:
                if keycode in df.columns:
                    selected_cols.append(keycode)
                else:
                    print(f"Warning: Keycode {keycode} not found in data")
        else:
            # If no specific keycodes, include all CA.* and IS.* columns
            for col in df.columns:
                if col.startswith(('CA.', 'IS.', 'BS.', 'NT.')):
                    selected_cols.append(col)
                    if len(selected_cols) > 20:  # Limit columns if too many
                        break
        
        # Return dataframe with selected columns
        return df[selected_cols] if selected_cols else df
    
    def _quarter_to_numeric(self, quarter_str: str) -> float:
        """Convert quarter string to numeric for sorting"""
        try:
            q = int(quarter_str[0])
            year = 2000 + int(quarter_str[2:4])
            return year + (q - 1) / 4
        except:
            return 0
    
    def _create_summary(self, df: pd.DataFrame, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of the extracted data"""
        summary = {
            'tickers': list(df['TICKER'].unique()) if 'TICKER' in df.columns else [],
            'items': query_analysis.get('items', []),
            'keycodes': query_analysis.get('keycodes', []),
            'timeframe': query_analysis.get('timeframe', ''),
            'data_points': len(df),
            'columns': list(df.columns)
        }
        
        # Add time range info
        if 'Date_Quarter' in df.columns:
            quarters = df['Date_Quarter'].unique()
            summary['quarters'] = sorted(quarters)
        elif 'Year' in df.columns:
            years = df['Year'].unique()
            summary['years'] = sorted(years)
        
        return summary