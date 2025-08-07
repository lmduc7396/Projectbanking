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
            'BS_Bank.csv': {
                'description': 'Balance sheet data for banks',
                'key_columns': ['TICKER', 'Date'],
                'metrics': ['Assets', 'Liabilities', 'Equity', 'Loans', 'Deposits'],
                'update_frequency': 'Quarterly'
            },
            'IS_Bank.csv': {
                'description': 'Income statement data for banks',
                'key_columns': ['TICKER', 'Date'],
                'metrics': ['Revenue', 'Net Income', 'NIM', 'Operating Income'],
                'update_frequency': 'Quarterly'
            },
            'Note_Bank.csv': {
                'description': 'Notes and additional metrics',
                'key_columns': ['TICKER', 'Date'],
                'metrics': ['NPL', 'Provision', 'Coverage Ratio'],
                'update_frequency': 'Quarterly'
            },
            'banking_comments.xlsx': {
                'description': 'AI-generated banking analysis comments',
                'key_columns': ['TICKER', 'QUARTER'],
                'metrics': ['Qualitative analysis'],
                'update_frequency': 'On-demand'
            },
            'Bank_Type.xlsx': {
                'description': 'Bank categorization and types',
                'key_columns': ['TICKER', 'Type'],
                'metrics': ['Bank classification'],
                'update_frequency': 'Static'
            },
            'Key_items.xlsx': {
                'description': 'Mapping of KeyCode to friendly names',
                'key_columns': ['KeyCode', 'Description'],
                'metrics': ['Metric definitions'],
                'update_frequency': 'Static'
            }
        }
    
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
        
        source_to_files = {
            'quarterly_metrics': ['dfsectorquarter.csv'],
            'yearly_metrics': ['dfsectoryear.csv'],
            'balance_sheet': ['BS_Bank.csv', 'BS_Bank1Q25.csv'],
            'income_statement': ['IS_Bank.csv', 'IS_Bank1Q25.csv'],
            'notes': ['Note_Bank.csv', 'Note_Bank1Q25.csv'],
            'comments': ['banking_comments.xlsx'],
            'sector_analysis': ['quarterly_analysis_results.xlsx']
        }
        
        # Handle data_source field from query router
        if 'data_source' in query_analysis:
            data_source_file = query_analysis['data_source']
            if 'quarter' in data_source_file.lower():
                files.append('dfsectorquarter.csv')
            elif 'year' in data_source_file.lower():
                files.append('dfsectoryear.csv')
        
        # Also handle data_sources if provided
        for source in query_analysis.get('data_sources', []):
            if source in source_to_files:
                files.extend(source_to_files[source])
        
        # If metrics are requested (like ROE), ensure we load the data files
        if query_analysis.get('metrics_requested'):
            # Always include the main data files when metrics are requested
            if not any('dfsector' in f for f in files):
                # Check time context to determine which file
                time_context = query_analysis.get('time_context', {})
                if time_context.get('specific_quarters') or 'Q' in str(query_analysis.get('original_query', '')):
                    files.append('dfsectorquarter.csv')
                else:
                    files.append('dfsectoryear.csv')
            
            files.append('Key_items.xlsx')
        
        if query_analysis.get('aggregation_level') in ['sector', 'group']:
            files.append('Bank_Type.xlsx')
        
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
        
        if banks and 'TICKER' in df.columns:
            df = df[df['TICKER'].isin(banks)]
        
        time_context = query_analysis.get('time_context', {})
        
        # Handle specific quarters
        if time_context.get('specific_quarters') and 'Date_Quarter' in df.columns:
            quarters = time_context['specific_quarters']
            # Also check for quarters in the original query (e.g., "2Q25")
            if not quarters and query_analysis.get('original_query'):
                import re
                quarter_pattern = r'[1-4]Q\d{2}'
                found_quarters = re.findall(quarter_pattern, query_analysis['original_query'])
                if found_quarters:
                    quarters = found_quarters
            
            if quarters:
                df = df[df['Date_Quarter'].isin(quarters)]
        
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
                df = df[df['_quarter_sort'] == df['_quarter_sort'].max()]
                df = df.drop('_quarter_sort', axis=1)
            elif 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df = df[df['Date'] == df['Date'].max()]
        
        # If no time filter was applied but we have ROE data, show recent data
        if 'Date_Quarter' in df.columns and len(df) > 100:
            # Only show last 4 quarters if too much data
            df['_quarter_sort'] = df['Date_Quarter'].apply(self._quarter_to_numeric)
            top_quarters = df['_quarter_sort'].nlargest(4).unique()
            df = df[df['_quarter_sort'].isin(top_quarters)]
            df = df.drop('_quarter_sort', axis=1)
        
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
        
        for file, df in extracted_data.items():
            if len(df) > 0:
                sample_df = df.head(5)
                
                relevant_cols = self._select_relevant_columns(sample_df, query_analysis)
                if relevant_cols:
                    sample_df = sample_df[relevant_cols]
                
                samples.append(f"\nSample from {file}:\n{sample_df.to_string()}")
        
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
        
        # Get keycodes needed for the metrics
        keycodes_needed = query_analysis.get('keycodes_needed', {})
        
        # Add columns based on keycodes
        for metric, keycodes in keycodes_needed.items():
            for keycode in keycodes:
                if keycode in df.columns and keycode not in relevant:
                    relevant.append(keycode)
        
        # Also search for metric names in column names
        for metric in metrics:
            for col in df.columns:
                if metric.lower() in col.lower() and col not in relevant:
                    relevant.append(col)
        
        # Special handling for common banking metrics
        metric_to_keycodes = {
            'ROE': ['CA.19', 'CA.18', 'CA.17'],  # Common ROE keycodes
            'ROA': ['CA.15', 'CA.14', 'CA.13'],  # Common ROA keycodes
            'NIM': ['CA.7', 'CA.8'],
            'NPL': ['CA.3', 'CA.4'],
            'CAR': ['CA.1', 'CA.2']
        }
        
        for metric in metrics:
            if metric.upper() in metric_to_keycodes:
                for keycode in metric_to_keycodes[metric.upper()]:
                    if keycode in df.columns and keycode not in relevant:
                        relevant.append(keycode)
        
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