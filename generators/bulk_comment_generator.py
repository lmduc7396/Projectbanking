#%%
"""
Bulk Comment Generator - Jupyter-style interactive script
Generate AI-powered banking comments for multiple quarters
"""

import pandas as pd
import numpy as np
import openai
import os
from dotenv import load_dotenv
from datetime import datetime
import time
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utilities.quarter_utils import quarter_to_numeric, quarter_sort_key

#%% Load environment and data
load_dotenv()

# Get API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

client = openai.OpenAI(api_key=api_key)

# Load all data files
print("Loading data...")
df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
keyitem = pd.read_excel('Data/Key_items.xlsx')
bank_type_mapping = pd.read_excel('Data/Bank_Type.xlsx')

print(f"Loaded {len(df_quarter)} quarterly records")
print(f"Loaded {len(bank_type_mapping)} bank mappings")

#%% Create bank sector mapping
# Simple vectorized mapping creation
if 'TICKER' in bank_type_mapping.columns and 'Type' in bank_type_mapping.columns:
    bank_sector_map = dict(zip(bank_type_mapping['TICKER'], bank_type_mapping['Type']))
else:
    # Create mapping from data
    banks_df = df_quarter[df_quarter['TICKER'].str.len() == 3].copy()
    bank_sector_map = banks_df.groupby('TICKER')['Type'].first().to_dict()

print(f"Mapped {len(bank_sector_map)} banks to sectors")

#%% Helper functions for data operations

def get_available_quarters():
    """Get all available quarters sorted"""
    quarters = df_quarter['Date_Quarter'].unique()
    return sorted(quarters, key=quarter_sort_key)

def filter_quarters_by_range(start_quarter=None, end_quarter=None):
    """Filter quarters within a specific range using vectorized operations"""
    quarters_df = pd.DataFrame({'quarter': get_available_quarters()})
    quarters_df['quarter_numeric'] = quarters_df['quarter'].apply(quarter_to_numeric)
    
    # Apply filters if provided
    if start_quarter:
        start_numeric = quarter_to_numeric(start_quarter)
        quarters_df = quarters_df[quarters_df['quarter_numeric'] >= start_numeric]
    
    if end_quarter:
        end_numeric = quarter_to_numeric(end_quarter)
        quarters_df = quarters_df[quarters_df['quarter_numeric'] <= end_numeric]
    
    return quarters_df['quarter'].tolist()

def load_existing_comments():
    """Load existing comments from cache"""
    cache_file = 'Data/banking_comments.xlsx'
    if os.path.exists(cache_file):
        return pd.read_excel(cache_file)
    return pd.DataFrame(columns=['TICKER', 'SECTOR', 'QUARTER', 'COMMENT', 'GENERATED_AT'])

def save_comments(comments_df):
    """Save comments to cache file"""
    cache_file = 'Data/banking_comments.xlsx'
    comments_df.to_excel(cache_file, index=False)
    print(f"[Saved] {len(comments_df)} comments")

#%% Data preparation functions

def prepare_bank_quarter_data(ticker, quarter):
    """Prepare financial metrics for a specific bank and quarter"""
    # Define metrics to extract
    metrics_df = pd.DataFrame({
        'Name': ['Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE', 
                'NIM', 'Loan yield', 'NPL', 'NPL Formation (%)', 
                'GROUP 2', 'G2 Formation (%)', 'NPL Coverage ratio']
    })
    
    # Get KeyCode mappings
    metrics_with_codes = metrics_df.merge(keyitem, on='Name', how='left')
    cols_to_keep = ['Date_Quarter'] + metrics_with_codes['KeyCode'].tolist()
    
    # Filter bank data
    bank_data = df_quarter[df_quarter['TICKER'] == ticker][cols_to_keep].copy()
    
    # Filter to target quarter and previous 5 quarters
    bank_data['quarter_numeric'] = bank_data['Date_Quarter'].apply(quarter_to_numeric)
    target_numeric = quarter_to_numeric(quarter)
    bank_data = bank_data[bank_data['quarter_numeric'] <= target_numeric]
    bank_data = bank_data.nlargest(6, 'quarter_numeric')
    
    # Calculate growth metrics using vectorized operations
    for col in metrics_with_codes['KeyCode']:
        if col in bank_data.columns:
            # QoQ growth
            bank_data[f'{col}_qoq'] = bank_data[col].pct_change()
            # YoY growth
            bank_data[f'{col}_yoy'] = bank_data[col].pct_change(periods=4)
    
    return bank_data.sort_values('quarter_numeric').to_dict('records')

#%% OpenAI comment generation

def generate_single_comment(ticker, sector, quarter):
    """Generate a comment for a single bank and quarter"""
    try:
        # Get bank data
        data = prepare_bank_quarter_data(ticker, quarter)
        
        # Create prompt
        prompt = f"""Analyze the performance of {ticker} ({sector} bank) for {quarter}.

Financial data (last 6 quarters):
{data}

Provide a concise analysis covering:
1. Key performance metrics and trends
2. Asset quality assessment  
3. Profitability analysis
4. Main strengths and concerns
5. Forward outlook

Keep the analysis to 200-250 words."""
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a banking analyst expert. Provide concise but insightful analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error generating comment for {ticker} {quarter}: {e}")
        return None

