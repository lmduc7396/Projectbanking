import pandas as pd
import requests
from datetime import datetime

def fetch_historical_price(ticker: str) -> pd.DataFrame:
    """Fetch stock historical price and volume data from TCBS API"""
    
    # TCBS API endpoint for historical data
    url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
    
    # Parameters for HPG stock - get more data for better visualization
    params = {
        "ticker": ticker,
        "type": "stock",
        "resolution": "D",  # Daily data
        "from": "0",
        "to": str(int(datetime.now().timestamp()))
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(data['data'])
            
            # Convert timestamp to datetime
            if 'tradingDate' in df.columns:
                # Check if tradingDate is already in ISO format
                if df['tradingDate'].dtype == 'object' and df['tradingDate'].str.contains('T').any():
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'])
                else:
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms')
            
            # Select relevant columns
            columns_to_keep = ['tradingDate', 'open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in columns_to_keep if col in df.columns]]
            
            return df
        else:
            print("No data found in response")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None