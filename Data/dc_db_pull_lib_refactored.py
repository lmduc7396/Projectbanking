#%%
import pyodbc
import pandas as pd
from pathlib import Path
import platform
from typing import Dict, List, Optional

# Helper functions
def get_base_path():
    if platform.system() == 'Windows':
        return Path(r"c:\Users\ducle\OneDrive\Work-related\VS - Code project")

# Connection string
DIAMOND_STR = 'DRIVER={ODBC Driver 17 for SQL Server};Server=dcdwh-prod.sql.azuresynapse.net;Database=dcdwhproddedicatedpool;UID=researchlogin;PWD=353fsf*($%#sfsfe;MultipleActiveResultSets=true;Command Timeout=300;'

# Project configuration
PROJECT_SUBDIR = "DAILY DATA"

# Query configurations
QUERY_CONFIG = {
    'FA_Q_FULL': {
        'base_query': """SELECT KEYCODE, TICKER, DATE, VALUE FROM SIL.W_F_FIN_FINANCIAL_STATEMENT""",
        'incremental_filter': "WHERE DATE = '{latest_quarter}'",
        'dedupe_columns': ['KEYCODE', 'TICKER', 'DATE'],
        'date_format': 'quarter'
    },
    'MARKET_CAP': {
        'base_query': """SELECT [PRIMARYSECID], [CUR_MKT_CAP], [TRADE_DATE]
                         FROM [SIL].[S_BBG_DATA_DWH_ADJUSTED]
                         WHERE [PRIMARYSECID] LIKE '%VN Equity%'
                         AND TRADE_DATE >= '2025-01-01'""",
        'incremental_filter': "AND TRADE_DATE >= '{start_date}'",
        'dedupe_columns': ['PRIMARYSECID', 'TRADE_DATE'],
        'date_format': 'date',
        'default_start_date': '2025-01-01'
    },
    'VALUATION': {
        'base_query': """SELECT PRIMARYSECID, TRADE_DATE, PE_RATIO, PX_TO_BOOK_RATIO, PX_TO_SALES_RATIO 
                         FROM SIL.S_BBG_DATA_DWH_ADJUSTED
                         WHERE PRIMARYSECID LIKE '%VN Equity'
                         AND TRADE_DATE >= '2018-01-01'""",
        'incremental_filter': "AND TRADE_DATE >= '{start_date}'",
        'dedupe_columns': ['PRIMARYSECID', 'TRADE_DATE'],
        'date_format': 'date',
        'default_start_date': '2018-01-01'
    },
    'EVEBITDA': {
        'base_query': """SELECT * FROM SIL.W_F_IRIS_CALCULATE
                         WHERE DATE >= '2018-01-01'""",
        'incremental_filter': "AND DATE >= '{start_date}'",
        'dedupe_columns': ['TICKER', 'DATE'],
        'date_format': 'date',
        'default_start_date': '2018-01-01'
    },
    'INDEX': {
        'base_query': """SELECT [COMGROUPCODE], [INDEXVALUE], [TRADINGDATE], [INDEXCHANGE], 
                         [PERCENTINDEXCHANGE], [REFERENCEINDEX], [OPENINDEX], [CLOSEINDEX],
                         [HIGHESTINDEX], [LOWESTINDEX], [TOTALMATCHVOLUME], [TOTALMATCHVALUE],
                         [TOTALDEALVOLUME], [TOTALDEALVALUE], [TOTALVOLUME], [TOTALVALUE],
                         [TOTALSTOCKUPPRICE], [TOTALSTOCKDOWNPRICE], [TOTALSTOCKNOCHANGEPRICE],
                         [TOTALUPVOLUME], [TOTALDOWNVOLUME], [TOTALNOCHANGEVOLUME],
                         [FOREIGNBUYVALUEMATCHED], [FOREIGNBUYVOLUMEMATCHED], [FOREIGNSELLVALUEMATCHED],
                         [FOREIGNSELLVOLUMEMATCHED], [FOREIGNBUYVALUETOTAL], [FOREIGNBUYVOLUMETOTAL],
                         [FOREIGNSELLVALUETOTAL], [FOREIGNSELLVOLUMETOTAL]
                         FROM [dbo].[S_SPS_HOSEINDEX]
                         WHERE TRADINGDATE >= '2018-01-01'""",
        'incremental_filter': "AND TRADINGDATE >= '{start_date}'",
        'dedupe_columns': ['COMGROUPCODE', 'TRADINGDATE'],
        'date_format': 'date',
        'default_start_date': '2018-01-01'
    }
}

# Bank queries (always full refresh)
BANK_QUERIES = {
    'Bank_BALANCESHEET': 'SELECT * FROM S_SPS_BALANCESHEET_BANK',
    'Bank_INCOMESTATEMENT': 'SELECT * FROM S_SPS_INCOMESTATEMENT_BANK',
    'Bank_NOTE': 'SELECT * FROM S_SPS_NOTE_BANK'
}

# Date format requirements:
# - For quarterly data: 'YYYYQX' format (e.g., '2025Q2')
# - For daily data: 'YYYY-MM-DD' format (e.g., '2025-07-15')

