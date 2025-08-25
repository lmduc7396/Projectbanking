#%% Import libraries
import pandas as pd
import os
from typing import Dict, List, Any, Optional

class DataDiscoveryAgent:
    
    def __init__(self, data_dir: str = 'Data'):
        self.data_dir = data_dir
        self.data_cache = {}
        self.latest_quarter = self._get_latest_quarter()
        
    def _get_latest_quarter(self) -> str:
        """Get the latest quarter from dfsectorquarter.csv"""
        try:
            quarter_file = os.path.join(self.data_dir, 'dfsectorquarter.csv')
            if os.path.exists(quarter_file):
                df = pd.read_csv(quarter_file)
                if 'Date_Quarter' in df.columns:
                    quarters = df['Date_Quarter'].unique()
                    quarters_sorted = sorted(quarters, key=self._quarter_to_numeric)
                    return quarters_sorted[-1] if quarters_sorted else "2025-Q2"
            return "2025-Q2"
        except:
            return "2025-Q2"
    
    def _get_latest_4_quarters(self) -> List[str]:
        """Get the latest 4 quarters based on the latest quarter"""
        try:
            q = int(self.latest_quarter[0])
            year = int(self.latest_quarter[2:4])
            
            quarters = []
            for i in range(3, -1, -1):
                calc_q = q - i
                calc_year = year
                
                while calc_q <= 0:
                    calc_q += 4
                    calc_year -= 1
                
                quarters.append(f"{calc_q}Q{calc_year:02d}")
            
            return quarters
        except:
            return ["2024-Q3", "2024-Q4", "2025-Q1", "2025-Q2"]
    
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
        
        # Filter by tickers/sectors
        tickers = query_analysis.get('tickers', [])
        need_components = query_analysis.get('need_components', False)
        
        if tickers and 'TICKER' in df.columns:
            # Special case: ALL_BANKS means get all individual banks
            if 'ALL_BANKS' in tickers:
                # Get all rows where TICKER is exactly 3 characters (individual banks)
                df = df[df['TICKER'].str.len() == 3]
                print(f"Filtered to all individual banks (3-letter tickers), rows: {len(df)}")
            else:
                # Check if any tickers are sector names
                sector_names = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
                has_sectors = any(t in sector_names for t in tickers)
                
                if has_sectors and need_components:
                    # Include both sector data AND component banks
                    # First get the sector rows
                    sector_df = df[df['TICKER'].isin(tickers)]
                    
                    # Then get component banks by matching Type column
                    # Special handling for "Sector" - get all individual banks
                    if 'Sector' in tickers:
                        # Get all individual banks (3-letter tickers)
                        # IMPORTANT: Exclude sub-sector aggregates (SOCB, Private_1, etc.)
                        sub_sectors = ['SOCB', 'Private_1', 'Private_2', 'Private_3']
                        component_df = df[(df['TICKER'].str.len() == 3) & 
                                         (~df['TICKER'].isin(sub_sectors))]
                    else:
                        # Get banks matching the specific sector types
                        component_df = df[df['Type'].isin(tickers)]
                    
                    # Combine both
                    df = pd.concat([sector_df, component_df]).drop_duplicates()
                    print(f"Filtered to sectors {tickers} with components, rows: {len(df)}")
                elif has_sectors:
                    # Only sector aggregated data
                    df = df[df['TICKER'].isin(tickers)]
                    print(f"Filtered to sectors only: {tickers}, rows: {len(df)}")
                else:
                    # Regular ticker filtering
                    df = df[df['TICKER'].isin(tickers)]
                    print(f"Filtered to {len(tickers)} tickers: {tickers}, rows: {len(df)}")
        
        # Filter by timeframe (now expects a list)
        latest_4 = self._get_latest_4_quarters()
        timeframe = query_analysis.get('timeframe', latest_4)
        
        # Ensure timeframe is a list
        if not isinstance(timeframe, list):
            if timeframe == 'LATEST':
                timeframe = latest_4
            else:
                timeframe = [timeframe]
        
        if 'Date_Quarter' in df.columns:
            # Quarterly data - filter by the list of quarters
            if timeframe:
                df = df[df['Date_Quarter'].isin(timeframe)]
                print(f"Filtered to quarters {timeframe}, rows: {len(df)}")
        
        elif 'Year' in df.columns:
            # Yearly data - extract years from timeframe if they're year values
            years = []
            for t in timeframe:
                if isinstance(t, str) and t.isdigit() and len(t) == 4:
                    years.append(int(t))
            
            if years:
                df = df[df['Year'].isin(years)]
                print(f"Filtered to years {years}, rows: {len(df)}")
            else:
                # If no valid years, get latest year
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