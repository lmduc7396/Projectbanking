#%% Import libraries
import re
import json
from typing import Dict, List, Any
from utilities.openai_utils import get_openai_client

class QueryRouter:
    
    def __init__(self):
        self.client = get_openai_client()
        
        self.data_sources = {
            'quarterly_metrics': {
                'files': ['dfsectorquarter.csv'],
                'keywords': ['quarter', 'quarterly', 'Q1', 'Q2', 'Q3', 'Q4', '1Q', '2Q', '3Q', '4Q'],
                'metrics': ['growth', 'performance', 'trend', 'change']
            },
            'yearly_metrics': {
                'files': ['dfsectoryear.csv'],
                'keywords': ['year', 'yearly', 'annual', 'YoY'],
                'metrics': ['annual', 'yearly trend', 'year-over-year']
            },
            'balance_sheet': {
                'files': ['BS_Bank.csv', 'BS_Bank1Q25.csv'],
                'keywords': ['assets', 'liabilities', 'equity', 'capital', 'CAR', 'deposits', 'loans'],
                'metrics': ['balance sheet', 'financial position']
            },
            'income_statement': {
                'files': ['IS_Bank.csv', 'IS_Bank1Q25.csv'],
                'keywords': ['revenue', 'income', 'profit', 'NIM', 'ROE', 'ROA', 'expenses'],
                'metrics': ['profitability', 'earnings', 'margins']
            },
            'notes': {
                'files': ['Note_Bank.csv', 'Note_Bank1Q25.csv'],
                'keywords': ['NPL', 'provision', 'coverage', 'asset quality', 'risk'],
                'metrics': ['credit quality', 'provisions']
            },
            'comments': {
                'files': ['banking_comments.xlsx'],
                'keywords': ['comment', 'analysis', 'insight', 'summary'],
                'metrics': ['qualitative analysis']
            },
            'sector_analysis': {
                'files': ['quarterly_analysis_results.xlsx'],
                'keywords': ['sector', 'industry', 'market', 'overall', 'banking sector'],
                'metrics': ['sector trends', 'market analysis']
            }
        }
        
        self.bank_tickers = [
            'VCB', 'BID', 'CTG', 'TCB', 'MBB', 'VPB', 'ACB', 'STB', 
            'HDB', 'TPB', 'SHB', 'VIB', 'LPB', 'MSB', 'OCB', 'EIB',
            'SSB', 'NAB', 'BAB', 'VAB', 'PGB', 'KLB', 'NCB', 'ABB'
        ]
        
        self.time_patterns = {
            'quarter': r'[1-4]Q\d{2}|Q[1-4]\s*\d{4}|quarter',
            'year': r'20\d{2}|year|annual',
            'month': r'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec'
        }
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        
        analysis = {
            'original_query': query,
            'intent': self._identify_intent(query_lower),
            'entities': self._extract_entities(query),
            'data_sources': self._identify_data_sources(query_lower),
            'time_context': self._extract_time_context(query),
            'metrics_requested': self._identify_metrics(query_lower),
            'comparison_type': self._identify_comparison(query_lower),
            'aggregation_level': self._identify_aggregation(query_lower)
        }
        
        if analysis['intent'] == 'complex':
            analysis['ai_interpretation'] = self._get_ai_interpretation(query)
        
        return analysis
    
    def _identify_intent(self, query: str) -> str:
        intents = {
            'trend_analysis': ['trend', 'growth', 'change', 'evolution', 'trajectory'],
            'comparison': ['compare', 'versus', 'vs', 'difference', 'better', 'worse'],
            'ranking': ['top', 'best', 'worst', 'highest', 'lowest', 'rank'],
            'specific_metric': ['what is', 'show me', 'tell me', 'how much'],
            'risk_assessment': ['risk', 'npl', 'provision', 'asset quality', 'coverage'],
            'performance': ['performance', 'roi', 'roe', 'roa', 'profitability'],
            'forecast': ['predict', 'forecast', 'outlook', 'expect', 'future'],
            'explanation': ['why', 'explain', 'reason', 'cause', 'driver']
        }
        
        for intent, keywords in intents.items():
            if any(keyword in query for keyword in keywords):
                return intent
        
        return 'complex'
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        entities = {
            'banks': [],
            'metrics': [],
            'time_periods': []
        }
        
        for ticker in self.bank_tickers:
            if ticker in query.upper():
                entities['banks'].append(ticker)
        
        metrics_map = {
            'NPL': ['npl', 'non-performing'],
            'ROE': ['roe', 'return on equity'],
            'ROA': ['roa', 'return on assets'],
            'NIM': ['nim', 'net interest margin'],
            'CAR': ['car', 'capital adequacy'],
            'LDR': ['ldr', 'loan deposit ratio'],
            'CIR': ['cir', 'cost income ratio']
        }
        
        query_lower = query.lower()
        for metric, patterns in metrics_map.items():
            if any(pattern in query_lower for pattern in patterns):
                entities['metrics'].append(metric)
        
        return entities
    
    def _identify_data_sources(self, query: str) -> List[str]:
        required_sources = []
        
        for source_name, source_info in self.data_sources.items():
            if any(keyword in query for keyword in source_info['keywords']):
                required_sources.append(source_name)
                continue
            
            if any(metric in query for metric in source_info['metrics']):
                required_sources.append(source_name)
        
        if not required_sources:
            required_sources = ['quarterly_metrics']
        
        return required_sources
    
    def _extract_time_context(self, query: str) -> Dict[str, Any]:
        import re
        
        time_context = {
            'specific_quarters': [],
            'specific_years': [],
            'time_range': None,
            'latest': False,
            'comparison_period': None
        }
        
        if any(word in query.lower() for word in ['latest', 'current', 'recent', 'last']):
            time_context['latest'] = True
        
        quarter_patterns = [
            r'[1-4]Q\d{2}',
            r'Q[1-4]\s*20\d{2}'
        ]
        for pattern in quarter_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            time_context['specific_quarters'].extend(matches)
        
        year_matches = re.findall(r'20\d{2}', query)
        time_context['specific_years'] = year_matches
        
        if 'from' in query.lower() and 'to' in query.lower():
            time_context['time_range'] = 'custom'
        elif 'ytd' in query.lower():
            time_context['time_range'] = 'year_to_date'
        elif 'qtd' in query.lower():
            time_context['time_range'] = 'quarter_to_date'
        
        return time_context
    
    def _identify_metrics(self, query: str) -> List[str]:
        metrics = []
        
        metric_keywords = {
            'growth': ['growth', 'increase', 'decrease', 'change'],
            'profitability': ['profit', 'income', 'earnings', 'margin'],
            'efficiency': ['efficiency', 'productivity', 'cost', 'expense'],
            'quality': ['quality', 'npl', 'provision', 'coverage'],
            'liquidity': ['liquidity', 'cash', 'deposit', 'funding'],
            'capital': ['capital', 'car', 'tier', 'basel']
        }
        
        for metric_type, keywords in metric_keywords.items():
            if any(keyword in query for keyword in keywords):
                metrics.append(metric_type)
        
        return metrics
    
    def _identify_comparison(self, query: str) -> str:
        if any(word in query for word in ['compare', 'versus', 'vs']):
            if 'peer' in query or 'sector' in query:
                return 'peer_comparison'
            elif 'quarter' in query:
                return 'time_comparison'
            else:
                return 'general_comparison'
        return 'none'
    
    def _identify_aggregation(self, query: str) -> str:
        if any(word in query for word in ['sector', 'industry', 'overall', 'total', 'aggregate']):
            return 'sector'
        elif any(word in query for word in ['group', 'type', 'category']):
            return 'group'
        elif any(word in query for word in ['individual', 'specific', 'each']):
            return 'individual'
        else:
            return 'auto'
    
    def _get_ai_interpretation(self, query: str) -> Dict[str, Any]:
        try:
            prompt = f"""
            Analyze this banking data query and extract the following:
            1. What specific data is being requested?
            2. What time period is relevant?
            3. What calculations or comparisons are needed?
            4. What format should the answer take?
            
            Query: {query}
            
            Provide response as JSON with keys: data_needed, time_period, calculations, output_format
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a query analysis expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return json.loads(response.choices[0].message.content)
        except:
            return {
                'data_needed': 'Unable to parse',
                'time_period': 'Latest available',
                'calculations': 'Standard metrics',
                'output_format': 'Summary'
            }