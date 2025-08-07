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
        self.latest_quarter = self._get_latest_quarter()
        
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
    
    def _get_latest_quarter(self) -> str:
        """Get the latest quarter from dfsectorquarter.csv"""
        try:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            quarter_file = os.path.join(current_dir, 'Data', 'dfsectorquarter.csv')
            
            df = pd.read_csv(quarter_file)
            if 'Date_Quarter' in df.columns:
                # Convert quarters to numeric for sorting
                def quarter_to_numeric(q):
                    try:
                        quarter = int(q[0])
                        year = 2000 + int(q[2:4])
                        return year + (quarter - 1) / 4
                    except:
                        return 0
                
                quarters = df['Date_Quarter'].unique()
                quarters_sorted = sorted(quarters, key=quarter_to_numeric)
                latest = quarters_sorted[-1] if quarters_sorted else "2Q25"
                print(f"Latest quarter detected: {latest}")
                return latest
            else:
                return "2Q25"  # Fallback
        except Exception as e:
            print(f"Error getting latest quarter: {e}")
            return "2Q25"  # Fallback
    
    def _get_latest_4_quarters(self) -> List[str]:
        """Get the latest 4 quarters based on the latest quarter"""
        try:
            # Parse the latest quarter
            q = int(self.latest_quarter[0])
            year = int(self.latest_quarter[2:4])
            
            quarters = []
            for i in range(3, -1, -1):  # Go back 3 quarters from latest
                calc_q = q - i
                calc_year = year
                
                while calc_q <= 0:
                    calc_q += 4
                    calc_year -= 1
                
                quarters.append(f"{calc_q}Q{calc_year:02d}")
            
            return quarters
        except:
            return ["3Q24", "4Q24", "1Q25", "2Q25"]  # Fallback
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Use OpenAI to analyze the query and extract:
        1. Tickers (bank codes like ACB, VCB)
        2. Items (metrics like NIM, ROA)
        3. Timeframe (quarters like 2Q25 or years like 2025)
        """
        
        # Get latest 4 quarters for the prompt
        latest_4_quarters = self._get_latest_4_quarters()
        
        # Use OpenAI to parse the query
        prompt = f"""
        Analyze this banking query and extract the following information:
        
        IMPORTANT: The current/latest quarter is {self.latest_quarter}. 

        Query: "{query}"
        
        Extract:
        1. TICKERS: List of bank ticker symbols or sector names mentioned
           - Individual banks: ACB, VCB, BID, etc. (3-letter codes)
           - Sector groups: "Sector", "SOCB", "Private_1", "Private_2", "Private_3"
           - If "all banks" is mentioned, return ["Sector"]
           - If no specific banks/sectors mentioned, return []
        
        2. ITEMS: List of financial metrics/items mentioned (e.g., ROE, ROA, NIM, NPL, CAR, etc.)
           - Look for common banking metrics
           - If no specific metrics mentioned, return []
        
        3. TIMEFRAME: The time period(s) mentioned
           - CRITICAL: If user says "current", "latest", or "recent" - ALWAYS return ["{self.latest_quarter}"] which is the latest quarter
           - For single quarter, return one quarter like ["2Q25"]
           - For year ranges (e.g., "2024 to 2025"), return ["2024", "2025"] ONLY if explicitly asking for yearly/annual data
           - For quarter ranges (from X to Y), return ALL quarters in between
           - Example: "from 1Q24 to 2Q25" -> ["1Q24", "2Q24", "3Q24", "4Q24", "1Q25", "2Q25"]
           - For full year data (annual/yearly), return just the year(s): "2024" -> ["2024"], "2023 and 2024" -> ["2023", "2024"]
           - If user mentions "quarterly" with a year, then return quarters: "quarterly data for 2024" -> ["1Q24", "2Q24", "3Q24", "4Q24"]
           - If no timeframe mentioned, return the latest 4 quarters: {latest_4_quarters}
           - Always return as a list, even for single periods
        
        4. NEED_COMPONENTS: Boolean - true if the question requires component bank data
           - true if asking for comparisons WITHIN a sector (e.g., "which bank in SOCB has highest ROE")
           - true if asking for rankings or identifying specific banks within sectors]
           - True if asking for detailed breakdowns of sector performance
           - True if contains inclusive words like among, within, compare
           - false if only asking for aggregated sector data
        
        Return your answer in JSON format:
        {{
            "tickers": [...],
            "items": [...],
            "timeframe": [...],
            "need_components": true/false
        }}
        
        Examples:
        - "Show me ROE for VCB in 2Q25" -> {{"tickers": ["VCB"], "items": ["ROE"], "timeframe": ["2Q25"], "need_components": false}}
        - "What's the NIM for SOCB in 2024?" -> {{"tickers": ["SOCB"], "items": ["NIM"], "timeframe": ["2024"], "need_components": false}}
        - "What's ACB current CASA?" -> {{"tickers": ["ACB"], "items": ["CASA"], "timeframe": ["{self.latest_quarter}"], "need_components": false}}
        - "Show current quarter ROE" -> {{"tickers": [], "items": ["ROE"], "timeframe": ["{self.latest_quarter}"], "need_components": false}}
        - "What's the current NPL?" -> {{"tickers": [], "items": ["NPL"], "timeframe": ["{self.latest_quarter}"], "need_components": false}}
        - "Which bank in SOCB has highest ROE?" -> {{"tickers": ["SOCB"], "items": ["ROE"], "timeframe": {latest_4_quarters}, "need_components": true}}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
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
            
            # Handle timeframe as a list
            latest_4 = self._get_latest_4_quarters()
            timeframe = parsed.get('timeframe', latest_4)
            if not isinstance(timeframe, list):
                timeframe = [timeframe] if timeframe else latest_4
            
            # Determine data source based on timeframe
            # If any quarter format detected (e.g., "1Q24"), use quarterly data
            # If only year format (e.g., "2024"), use yearly data
            has_quarters = any('Q' in str(t) for t in timeframe)
            has_only_years = all(str(t).isdigit() and len(str(t)) == 4 for t in timeframe)
            
            if has_quarters:
                data_source = 'dfsectorquarter.csv'
            elif has_only_years:
                data_source = 'dfsectoryear.csv'
            else:
                # Default to quarterly for mixed or latest
                data_source = 'dfsectorquarter.csv'
            
            return {
                'original_query': query,
                'tickers': parsed.get('tickers', []),
                'items': parsed.get('items', []),
                'keycodes': keycodes,
                'timeframe': timeframe,
                'data_source': data_source,
                'need_components': parsed.get('need_components', False)
            }
            
        except Exception as e:
            print(f"Error analyzing query: {e}")
            # Fallback to simple parsing
            return self._simple_parse(query)
    
    def _simple_parse(self, query: str) -> Dict[str, Any]:
        """Fallback simple parser if OpenAI fails"""
        query_upper = query.upper()
        
        # Extract tickers and sectors
        tickers = []
        common_tickers = ['VCB', 'BID', 'CTG', 'TCB', 'MBB', 'VPB', 'ACB', 'STB', 
                         'HDB', 'TPB', 'SHB', 'VIB', 'LPB', 'MSB', 'OCB', 'EIB']
        sectors = ['SECTOR', 'SOCB', 'PRIVATE_1', 'PRIVATE_2', 'PRIVATE_3']
        
        for ticker in common_tickers:
            if ticker in query_upper:
                tickers.append(ticker)
        
        for sector in sectors:
            if sector in query_upper.replace(' ', '_'):
                tickers.append(sector.replace('_', '_'))
        
        # Extract items
        items = []
        keycodes = []
        for item_name, keycode in self.keycode_mapping.items():
            if item_name in query_upper:
                items.append(item_name)
                keycodes.append(keycode)
        
        # Extract timeframe
        timeframe = self._get_latest_4_quarters()  # Default to latest 4 quarters
        quarter_pattern = r'[1-4]Q\d{2}'
        quarter_matches = re.findall(quarter_pattern, query_upper)
        
        if quarter_matches:
            timeframe = quarter_matches
            data_source = 'dfsectorquarter.csv'
        else:
            year_pattern = r'20\d{2}'
            year_matches = re.findall(year_pattern, query)
            if year_matches:
                # Check if "quarterly" is mentioned
                if 'QUARTERLY' in query_upper or 'QUARTER' in query_upper:
                    # Convert years to quarters
                    timeframe = []
                    for year in year_matches:
                        year_suffix = year[-2:]
                        timeframe.extend([f"1Q{year_suffix}", f"2Q{year_suffix}", f"3Q{year_suffix}", f"4Q{year_suffix}"])
                    data_source = 'dfsectorquarter.csv'
                else:
                    # Use yearly data
                    timeframe = year_matches
                    data_source = 'dfsectoryear.csv'
            else:
                data_source = 'dfsectorquarter.csv'
        
        # Check if need components (simple heuristic)
        need_components = False
        if any(word in query_upper for word in ['WHICH', 'AMONG', 'WITHIN', 'COMPARE', 'HIGHEST', 'LOWEST', 'BEST', 'WORST']):
            if any(sector in tickers for sector in ['SECTOR', 'SOCB', 'PRIVATE_1', 'PRIVATE_2', 'PRIVATE_3']):
                need_components = True
        
        return {
            'original_query': query,
            'tickers': tickers if tickers else [],
            'items': items,
            'keycodes': keycodes,
            'timeframe': timeframe,
            'data_source': data_source,
            'need_components': need_components
        }