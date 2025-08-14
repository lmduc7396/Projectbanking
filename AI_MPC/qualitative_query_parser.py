#%% Import libraries
import json
from typing import Dict, List, Any

def parse_qualitative_query(user_question: str, client, latest_quarter: str, latest_4_quarters: List[str]) -> Dict[str, Any]:
    """
    Parse a qualitative banking question to extract tickers, timeframe, and valuation flag
    
    Args:
        user_question: The user's question
        client: OpenAI client instance
        latest_quarter: The latest available quarter string
        latest_4_quarters: List of the latest 4 quarters
    
    Returns:
        Dictionary with parsed information:
        - tickers: List of bank codes or sector names
        - timeframe: List of quarters
        - has_sectors: Boolean indicating if sectors are mentioned
        - valuation: Boolean indicating if valuation metrics are needed
    """
    
    parse_prompt = f"""
Analyze this qualitative banking question and extract:
1. TICKERS: List ALL bank codes or sector names mentioned. Valid sectors are:
   - Sector (overall banking sector)
   - SOCB (state-owned commercial banks)
   - Private_1, Private_2, Private_3 (private bank groups)
   IMPORTANT: 
   - Return ALL tickers mentioned in the question as a list
   - Preserve the exact format with underscore for Private sectors (e.g., "Private_1" not "Private 1")
   
2. TIMEFRAME: List of quarters mentioned (e.g., ["1Q24", "2Q24"])
   - If "current" or "latest", return ["{latest_quarter}"]
   - If no timeframe, return latest 4 quarters: {latest_4_quarters}

3. VALUATION: Boolean - true if the question is about valuation metrics (e.g., P/E, P/B)
    - true if mentioned valuation terms like "P/E", "P/B", "valuation", "metrics"
    - true if user ask for investment recommendation
    - false otherwise

4. NEED_COMPONENTS: Boolean - true if the question requires individual bank data within a sector
   - true if asking for comparisons WITHIN a sector (e.g., "which bank in SOCB", "among all Private_1 banks")
   - true if asking "which one", "best among", "worst in", "ranking within"
   - true if the question implies selecting or comparing individual banks within a sector group
   - false if only asking about sector-level aggregated analysis

Question: "{user_question}"

Return JSON: {{"tickers": [...], "timeframe": [...], "has_sectors": true/false, "valuation": true/false, "need_components": true/false}}


"""
    
    parse_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Extract structured data from banking questions."},
            {"role": "user", "content": parse_prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )
    
    parsed = json.loads(parse_response.choices[0].message.content)
    
    # Ensure tickers preserve underscores for Private sectors
    tickers = parsed.get('tickers', [])
    normalized_tickers = []
    for ticker in tickers:
        if ticker.startswith('Private'):
            # Normalize Private sector format
            ticker_parts = ticker.replace(' ', '_').split('_')
            if len(ticker_parts) >= 2 and ticker_parts[1].isdigit():
                normalized_tickers.append(f"Private_{ticker_parts[1]}")
            else:
                normalized_tickers.append(ticker)
        else:
            normalized_tickers.append(ticker)
    parsed['tickers'] = normalized_tickers
    
    return parsed