#%% Bulk generation function

def generate_bulk_comments(start_quarter=None, end_quarter=None, overwrite_existing=False, banks_filter=None):
    """
    Generate comments for multiple banks and quarters using vectorized operations
    """
    # Get quarters to process
    quarters_to_process = filter_quarters_by_range(start_quarter, end_quarter)
    
    # Get banks to process
    banks_to_process = banks_filter if banks_filter else list(bank_sector_map.keys())
    
    # Load existing comments
    existing_comments = load_existing_comments()
    
    # Create combinations dataframe for processing
    combinations = pd.DataFrame([
        (bank, quarter) 
        for quarter in quarters_to_process 
        for bank in banks_to_process
    ], columns=['TICKER', 'QUARTER'])
    
    # Add sector information
    combinations['SECTOR'] = combinations['TICKER'].map(bank_sector_map)
    
    # Check existing comments if not overwriting
    if not overwrite_existing and not existing_comments.empty:
        # Create a key for matching
        combinations['key'] = combinations['TICKER'] + '_' + combinations['QUARTER']
        existing_comments['key'] = existing_comments['TICKER'] + '_' + existing_comments['QUARTER']
        existing_keys = set(existing_comments['key'])
        
        # Filter out existing combinations
        combinations = combinations[~combinations['key'].isin(existing_keys)]
        combinations = combinations.drop('key', axis=1)
    
    print(f"\n{'='*60}")
    print(f"Starting bulk comment generation")
    print(f"Banks: {len(banks_to_process)}")
    print(f"Quarters: {len(quarters_to_process)}")
    print(f"Combinations to process: {len(combinations)}")
    print(f"Overwrite existing: {overwrite_existing}")
    print(f"{'='*60}\n")
    
    # Generate comments
    new_comments = []
    total = len(combinations)
    
    for idx, row in combinations.iterrows():
        ticker = row['TICKER']
        quarter = row['QUARTER']
        sector = row['SECTOR']
        
        print(f"[{len(new_comments)+1}/{total}] {ticker} - {quarter}: Generating...", end='')
        
        comment = generate_single_comment(ticker, sector, quarter)
        
        if comment:
            new_comments.append({
                'TICKER': ticker,
                'SECTOR': sector,
                'QUARTER': quarter,
                'COMMENT': comment,
                'GENERATED_AT': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            print(" [Done]")
            
            # Save progress every 10 comments
            if len(new_comments) % 10 == 0:
                temp_df = pd.DataFrame(new_comments)
                if overwrite_existing:
                    # Remove old entries for these ticker-quarter combinations
                    mask = existing_comments.apply(
                        lambda x: not any((temp_df['TICKER'] == x['TICKER']) & 
                                         (temp_df['QUARTER'] == x['QUARTER'])), 
                        axis=1
                    )
                    existing_comments = existing_comments[mask]
                
                combined_df = pd.concat([existing_comments, temp_df], ignore_index=True)
                save_comments(combined_df)
        else:
            print(" [Failed]")
        
        # Rate limiting
        time.sleep(0.5)
    
    # Final save
    if new_comments:
        new_df = pd.DataFrame(new_comments)
        if overwrite_existing:
            # Remove old entries
            for _, row in new_df.iterrows():
                mask = ~((existing_comments['TICKER'] == row['TICKER']) & 
                        (existing_comments['QUARTER'] == row['QUARTER']))
                existing_comments = existing_comments[mask]
        
        final_df = pd.concat([existing_comments, new_df], ignore_index=True)
        save_comments(final_df)
    
    print(f"\n{'='*60}")
    print(f"[COMPLETE] Generation finished!")
    print(f"Generated {len(new_comments)} new comments")
    print(f"{'='*60}\n")
    
    return pd.DataFrame(new_comments)

#%% Main execution function

def main():
    """Main function with menu interface"""
    print("\n" + "="*60)
    print("BULK COMMENT GENERATOR")
    print("="*60)
    
    # Show available quarters
    available_quarters = get_available_quarters()
    print(f"\nAvailable quarters: {available_quarters[0]} to {available_quarters[-1]}")
    
    print("\nOptions:")
    print("1. Generate for ALL timeframes")
    print("2. Generate for SPECIFIC timeframe")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '1':
        # All timeframes
        print("\nGenerate for ALL timeframes")
        overwrite = input("Overwrite existing comments? (y/n): ").strip().lower() == 'y'
        
        result = generate_bulk_comments(
            start_quarter=None,
            end_quarter=None,
            overwrite_existing=overwrite
        )
        
    elif choice == '2':
        # Specific timeframe
        print("\nGenerate for SPECIFIC timeframe")
        print("Enter quarters in format like '1Q24' or press Enter to skip")
        
        start = input("Start quarter (or Enter for earliest): ").strip() or None
        end = input("End quarter (or Enter for latest): ").strip() or None
        overwrite = input("Overwrite existing comments? (y/n): ").strip().lower() == 'y'
        
        result = generate_bulk_comments(
            start_quarter=start,
            end_quarter=end,
            overwrite_existing=overwrite
        )
        
    else:
        print("Exiting...")

#%% Execute if run directly
if __name__ == "__main__":
    main()