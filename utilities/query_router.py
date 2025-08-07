#%% Import libraries
import re
import pandas as pd
import os
from typing import Dict, List, Any, Optional
from utilities.openai_utils import get_openai_client

class QueryRouter:
    
    def __init__(self):
        self.client = get_openai_client()
        self.keycode_mapping = self._load_keycode_mapping()
        
    def _load_keycode_mapping(self) -> Dict[str, str]:
        """Load Key_items.xlsx and create mapping from item names to keycodes"""
        try:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            key_items_path = os.path.join(current_dir, 'Data', 'Key_items.xlsx')
            
            df = pd.read_excel(key_items_path)
            
            # Create mapping: item name -> keycode
            mapping = {}
            for _, row in df.iterrows():
                name = str(row.get('Name', '')).strip().upper()
                keycode = str(row.get('KeyCode', '')).strip()
                
                if name and keycode:
                    mapping[name] = keycode
                    
                    # Add common variations
                    if name == 'ROE':
                        mapping['RETURN ON EQUITY'] = keycode
                    elif name == 'ROA':
                        mapping['RETURN ON ASSETS'] = keycode
                    elif name == 'NIM':
                        mapping['NET INTEREST MARGIN'] = keycode
                    elif name == 'NPL':
                        mapping['NON PERFORMING LOAN'] = keycode
                        mapping['NON-PERFORMING LOAN'] = keycode
            
            print(f"Loaded {len(mapping)} item-to-keycode mappings")
            return mapping
            
        except Exception as e:
            print(f"Error loading Key_items.xlsx: {e}")
            return {}
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Use OpenAI to analyze the query and extract:
        1. Tickers (bank codes like ACB, VCB)
        2. Items (metrics like NIM, ROA)
        3. Timeframe (quarters like 2Q25 or years like 2025)
        """
        
        # Use OpenAI to parse the query
        prompt = f"""
        Analyze this banking query and extract the following information:
        
        Query: "{query}"
        
        Extract:
        1. TICKERS: List of bank ticker symbols mentioned (e.g., ACB, VCB, BID, etc.)
           - If "all banks" or "sector" is mentioned, return ["ALL"]
           - If no specific banks mentioned, return []
        
        2. ITEMS: List of financial metrics/items mentioned (e.g., ROE, ROA, NIM, NPL, CAR, etc.)
           - Look for common banking metrics
           - If no specific metrics mentioned, return []
        
        3. TIMEFRAME: The time period mentioned
           - For quarters, use format like "2Q25", "1Q24"
           - For years, use format like "2025", "2024"
           - If "latest" or "current" mentioned, return "LATEST"
           - If no timeframe mentioned, return "LATEST"
        
        Return your answer in JSON format:
        {{
            "tickers": [...],
            "items": [...],
            "timeframe": "..."
        }}
        
        Examples:
        - "Show me ROE for VCB in 2Q25" -> {{"tickers": ["VCB"], "items": ["ROE"], "timeframe": "2Q25"}}
        - "What's the NIM trend for all banks in 2024?" -> {{"tickers": ["ALL"], "items": ["NIM"], "timeframe": "2024"}}
        - "Compare ROA and ROE for ACB and BID" -> {{"tickers": ["ACB", "BID"], "items": ["ROA", "ROE"], "timeframe": "LATEST"}}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a banking data query parser. Extract structured information from user queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            import json
            parsed = json.loads(response.choices[0].message.content)
            
            # Convert items to keycodes
            keycodes = []
            for item in parsed.get('items', []):
                item_upper = item.upper()
                if item_upper in self.keycode_mapping:
                    keycodes.append(self.keycode_mapping[item_upper])
                else:
                    print(f"Warning: No keycode found for item '{item}'")
            
            # Determine data source based on timeframe
            timeframe = parsed.get('timeframe', 'LATEST')
            if 'Q' in timeframe:
                data_source = 'dfsectorquarter.csv'
            else:
                data_source = 'dfsectoryear.csv'
            
            return {
                'original_query': query,
                'tickers': parsed.get('tickers', []),
                'items': parsed.get('items', []),
                'keycodes': keycodes,
                'timeframe': timeframe,
                'data_source': data_source
            }
            
        except Exception as e:
            print(f"Error analyzing query: {e}")
            # Fallback to simple parsing
            return self._simple_parse(query)
    
    def _simple_parse(self, query: str) -> Dict[str, Any]:
        """Fallback simple parser if OpenAI fails"""
        query_upper = query.upper()
        
        # Extract tickers
        tickers = []
        common_tickers = ['VCB', 'BID', 'CTG', 'TCB', 'MBB', 'VPB', 'ACB', 'STB', 
                         'HDB', 'TPB', 'SHB', 'VIB', 'LPB', 'MSB', 'OCB', 'EIB']
        for ticker in common_tickers:
            if ticker in query_upper:
                tickers.append(ticker)
        
        # Extract items
        items = []
        keycodes = []
        for item_name, keycode in self.keycode_mapping.items():
            if item_name in query_upper:
                items.append(item_name)
                keycodes.append(keycode)
        
        # Extract timeframe
        timeframe = 'LATEST'
        quarter_pattern = r'[1-4]Q\d{2}'
        quarter_matches = re.findall(quarter_pattern, query_upper)
        if quarter_matches:
            timeframe = quarter_matches[0]
            data_source = 'dfsectorquarter.csv'
        else:
            year_pattern = r'20\d{2}'
            year_matches = re.findall(year_pattern, query)
            if year_matches:
                timeframe = year_matches[0]
                data_source = 'dfsectoryear.csv'
            else:
                data_source = 'dfsectorquarter.csv'
        
        return {
            'original_query': query,
            'tickers': tickers if tickers else [],
            'items': items,
            'keycodes': keycodes,
            'timeframe': timeframe,
            'data_source': data_source
        }