#%% Import libraries

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

class DataDiscoveryAgent:
    
    def __init__(self, data_dir: str = 'Data'):
        self.data_dir = data_dir
        self.data_cache = {}
        self._initialize_data_catalog()
        self._load_keycode_mappings()
    
    def _initialize_data_catalog(self):
        self.data_catalog = {
            'dfsectorquarter.csv': {
                'description': 'Quarterly banking metrics by sector',
                'key_columns': ['TICKER', 'Date_Quarter', 'Type'],
                'metrics': ['All KeyCode columns'],
                'update_frequency': 'Quarterly'
            },
            'dfsectoryear.csv': {
                'description': 'Yearly banking metrics by sector',
                'key_columns': ['TICKER', 'Year', 'Type'],
                'metrics': ['All KeyCode columns'],
                'update_frequency': 'Yearly'
            },
            'IRIS KeyCodes - Bank.xlsx': {
                'description': 'IRIS keycode definitions and mapping',
                'key_columns': ['KeyCode', 'Name'],
                'metrics': ['Metric definitions'],
                'update_frequency': 'Static'
            },
            'Key_items.xlsx': {
                'description': 'Mapping of KeyCode to friendly names',
                'key_columns': ['KeyCode', 'Description'],
                'metrics': ['Metric definitions'],
                'update_frequency': 'Static'
            }
        }
    
    def _load_keycode_mappings(self):
        """Load keycode mappings from Key_items.xlsx and IRIS KeyCodes"""
        self.metric_to_keycodes = {}
        
        try:
            # Load Key_items.xlsx
            key_items_path = os.path.join(self.data_dir, 'Key_items.xlsx')
            if os.path.exists(key_items_path):
                df_key = pd.read_excel(key_items_path)
                
                # Create mapping from metric name to keycode
                for _, row in df_key.iterrows():
                    name = str(row.get('Name', '')).upper().strip()
                    keycode = str(row.get('KeyCode', '')).strip()
                    
                    if name and keycode:
                        # Direct mapping
                        self.metric_to_keycodes[name] = [keycode]
                        
                        # Also handle common variations
                        if name == 'ROE':
                            self.metric_to_keycodes['RETURN ON EQUITY'] = [keycode]
                        elif name == 'ROA':
                            self.metric_to_keycodes['RETURN ON ASSETS'] = [keycode]
                        elif name == 'NIM':
                            self.metric_to_keycodes['NET INTEREST MARGIN'] = [keycode]
                
                print(f"Loaded {len(self.metric_to_keycodes)} metric mappings from Key_items.xlsx")
            
            # Load IRIS KeyCodes for additional mappings
            iris_path = os.path.join(self.data_dir, 'IRIS KeyCodes - Bank.xlsx')
            if os.path.exists(iris_path):
                df_iris = pd.read_excel(iris_path)
                
                # Add IRIS mappings for metrics not in Key_items
                for _, row in df_iris.iterrows():
                    name = str(row.get('Name', '')).upper().strip()
                    keycode = str(row.get('KeyCode', '')).strip()
                    
                    # Only add if it's a CA.*, IS.*, BS.*, or NT.* keycode
                    if keycode and any(keycode.startswith(prefix) for prefix in ['CA.', 'IS.', 'BS.', 'NT.']):
                        if 'NPL' in name and 'NPL' not in self.metric_to_keycodes:
                            self.metric_to_keycodes['NPL'] = [keycode]
                        elif 'CAR' in name and 'CAR' not in self.metric_to_keycodes:
                            self.metric_to_keycodes['CAR'] = [keycode]
                        elif 'COVERAGE' in name and 'COVERAGE' not in self.metric_to_keycodes:
                            self.metric_to_keycodes['COVERAGE'] = [keycode]
                
                print(f"Total metric mappings: {len(self.metric_to_keycodes)}")
                
        except Exception as e:
            print(f"Warning: Could not load keycode mappings: {e}")
            # Fallback to empty mappings
            self.metric_to_keycodes = {}
    
    def get_available_sources(self) -> List[str]:
        available = []
        for filename in self.data_catalog.keys():
            filepath = os.path.join(self.data_dir, filename)
            if os.path.exists(filepath):
                available.append(filename)
        return available
    
    def find_relevant_data(self, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'data_found': False,
            'sources': [],
            'summary': {},
            'sample_data': None,
            'error': None
        }
        
        try:
            files_to_load = self._determine_files(query_analysis)
            
            extracted_data = {}
            for file in files_to_load:
                filepath = os.path.join(self.data_dir, file)
                if os.path.exists(filepath):
                    data = self._load_and_filter_data(
                        filepath, 
                        query_analysis
                    )
                    if data is not None and not data.empty:
                        extracted_data[file] = data
                        result['sources'].append({
                            'file': file,
                            'description': self.data_catalog.get(file, {}).get('description', ''),
                            'rows': len(data),
                            'columns': list(data.columns)[:10]
                        })
            
            if extracted_data:
                result['data_found'] = True
                result['summary'] = self._create_data_summary(extracted_data, query_analysis)
                result['sample_data'] = self._create_sample_data(extracted_data, query_analysis)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _determine_files(self, query_analysis: Dict[str, Any]) -> List[str]:
        files = []
        
        # Only use the 4 specified files
        # Determine if we need quarterly or yearly data
        time_context = query_analysis.get('time_context', {})
        original_query = str(query_analysis.get('original_query', '')).lower()
        
        # Check if query mentions quarters or years
        if time_context.get('specific_quarters') or 'q' in original_query or 'quarter' in original_query:
            files.append('dfsectorquarter.csv')
        elif time_context.get('specific_years') or 'year' in original_query or 'annual' in original_query:
            files.append('dfsectoryear.csv')
        else:
            # Default to quarterly if metrics are requested
            if query_analysis.get('metrics_requested'):
                files.append('dfsectorquarter.csv')
        
        # Handle data_source field from query router if present
        if 'data_source' in query_analysis:
            data_source_file = query_analysis['data_source']
            if 'quarter' in data_source_file.lower() and 'dfsectorquarter.csv' not in files:
                files.append('dfsectorquarter.csv')
            elif 'year' in data_source_file.lower() and 'dfsectoryear.csv' not in files:
                files.append('dfsectoryear.csv')
        
        # We don't need to load Key_items.xlsx or IRIS KeyCodes for data display
        # They're only used internally for mapping
        
        return list(set(files))
    
    def _load_and_filter_data(self, filepath: str, query_analysis: Dict[str, Any]) -> Optional[pd.DataFrame]:
        try:
            if filepath in self.data_cache:
                df = self.data_cache[filepath].copy()
            else:
                if filepath.endswith('.csv'):
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)
                
                self.data_cache[filepath] = df.copy()
            
            df = self._apply_filters(df, query_analysis)
            
            return df
            
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return None
    
    def _apply_filters(self, df: pd.DataFrame, query_analysis: Dict[str, Any]) -> pd.DataFrame:
        # Filter by banks if specified
        banks = query_analysis.get('entities', {}).get('banks', [])
        if not banks:
            # Also check the 'banks' field directly
            banks = query_analysis.get('banks', [])
        
        # IMPORTANT: Filter by banks FIRST to reduce data size
        if banks and 'TICKER' in df.columns:
            print(f"Filtering for banks: {banks}")
            df = df[df['TICKER'].isin(banks)]
            
            # If no matching banks found, return empty dataframe
            if df.empty:
                print(f"No data found for banks: {banks}")
                return df
        
        time_context = query_analysis.get('time_context', {})
        
        # Handle specific quarters
        if 'Date_Quarter' in df.columns:
            quarters = time_context.get('specific_quarters', [])
            
            # Also check for quarters in the original query (e.g., "2Q25")
            if not quarters and query_analysis.get('original_query'):
                import re
                quarter_pattern = r'[1-4]Q\d{2}'
                found_quarters = re.findall(quarter_pattern, query_analysis['original_query'])
                if found_quarters:
                    quarters = found_quarters
                    print(f"Found quarters in query: {quarters}")
            
            if quarters:
                df = df[df['Date_Quarter'].isin(quarters)]
                print(f"Filtered to quarters: {quarters}, rows remaining: {len(df)}")
        
        elif time_context.get('specific_years'):
            year_columns = ['Year', 'Date']
            for col in year_columns:
                if col in df.columns:
                    if col == 'Year':
                        df = df[df[col].astype(str).isin(time_context['specific_years'])]
                    elif col == 'Date':
                        df['_year'] = pd.to_datetime(df[col]).dt.year.astype(str)
                        df = df[df['_year'].isin(time_context['specific_years'])]
                        df = df.drop('_year', axis=1)
                    break
        
        # Handle "latest" request
        if time_context.get('latest'):
            if 'Date_Quarter' in df.columns:
                df['_quarter_sort'] = df['Date_Quarter'].apply(self._quarter_to_numeric)
                latest_quarter = df['_quarter_sort'].max()
                df = df[df['_quarter_sort'] == latest_quarter]
                df = df.drop('_quarter_sort', axis=1)
                print(f"Filtered to latest quarter, rows: {len(df)}")
            elif 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df = df[df['Date'] == df['Date'].max()]
        
        # If no time filter was applied and we have too much data, limit it
        if 'Date_Quarter' in df.columns and len(df) > 100 and not quarters and not time_context.get('latest'):
            # Only show last 4 quarters if too much data
            df['_quarter_sort'] = df['Date_Quarter'].apply(self._quarter_to_numeric)
            top_quarters = sorted(df['_quarter_sort'].unique())[-4:]
            df = df[df['_quarter_sort'].isin(top_quarters)]
            df = df.drop('_quarter_sort', axis=1)
            print(f"Limited to last 4 quarters, rows: {len(df)}")
        
        return df
    
    def _quarter_to_numeric(self, quarter_str: str) -> float:
        try:
            q = int(quarter_str[0])
            year = 2000 + int(quarter_str[2:4])
            return year + (q - 1) / 4
        except:
            return 0
    
    def _create_data_summary(self, extracted_data: Dict[str, pd.DataFrame], query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        summary = {
            'total_records': sum(len(df) for df in extracted_data.values()),
            'data_sources': list(extracted_data.keys()),
            'time_coverage': {},
            'entities_found': {}
        }
        
        for file, df in extracted_data.items():
            if 'Date_Quarter' in df.columns:
                quarters = df['Date_Quarter'].unique()
                summary['time_coverage'][file] = {
                    'type': 'quarterly',
                    'periods': sorted(quarters)[-5:] if len(quarters) > 5 else sorted(quarters)
                }
            elif 'Date' in df.columns:
                dates = pd.to_datetime(df['Date'])
                summary['time_coverage'][file] = {
                    'type': 'date',
                    'min': str(dates.min()),
                    'max': str(dates.max())
                }
        
        for file, df in extracted_data.items():
            if 'TICKER' in df.columns:
                tickers = df['TICKER'].unique()
                summary['entities_found'][file] = list(tickers)[:10]
        
        metrics_requested = query_analysis.get('metrics_requested', [])
        if metrics_requested:
            summary['metrics_available'] = self._identify_available_metrics(extracted_data, metrics_requested)
        
        return summary
    
    def _create_sample_data(self, extracted_data: Dict[str, pd.DataFrame], query_analysis: Dict[str, Any]) -> str:
        samples = []
        
        # Only process the main data files
        data_files = ['dfsectorquarter.csv', 'dfsectoryear.csv']
        
        for file, df in extracted_data.items():
            # Skip metadata files - we don't want to show Key_items or IRIS KeyCodes data
            if file in ['Key_items.xlsx', 'IRIS KeyCodes - Bank.xlsx', 'Bank_Type.xlsx']:
                continue
                
            if file in data_files and len(df) > 0:
                # Get all data, not just head(5) if filtered properly
                if len(df) <= 20:
                    sample_df = df
                else:
                    sample_df = df.head(20)
                
                relevant_cols = self._select_relevant_columns(sample_df, query_analysis)
                if relevant_cols:
                    sample_df = sample_df[relevant_cols]
                
                # Sort by Date_Quarter if available for better readability
                if 'Date_Quarter' in sample_df.columns:
                    sample_df['_sort'] = sample_df['Date_Quarter'].apply(self._quarter_to_numeric)
                    sample_df = sample_df.sort_values('_sort', ascending=False)
                    sample_df = sample_df.drop('_sort', axis=1)
                
                samples.append(f"\nData from {file}:\n{sample_df.to_string()}")
        
        return "\n".join(samples) if samples else "No sample data available"
    
    def _select_relevant_columns(self, df: pd.DataFrame, query_analysis: Dict[str, Any]) -> List[str]:
        relevant = []
        
        id_cols = ['TICKER', 'Date', 'Date_Quarter', 'Year', 'QUARTER', 'Type']
        for col in id_cols:
            if col in df.columns:
                relevant.append(col)
        
        # Get metrics from entities and metrics_requested
        metrics = query_analysis.get('entities', {}).get('metrics', [])
        metrics.extend(query_analysis.get('metrics_requested', []))
        
        # Get keycodes needed for the metrics from query router
        keycodes_needed = query_analysis.get('keycodes_needed', {})
        
        # Add columns based on keycodes from query router
        for metric, keycodes in keycodes_needed.items():
            for keycode in keycodes:
                if keycode in df.columns and keycode not in relevant:
                    relevant.append(keycode)
        
        # Use dynamically loaded keycode mappings
        for metric in metrics:
            metric_upper = metric.upper()
            
            # Check our loaded mappings
            if metric_upper in self.metric_to_keycodes:
                for keycode in self.metric_to_keycodes[metric_upper]:
                    if keycode in df.columns and keycode not in relevant:
                        relevant.append(keycode)
            
            # Also search for metric names in column names
            for col in df.columns:
                if metric.lower() in col.lower() and col not in relevant:
                    relevant.append(col)
        
        # If still not enough columns, add some keycode columns
        if len(relevant) < 5:
            keycode_cols = [col for col in df.columns if col.startswith('CA.') or col.startswith('IS.')]
            relevant.extend(keycode_cols[:10-len(relevant)])
        
        return relevant[:15]  # Return more columns for better context
    
    def _identify_available_metrics(self, extracted_data: Dict[str, pd.DataFrame], metrics_requested: List[str]) -> Dict[str, List[str]]:
        available = {}
        
        for metric_type in metrics_requested:
            available[metric_type] = []
            
            for file, df in extracted_data.items():
                metric_keywords = {
                    'growth': ['growth', 'change', 'pct'],
                    'profitability': ['profit', 'income', 'roi', 'roe', 'roa', 'margin'],
                    'quality': ['npl', 'provision', 'coverage', 'quality'],
                    'efficiency': ['cir', 'cost', 'expense', 'efficiency'],
                    'liquidity': ['ldr', 'deposit', 'liquid', 'cash'],
                    'capital': ['car', 'capital', 'tier', 'equity']
                }
                
                keywords = metric_keywords.get(metric_type, [metric_type])
                for col in df.columns:
                    col_lower = col.lower()
                    if any(kw in col_lower for kw in keywords):
                        available[metric_type].append(f"{file}:{col}")
        
        return available
    
    def analyze_data_quality(self) -> Dict[str, Any]:
        quality_report = {
            'data_sources': {},
            'overall_quality': 'Good',
            'issues': [],
            'recommendations': []
        }
        
        for filename in self.get_available_sources():
            filepath = os.path.join(self.data_dir, filename)
            try:
                if filename.endswith('.csv'):
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)
                
                quality_report['data_sources'][filename] = {
                    'rows': len(df),
                    'columns': len(df.columns),
                    'missing_values': df.isnull().sum().sum(),
                    'missing_percentage': f"{(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100):.2f}%",
                    'duplicate_rows': df.duplicated().sum(),
                    'last_modified': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d')
                }
                
                if df.isnull().sum().sum() > len(df) * len(df.columns) * 0.1:
                    quality_report['issues'].append(f"{filename}: High missing data (>10%)")
                
                if df.duplicated().sum() > 0:
                    quality_report['issues'].append(f"{filename}: Contains duplicate rows")
                
            except Exception as e:
                quality_report['data_sources'][filename] = {'error': str(e)}
                quality_report['issues'].append(f"{filename}: Failed to load")
        
        if quality_report['issues']:
            quality_report['overall_quality'] = 'Needs Attention'
            quality_report['recommendations'] = [
                "Review and clean data files with high missing values",
                "Remove duplicate rows where found",
                "Ensure all data files are properly formatted"
            ]
        
        return quality_report