def load_data(query: str) -> Optional[pd.DataFrame]:
    """Load data from the database using the provided query."""
    try:
        connection = pyodbc.connect(DIAMOND_STR)
        print("Connection successful!")
        
        data = pd.read_sql(query, connection)
        print(f"Data loaded successfully. Shape: {data.shape}")
        
        connection.close()
        return data
        
    except pyodbc.Error as e:
        print(f"Database error: {e}")
        return None
    except Exception as e:
        print(f"General error: {e}")
        return None

def to_csv(df: pd.DataFrame, file_name: str):
    """Export DataFrame to CSV."""
    if df is None:
        print(f"Cannot save {file_name}: No data available")
        return
    
    output_dir = get_base_path() / PROJECT_SUBDIR 
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_dir / f"{file_name}.csv", index=False)
    print(f"Saved to {output_dir / f'{file_name}.csv'}")

def merge_and_deduplicate(new_df: pd.DataFrame, existing_file_name: str, 
                         dedupe_columns: List[str]) -> Optional[pd.DataFrame]:
    """Merge new dataframe with existing CSV file and remove duplicates."""
    if new_df is None:
        print(f"Cannot merge {existing_file_name}: No new data available")
        return None
    
    try:
        existing_path = get_base_path() / PROJECT_SUBDIR / f"{existing_file_name}.csv"
        existing_df = pd.read_csv(existing_path)
        merged_df = pd.concat([existing_df, new_df], ignore_index=True)
        final_df = merged_df.drop_duplicates(subset=dedupe_columns, keep='last')
        final_df.to_csv(existing_path, index=False)
        print(f"Merged and saved to {existing_path}")
        print(f"Previous records: {len(existing_df)}, New records: {len(new_df)}, Final records: {len(final_df)}")
        return final_df
    except FileNotFoundError:
        print(f"Existing file not found, saving new data as {existing_file_name}.csv")
        to_csv(new_df, existing_file_name)
        return new_df

def build_query(config: Dict, incremental: bool = False, incremental_date: Optional[str] = None) -> str:
    """Build the appropriate query based on refresh type."""
    query = config['base_query']
    
    if incremental and 'incremental_filter' in config and incremental_date:
        if config['date_format'] == 'quarter':
            filter_clause = config['incremental_filter'].format(latest_quarter=incremental_date)
        else:
            filter_clause = config['incremental_filter'].format(start_date=incremental_date)
        
        # For queries with default_start_date, replace the default date with the incremental date
        if 'default_start_date' in config:
            query = query.replace(config['default_start_date'], incremental_date)
        else:
            # Add WHERE clause or append to existing WHERE
            if 'WHERE' in query.upper():
                query += f" {filter_clause}"
            else:
                query += f" {filter_clause}"
    
    return query

#%% Refresh functions
def full_refresh(query_name: str):
    """Perform a full refresh for a specific query."""
    if query_name in QUERY_CONFIG:
        config = QUERY_CONFIG[query_name]
        query = build_query(config, incremental=False)
        df = load_data(query)
        if df is not None:
            to_csv(df, query_name)
    else:
        print(f"Query {query_name} not found in configuration")

def full_refresh_all():
    """Perform full refresh for all configured queries."""
    # Process configured queries
    for query_name, config in QUERY_CONFIG.items():
        print(f"\n{'='*60}")
        print(f"Full refresh: {query_name}")
        full_refresh(query_name)
    
    # Process bank queries (always full refresh)
    print(f"\n{'='*60}")
    print("Processing Bank Data")
    for query_name, query in BANK_QUERIES.items():
        df = load_data(query)
        to_csv(df, query_name)

def incremental_update(query_name: str, date_filter: str):
    """
    Perform incremental update for a specific query.
    
    Args:
        query_name: Name of the query from QUERY_CONFIG
        date_filter: Date filter in appropriate format:
                    - For quarterly data: 'YYYYQX' (e.g., '2025Q2')
                    - For daily data: 'YYYY-MM-DD' (e.g., '2025-07-15')
    """
    if query_name not in QUERY_CONFIG:
        print(f"Query {query_name} not found in configuration")
        return
    
    config = QUERY_CONFIG[query_name]
    
    print(f"Incremental update from: {date_filter}")
    query = build_query(config, incremental=True, incremental_date=date_filter)
    df = load_data(query)
    
    if df is not None:
        merge_and_deduplicate(df, query_name, config['dedupe_columns'])

def full_refresh_banks():
    """Perform full refresh for Bank data only."""
    print(f"\n{'='*60}")
    print("Processing Bank Data (Full Refresh)")
    print(f"{'='*60}")
    
    for query_name, query in BANK_QUERIES.items():
        print(f"\nProcessing: {query_name}")
        df = load_data(query)
        to_csv(df, query_name)
        
    print(f"\n{'='*60}")
    print("Bank data refresh completed!")

#%% Example usage
if __name__ == "__main__":
    # Examples of different usage patterns:
    
    # 1. Full refresh everything (includes all data + banks)
    # full_refresh_all()
    
    # 2. Full refresh Bank data only
    full_refresh_banks()
    
    # 3. Full refresh specific query
    # full_refresh('MARKET_CAP')
    
    # 4. Incremental update with date filter
    # incremental_update('VALUATION', '2025-07-15')  # Daily data from this date
    # incremental_update('EVEBITDA', '2025-07-15')  # Daily data from this date
    incremental_update('FA_Q_FULL', '2025Q2')      # Quarterly data for Q2 2025
    # incremental_update('MARKET_CAP', '2025-07-15')  # Daily data from this date
    
