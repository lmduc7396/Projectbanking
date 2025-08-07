#%% Import libraries
import re
import json
import pandas as pd
import os
from typing import Dict, List, Any, Optional, Tuple
from utilities.openai_utils import get_openai_client

class QueryRouter:
    
    def __init__(self):
        self.client = get_openai_client()
        
        # Load IRIS keycode mapping
        self.keycode_mapping = self._load_keycode_mapping()
        
        # Define the main data sources
        self.data_sources = {
            'quarterly_metrics': {
                'file': 'dfsectorquarter.csv',
                'time_keywords': ['quarter', 'quarterly', 'Q1', 'Q2', 'Q3', 'Q4', '1Q', '2Q', '3Q', '4Q'],
                'description': 'Quarterly banking metrics with keycode columns'
            },
            'yearly_metrics': {
                'file': 'dfsectoryear.csv',
                'time_keywords': ['year', 'yearly', 'annual', 'YoY'],
                'description': 'Yearly banking metrics with keycode columns'
            },
            'keycode_reference': {
                'file': 'IRIS KeyCodes - Bank.xlsx',
                'description': 'Keycode to metric name mapping'
            }
        }
        
        # Common banking metrics and their potential keycodes
        self.metric_keywords = {
            'NIM': ['nim', 'net interest margin'],
            'NPL': ['npl', 'non-performing', 'non performing loan'],
            'ROE': ['roe', 'return on equity'],
            'ROA': ['roa', 'return on assets'],
            'PBT': ['pbt', 'profit before tax'],
            'CAR': ['car', 'capital adequacy ratio'],
            'LDR': ['ldr', 'loan deposit ratio', 'loan to deposit'],
            'CIR': ['cir', 'cost income ratio', 'cost to income'],
            'Coverage': ['coverage', 'provision coverage'],
            'Asset Quality': ['asset quality', 'credit quality'],
            'Total Assets': ['total assets', 'assets'],
            'Total Loans': ['total loans', 'loans', 'credit'],
            'Deposits': ['deposits', 'customer deposits'],
            'Revenue': ['revenue', 'total revenue', 'income'],
            'Net Profit': ['net profit', 'net income', 'profit after tax']
        }
        
        self.bank_tickers = [
            'VCB', 'BID', 'CTG', 'TCB', 'MBB', 'VPB', 'ACB', 'STB', 
            'HDB', 'TPB', 'SHB', 'VIB', 'LPB', 'MSB', 'OCB', 'EIB',
            'SSB', 'NAB', 'BAB', 'VAB', 'PGB', 'KLB', 'NCB', 'ABB', 'NVB'
        ]
        
        self.time_patterns = {
            'quarter': r'[1-4]Q\d{2}|Q[1-4]\s*\d{4}|quarter',
            'year': r'20\d{2}|year|annual'
        }
    
    def _load_keycode_mapping(self) -> pd.DataFrame:
        """Load the IRIS keycode mapping file"""
        try:
            # Get the data directory path
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            keycode_file = os.path.join(current_dir, 'Data', 'IRIS KeyCodes - Bank.xlsx')
            df = pd.read_excel(keycode_file)
            # Create a clean mapping of keycodes to names
            df['Name_Clean'] = df['Name'].str.upper().str.strip()
            return df
        except Exception as e:
            print(f"Warning: Could not load keycode mapping: {e}")
            return pd.DataFrame()
    
    def translate_metric_to_keycode(self, metric_name: str) -> List[str]:
        """
        Translate a metric name (like 'NIM', 'NPL') to its corresponding keycode(s)
        Returns a list of matching keycodes
        """
        if self.keycode_mapping.empty:
            return []
        
        metric_upper = metric_name.upper().strip()
        
        # Direct match on keycode
        direct_matches = self.keycode_mapping[
            self.keycode_mapping['KeyCode'].str.contains(metric_upper, case=False, na=False)
        ]
        
        # Match on name
        name_matches = self.keycode_mapping[
            self.keycode_mapping['Name_Clean'].str.contains(metric_upper, case=False, na=False)
        ]
        
        # Combine matches and get unique keycodes
        all_matches = pd.concat([direct_matches, name_matches]).drop_duplicates()
        
        # Filter for relevant keycodes (IS.*, CA.*, BS.*, NT.*)
        keycodes = all_matches['KeyCode'].tolist()
        relevant_keycodes = [k for k in keycodes if any(k.startswith(prefix) for prefix in ['IS.', 'CA.', 'BS.', 'NT.'])]
        
        return relevant_keycodes
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze user query and determine data requirements
        """
        query_lower = query.lower()
        
        # Extract components
        metrics_requested = self._identify_requested_metrics(query)
        keycodes = self._translate_metrics_to_keycodes(metrics_requested)
        
        analysis = {
            'original_query': query,
            'intent': self._identify_intent(query_lower),
            'entities': self._extract_entities(query),
            'metrics_requested': metrics_requested,
            'keycodes_needed': keycodes,
            'data_source': self._determine_data_source(query_lower),
            'time_context': self._extract_time_context(query),
            'banks': self._extract_banks(query),
            'aggregation_level': self._identify_aggregation(query_lower)
        }
        
        # Add interpretation for complex queries
        if not keycodes and metrics_requested:
            analysis['needs_manual_mapping'] = True
            analysis['suggested_action'] = 'Manual review of IRIS keycode file needed'
        
        return analysis
    
    def _identify_requested_metrics(self, query: str) -> List[str]:
        """Identify which metrics the user is asking about"""
        query_lower = query.lower()
        found_metrics = []
        
        for metric, keywords in self.metric_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                found_metrics.append(metric)
        
        # Also check for direct metric mentions
        words = query_lower.split()
        for word in words:
            word_upper = word.upper()
            if word_upper in ['NIM', 'NPL', 'ROE', 'ROA', 'PBT', 'CAR', 'LDR', 'CIR']:
                if word_upper not in found_metrics:
                    found_metrics.append(word_upper)
        
        return found_metrics
    
    def _translate_metrics_to_keycodes(self, metrics: List[str]) -> Dict[str, List[str]]:
        """Translate list of metrics to their keycodes"""
        keycode_dict = {}
        
        for metric in metrics:
            keycodes = self.translate_metric_to_keycode(metric)
            if keycodes:
                keycode_dict[metric] = keycodes
        
        return keycode_dict
    
    def _determine_data_source(self, query: str) -> str:
        """Determine whether to use quarterly or yearly data"""
        # Check for quarterly keywords
        if any(keyword in query for keyword in self.data_sources['quarterly_metrics']['time_keywords']):
            return 'dfsectorquarter.csv'
        
        # Check for yearly keywords
        if any(keyword in query for keyword in self.data_sources['yearly_metrics']['time_keywords']):
            return 'dfsectoryear.csv'
        
        # Default to quarterly
        return 'dfsectorquarter.csv'
    
    def _identify_intent(self, query: str) -> str:
        """Identify the intent of the query"""
        intents = {
            'trend_analysis': ['trend', 'growth', 'change', 'evolution', 'trajectory'],
            'comparison': ['compare', 'versus', 'vs', 'difference', 'better', 'worse'],
            'ranking': ['top', 'best', 'worst', 'highest', 'lowest', 'rank'],
            'specific_metric': ['what is', 'show me', 'tell me', 'how much', 'value'],
            'risk_assessment': ['risk', 'npl', 'provision', 'asset quality', 'coverage'],
            'performance': ['performance', 'roi', 'roe', 'roa', 'profitability'],
            'forecast': ['predict', 'forecast', 'outlook', 'expect', 'future'],
            'explanation': ['why', 'explain', 'reason', 'cause', 'driver']
        }
        
        for intent, keywords in intents.items():
            if any(keyword in query for keyword in keywords):
                return intent
        
        return 'general_inquiry'
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract entities from the query"""
        entities = {
            'banks': self._extract_banks(query),
            'metrics': self._identify_requested_metrics(query),
            'time_periods': self._extract_specific_periods(query)
        }
        return entities
    
    def _extract_banks(self, query: str) -> List[str]:
        """Extract bank tickers from query"""
        banks = []
        query_upper = query.upper()
        
        for ticker in self.bank_tickers:
            # Check for exact match with word boundaries
            import re
            pattern = r'\b' + ticker + r'\b'
            if re.search(pattern, query_upper):
                banks.append(ticker)
        
        return banks
    
    def _extract_time_context(self, query: str) -> Dict[str, Any]:
        """Extract time-related information from query"""
        time_context = {
            'specific_quarters': self._extract_specific_periods(query),
            'specific_years': [],
            'time_range': None,
            'latest': False
        }
        
        # Check for latest/current
        if any(word in query.lower() for word in ['latest', 'current', 'recent', 'last']):
            time_context['latest'] = True
        
        # Extract years
        year_matches = re.findall(r'20\d{2}', query)
        time_context['specific_years'] = year_matches
        
        # Check for ranges
        if 'from' in query.lower() and 'to' in query.lower():
            time_context['time_range'] = 'custom'
        elif 'ytd' in query.lower():
            time_context['time_range'] = 'year_to_date'
        
        return time_context
    
    def _extract_specific_periods(self, query: str) -> List[str]:
        """Extract specific quarter periods from query"""
        quarters = []
        
        # Pattern for quarters like 1Q24, 2Q23, etc.
        pattern1 = r'[1-4]Q\d{2}'
        matches1 = re.findall(pattern1, query, re.IGNORECASE)
        quarters.extend(matches1)
        
        # Pattern for quarters like Q1 2024, Q2 2023, etc.
        pattern2 = r'Q[1-4]\s*20\d{2}'
        matches2 = re.findall(pattern2, query, re.IGNORECASE)
        # Convert to standard format
        for match in matches2:
            parts = re.split(r'\s+', match)
            if len(parts) == 2:
                quarter_num = parts[0][1]
                year = parts[1][-2:]
                quarters.append(f"{quarter_num}Q{year}")
        
        return list(set(quarters))  # Remove duplicates
    
    def _identify_aggregation(self, query: str) -> str:
        """Identify aggregation level needed"""
        if any(word in query for word in ['sector', 'industry', 'overall', 'total', 'aggregate']):
            return 'sector'
        elif any(word in query for word in ['group', 'type', 'category']):
            return 'group'
        elif any(word in query for word in ['individual', 'specific', 'each']):
            return 'individual'
        else:
            # Default based on whether specific banks are mentioned
            banks = self._extract_banks(query)
            return 'individual' if banks else 'sector'
    
    def get_data_for_query(self, analysis: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
        """
        Based on query analysis, load the appropriate data and return relevant columns
        Returns: (dataframe, list of relevant column names)
        """
        # Determine which file to load
        data_file = analysis['data_source']
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(current_dir, 'Data', data_file)
        df = pd.read_csv(file_path)
        
        # Get relevant columns
        relevant_columns = ['TICKER', 'Date_Quarter' if 'quarter' in data_file else 'Date_Year']
        
        # Add keycode columns
        for metric, keycodes in analysis['keycodes_needed'].items():
            for keycode in keycodes:
                if keycode in df.columns:
                    relevant_columns.append(keycode)
        
        # Filter by banks if specified
        if analysis['banks']:
            df = df[df['TICKER'].isin(analysis['banks'])]
        
        # Filter by time if specified
        if analysis['time_context']['specific_quarters']:
            time_col = 'Date_Quarter' if 'quarter' in data_file else 'Date_Year'
            df = df[df[time_col].isin(analysis['time_context']['specific_quarters'])]
        
        return df, relevant_columns
    
    def explain_keycodes(self, keycodes: List[str]) -> Dict[str, str]:
        """
        Get human-readable names for keycodes
        """
        explanations = {}
        
        for keycode in keycodes:
            matches = self.keycode_mapping[self.keycode_mapping['KeyCode'] == keycode]
            if not matches.empty:
                explanations[keycode] = matches.iloc[0]['Name']
            else:
                explanations[keycode] = f"Unknown metric ({keycode})"
        
        return explanations

# Helper function for quick testing
def test_query_router():
    router = QueryRouter()
    
    # Test queries
    test_queries = [
        "Show me NIM for VCB in Q1 2024",
        "What is the NPL ratio trend for all banks?",
        "Compare ROE and ROA for TCB and MBB",
        "Show profit before tax for the banking sector in 2023"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        analysis = router.analyze_query(query)
        print(f"Metrics: {analysis['metrics_requested']}")
        print(f"Keycodes: {analysis['keycodes_needed']}")
        print(f"Data source: {analysis['data_source']}")
        print(f"Banks: {analysis['banks']}")