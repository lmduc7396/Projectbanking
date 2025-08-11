#!/usr/bin/env python3
"""
Test TCBS API integration for Vietnamese bank stocks
"""

import pandas as pd
import requests
from datetime import datetime, timedelta

def test_fetch_stock(ticker: str, days: int = 30):
    """Test fetching stock data from TCBS API"""
    
    print(f"\nTesting TCBS API for ticker: {ticker}")
    print("=" * 50)
    
    # TCBS API endpoint
    url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
    
    # Calculate timestamps
    from_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
    to_timestamp = int(datetime.now().timestamp())
    
    params = {
        "ticker": ticker,
        "type": "stock",
        "resolution": "D",
        "from": str(from_timestamp),
        "to": str(to_timestamp)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data and data['data']:
            df = pd.DataFrame(data['data'])
            
            # Convert timestamp to datetime
            if 'tradingDate' in df.columns:
                if df['tradingDate'].dtype == 'object' and isinstance(df['tradingDate'].iloc[0], str) and 'T' in df['tradingDate'].iloc[0]:
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'])
                else:
                    df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms')
            
            # Select relevant columns
            columns_to_keep = ['tradingDate', 'open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in columns_to_keep if col in df.columns]]
            
            print(f"✓ Successfully fetched {len(df)} days of data")
            print(f"\nLatest 5 days:")
            print(df.tail(5).to_string(index=False))
            
            # Show statistics
            latest = df.iloc[-1]
            first = df.iloc[0]
            price_change = ((latest['close'] - first['close']) / first['close'] * 100)
            
            print(f"\nStatistics:")
            print(f"  Latest Close: {latest['close']:,.0f} VND")
            print(f"  Period Change: {price_change:+.2f}%")
            print(f"  Highest: {df['high'].max():,.0f} VND")
            print(f"  Lowest: {df['low'].min():,.0f} VND")
            print(f"  Avg Volume: {df['volume'].mean():,.0f}")
            
            return True
        else:
            print(f"✗ No data returned for {ticker}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Network error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

# Test with common Vietnamese bank tickers
test_banks = [
    "ACB",  # Asia Commercial Bank
    "VCB",  # Vietcombank
    "BID",  # BIDV
    "TCB",  # Techcombank
    "VPB",  # VPBank
]

print("Testing TCBS API with Vietnamese Bank Stocks")
print("=" * 50)

success_count = 0
for ticker in test_banks:
    if test_fetch_stock(ticker, days=30):
        success_count += 1

print("\n" + "=" * 50)
print(f"Summary: {success_count}/{len(test_banks)} tickers successfully fetched data")

if success_count == len(test_banks):
    print("✓ All tests passed! API integration is working correctly.")
else:
    print("⚠ Some tickers failed. Check network connection or ticker symbols.")