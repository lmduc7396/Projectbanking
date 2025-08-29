import pandas as pd
import numpy as np
import openai
import os
from dotenv import load_dotenv
from datetime import datetime
import time
import sys

# Add parent directory to path for utilities import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utilities.quarter_utils import quarter_to_numeric, quarter_sort_key

# Load environment variables
load_dotenv()

# Get project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_dir = os.path.join(project_root, 'Data')

# Load data
print("Loading data...")
df_quarter = pd.read_parquet(os.path.join(data_dir, 'dfsectorquarter.parquet'))
keyitem = pd.read_excel(os.path.join(data_dir, 'Key_items.xlsx'))
bank_type_mapping = pd.read_excel(os.path.join(data_dir, 'Bank_Type.xlsx'))

# Load earnings quality data for QoQ earnings drivers
df_earnings_quality = pd.read_parquet(os.path.join(data_dir, 'earnings_quality_quarterly.parquet'))
print(f"Loaded earnings quality data with {len(df_earnings_quality)} records")

print(f"Bank Type mapping structure:")
print(bank_type_mapping.head())
print(f"Columns: {bank_type_mapping.columns.tolist()}")

def get_bank_sector_mapping():
    """Create a mapping of bank tickers to their sectors"""
    mapping = {}
    
    # First, get individual banks from Bank_Type.xlsx
    if 'TICKER' in bank_type_mapping.columns and 'Type' in bank_type_mapping.columns:
        for _, row in bank_type_mapping.iterrows():
            mapping[row['TICKER']] = row['Type']
    
    # Then add all unique tickers from the data (including sectors)
    all_tickers = df_quarter['TICKER'].unique()
    for ticker in all_tickers:
        if ticker not in mapping:
            # For tickers not in Bank_Type (like sectors), use their Type from the data
            ticker_data = df_quarter[df_quarter['TICKER'] == ticker]
            if not ticker_data.empty:
                # For sectors (len > 3), mark as 'Sector'
                if len(str(ticker)) > 3:
                    mapping[ticker] = 'Sector'
                else:
                    # For individual banks, use their Type
                    mapping[ticker] = ticker_data['Type'].iloc[0]
    
    return mapping

def get_quarters_from_2023():
    """Get all quarters from Q1 2023 to most recent quarter"""
    # Extract all unique quarters and sort them
    quarters = df_quarter['Date_Quarter'].unique()
    
    # Filter quarters from 2023 onwards
    quarters_2023_plus = []
    for q in quarters:
        numeric_q = quarter_to_numeric(q)
        if numeric_q >= 20231:  # 2023 Q1
            quarters_2023_plus.append(q)
    
    # Sort quarters using utility function
    quarters_2023_plus.sort(key=quarter_sort_key)
    return quarters_2023_plus

def openai_comment_bulk(ticker, sector, quarter, df_quarter_data, keyitem_data, df_earnings_data):
    """Modified version of openai_comment for bulk processing"""
    
    def get_data(ticker, target_quarter):
        # The data already has proper column names, no need for KeyCode mapping
        cols_keep = [
            'Date_Quarter', 'Loan', 'TOI', 'Provision/ Total Loan', 'PBT', 
            'ROA', 'ROE', 'NIM', 'Loan yield', 'NPL', 'New NPL', 
            'GROUP 2', 'New G2', 'NPL Coverage ratio'
        ]
        
        # Check which columns are actually available in the data
        available_cols = df_quarter_data.columns.tolist()
        cols_keep_final = [col for col in cols_keep if col in available_cols]
        
        # If Provision expense is not available, use Provision/ Total Loan
        if 'Provision expense' not in cols_keep_final and 'Provision/ Total Loan' in cols_keep_final:
            # Keep as is - the column is already named appropriately
            pass

        # Helper functions for growth calculations
        def calculate_growth(df_data, period, suffix):
            """Calculate growth (%) and return formatted DataFrame."""
            growth = df_data.iloc[:, 1:].pct_change(periods=period)
            growth = growth.add_suffix(f' {suffix} (%)')
            return pd.concat([df_data['Date_Quarter'], growth], axis=1)

        def calculate_ytd_growth(df_data):
            """Calculate YTD growth (%) from current quarter to Q4 of previous year."""
            df_filtered = df_data.copy()
            
            # Extract year and quarter from Date_Quarter (format: YYYY-Q#)
            df_filtered['Year'] = df_filtered['Date_Quarter'].str.extract(r'(\d{4})-Q').astype(int)
            df_filtered['Quarter'] = df_filtered['Date_Quarter'].str.extract(r'-Q(\d)').astype(int)
            
            # Calculate YTD growth for Loan only
            ytd_growth = pd.DataFrame(index=df_filtered.index)
            ytd_growth['Date_Quarter'] = df_filtered['Date_Quarter']
            
            # Loan column is directly named 'Loan' in the data
            loan_col = 'Loan' if 'Loan' in df_filtered.columns else None
            
            if loan_col:
                ytd_growth['Loan YTD (%)'] = np.nan
                
                for i in range(len(df_filtered)):
                    current_year = df_filtered.iloc[i]['Year']
                    current_value = df_filtered.iloc[i][loan_col]
                    
                    # Find Q4 of previous year
                    prev_year_q4 = df_filtered[
                        (df_filtered['Year'] == current_year - 1) & 
                        (df_filtered['Quarter'] == 4)
                    ]
                    
                    if not prev_year_q4.empty and pd.notnull(current_value):
                        prev_q4_value = prev_year_q4.iloc[0][loan_col]
                        if pd.notnull(prev_q4_value) and prev_q4_value != 0:
                            ytd_growth.iloc[i, ytd_growth.columns.get_loc('Loan YTD (%)')] = \
                                (current_value - prev_q4_value) / prev_q4_value
            
            return ytd_growth[['Date_Quarter'] + [col for col in ytd_growth.columns if 'YTD (%)' in col]]

        # Get ticker data up to target quarter
        df_ticker = df_quarter_data[df_quarter_data['TICKER'] == ticker]
        
        # Select only the columns we want to keep
        df_ticker = df_ticker[cols_keep_final]
        
        # Sort by date and get data up to target quarter
        # Filter data up to target quarter
        target_numeric = quarter_to_numeric(target_quarter)
        df_ticker['quarter_numeric'] = df_ticker['Date_Quarter'].apply(quarter_to_numeric)
        df_ticker = df_ticker[df_ticker['quarter_numeric'] <= target_numeric]
        df_ticker = df_ticker.sort_values('quarter_numeric')
        df_ticker = df_ticker.drop('quarter_numeric', axis=1)
        
        # Take last 6 quarters for analysis (no renaming needed as columns already have proper names)
        df_ticker_base = df_ticker.tail(6)
        
        # Calculate growth metrics for ticker
        df_ticker_qoq = calculate_growth(df_ticker.tail(6), 1, 'QoQ')
        df_ticker_yoy = calculate_growth(df_ticker.tail(6), 4, 'YoY')
        df_ticker_ytd = calculate_ytd_growth(df_ticker.tail(6))
        
        # Combine ticker data with growth metrics
        ticker_combined = df_ticker_base.copy()
        
        # Add specific growth columns
        if not df_ticker_qoq.empty:
            # Note: Use the actual column names in the data
            for metric in ['Loan', 'TOI', 'Provision/ Total Loan', 'PBT']:
                qoq_col = f'{metric} QoQ (%)'
                if qoq_col in df_ticker_qoq.columns:
                    ticker_combined[qoq_col] = df_ticker_qoq[qoq_col]
        
        if not df_ticker_yoy.empty:
            for metric in ['TOI', 'Provision/ Total Loan', 'PBT']:
                yoy_col = f'{metric} YoY (%)'
                if yoy_col in df_ticker_yoy.columns:
                    ticker_combined[yoy_col] = df_ticker_yoy[yoy_col]
        
        if not df_ticker_ytd.empty:
            if 'Loan YTD (%)' in df_ticker_ytd.columns:
                ticker_combined['Loan YTD (%)'] = df_ticker_ytd['Loan YTD (%)']
        
        # Transpose ticker data
        df_ticker_out = ticker_combined.T
        df_ticker_out.columns = df_ticker_out.iloc[0]
        df_ticker_out = df_ticker_out[1:]
        
        return df_ticker_out

    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    client = openai.OpenAI(api_key=api_key)
    
    # Get ticker data
    ticker_data = get_data(ticker, quarter)
    
    # Get earnings driver data for the ticker and quarter
    earnings_drivers = None
    earnings_data = df_earnings_data[
        (df_earnings_data['TICKER'] == ticker) & 
        (df_earnings_data['Date_Quarter'] == quarter)
    ]
    
    if not earnings_data.empty:
        # Extract QoQ WEIGHTED IMPACT scores (not raw scores)
        # These show actual percentage point contribution to PBT growth
        earnings_drivers = {
            'PBT_Growth_QoQ': earnings_data['PBT_Growth_%_QoQ'].iloc[0] if 'PBT_Growth_%_QoQ' in earnings_data.columns else None,
            'Main_Components': {
                'Top_Line_Impact': earnings_data['Top_Line_Impact_QoQ'].iloc[0] if 'Top_Line_Impact_QoQ' in earnings_data.columns else None,
                'Cost_Cutting_Impact': earnings_data['Cost_Cutting_Impact_QoQ'].iloc[0] if 'Cost_Cutting_Impact_QoQ' in earnings_data.columns else None,
                'Non_Recurring_Impact': earnings_data['Non_Recurring_Impact_QoQ'].iloc[0] if 'Non_Recurring_Impact_QoQ' in earnings_data.columns else None
            },
            'Revenue_Breakdown': {
                'NII_Impact': earnings_data['NII_Impact_QoQ'].iloc[0] if 'NII_Impact_QoQ' in earnings_data.columns else None,
                'Fee_Impact': earnings_data['Fee_Impact_QoQ'].iloc[0] if 'Fee_Impact_QoQ' in earnings_data.columns else None
            },
            'NII_Breakdown': {
                'Loan_Impact': earnings_data['Loan_Impact_QoQ'].iloc[0] if 'Loan_Impact_QoQ' in earnings_data.columns else None,
                'NIM_Impact': earnings_data['NIM_Impact_QoQ'].iloc[0] if 'NIM_Impact_QoQ' in earnings_data.columns else None
            },
            'Cost_Breakdown': {
                'OPEX_Impact': earnings_data['OPEX_Impact_QoQ'].iloc[0] if 'OPEX_Impact_QoQ' in earnings_data.columns else None,
                'Provision_Impact': earnings_data['Provision_Impact_QoQ'].iloc[0] if 'Provision_Impact_QoQ' in earnings_data.columns else None
            },
            'Total_Impact': earnings_data['Total_Impact_QoQ'].iloc[0] if 'Total_Impact_QoQ' in earnings_data.columns else None
        }
        
        # Clean up None values - format as percentage points
        def clean_none(value, suffix="pp"):
            if pd.isna(value) or value is None:
                return "N/A"
            # For PBT Growth %, use % suffix
            if suffix == "%":
                return f"{value:.1f}%"
            # For impacts, use pp (percentage points)
            return f"{value:.1f}pp"
        
        # Format all values
        if earnings_drivers:
            earnings_drivers['PBT_Growth_QoQ'] = clean_none(earnings_drivers['PBT_Growth_QoQ'], "%")
            earnings_drivers['Total_Impact'] = clean_none(earnings_drivers['Total_Impact'])
            for key in earnings_drivers['Main_Components']:
                earnings_drivers['Main_Components'][key] = clean_none(earnings_drivers['Main_Components'][key])
            for key in earnings_drivers['Revenue_Breakdown']:
                earnings_drivers['Revenue_Breakdown'][key] = clean_none(earnings_drivers['Revenue_Breakdown'][key])
            for key in earnings_drivers['NII_Breakdown']:
                earnings_drivers['NII_Breakdown'][key] = clean_none(earnings_drivers['NII_Breakdown'][key])
            for key in earnings_drivers['Cost_Breakdown']:
                earnings_drivers['Cost_Breakdown'][key] = clean_none(earnings_drivers['Cost_Breakdown'][key])
    
    # No longer loading writing examples
    
    # Create earnings drivers table
    earnings_drivers_text = ""
    if earnings_drivers:
        earnings_drivers_text = f"""
Earnings Drivers (QoQ):
PBT Growth: {earnings_drivers['PBT_Growth_QoQ']}

Component | Impact
--- | ---
Top Line (Revenue) | {earnings_drivers['Main_Components']['Top_Line_Impact']}
- NII | {earnings_drivers['Revenue_Breakdown']['NII_Impact']}
  - Loan Growth | {earnings_drivers['NII_Breakdown']['Loan_Impact']}
  - NIM | {earnings_drivers['NII_Breakdown']['NIM_Impact']}
- Fee Income | {earnings_drivers['Revenue_Breakdown']['Fee_Impact']}
Cost Cutting | {earnings_drivers['Main_Components']['Cost_Cutting_Impact']}
- OPEX | {earnings_drivers['Cost_Breakdown']['OPEX_Impact']}
- Provisions | {earnings_drivers['Cost_Breakdown']['Provision_Impact']}
Non-Recurring | {earnings_drivers['Main_Components']['Non_Recurring_Impact']}
"""
    
    prompt = f"""
    You are a financial analyst specializing in the banking sector. Analyze quarterly bank results from the provided data (financial metrics, ratios, and earnings drivers).
    Your answer must follow this structure exactly. Do not add or remove sections.

    1. Conclusion (exactly 3 bullet points)
        Write these bullets as a story-driven investor takeaway.
        Focus on the big picture: what kind of quarter this was, what drove it, and how sustainable it looks.
        Keep numbers supportive, but not the headline. (Example: “Profit rebound looks strong, but much of it came from one-offs, raising questions about repeatability.” instead of “PBT +33% QoQ.”)
        Tone must be punchy, neutral, analytical.

    2. Profitability
        Present TOI, PBT, ROA, ROE trends with interpretation.
        Use the earnings bridge (Revenue, Cost, Non-recurring) to explain what really changed.
        Each bullet must combine data and meaning.

    3. Loan Growth & NIM
        Present loan growth (QoQ, YoY) and loan book size.
        Show NIM and yield evolution, linking to funding dynamics.
        Explain how volume vs margin balance is shaping income.

    4. Asset Quality
        Present NPL and Group-2 ratios, formation trends, provisions, coverage.
        Each bullet must integrate figures with implications for credit risk and earnings durability.


    Writing Approach Rules
        Conclusion = story first, numbers second.
        Each bullet across all sections must weave number + meaning in one line.
        Avoid mechanical breakdowns of every bridge component; focus only on what matters most.
        Keep style punchy, concise, and investment-oriented.
    
    Data for Bank: {ticker} (Quarter: {quarter})
    {ticker_data.to_markdown(index=True, tablefmt='grid')}
    
    {earnings_drivers_text}

    Format Guidelines:
    - Use one decimal point for percentages (e.g., 15.7%) when citing specific figures
    - Keep analysis factual and data-driven

    """

    # Send to OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a financial analyst."},
                {"role": "user", "content": prompt}
            ]
            # Note: GPT-5 only supports default temperature (1.0)
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API for {ticker} {quarter}: {str(e)}")
        return None

def generate_all_comments(specific_quarters=None):
    """Generate comments for all banks and all quarters
    
    Args:
        specific_quarters: Optional list of quarters to generate (e.g., ['2025-Q1', '2025-Q2'])
                          If None, generates for all quarters from 2023 onwards
    """
    
    print("Getting bank-sector mapping...")
    bank_sector_mapping = get_bank_sector_mapping()
    print(f"Found {len(bank_sector_mapping)} entities (banks and sectors)")
    
    if specific_quarters:
        print(f"Generating for specific quarters: {specific_quarters}")
        quarters = specific_quarters
    else:
        print("Getting quarters from 2023...")
        quarters = get_quarters_from_2023()
    print(f"Found {len(quarters)} quarters: {quarters}")
    
    # Get ALL tickers (both individual banks and sectors)
    all_tickers = list(bank_sector_mapping.keys())
    print(f"Processing {len(all_tickers)} tickers (including individual banks and sectors)")
    
    # Check if comments file already exists
    comments_file = 'Data/banking_comments.parquet'
    if os.path.exists(comments_file):
        existing_comments = pd.read_parquet(comments_file)
        print(f"Found existing comments file with {len(existing_comments)} entries")
    else:
        existing_comments = pd.DataFrame(columns=['TICKER', 'SECTOR', 'QUARTER', 'COMMENT', 'GENERATED_DATE'])
        print("Creating new comments file")
    
    # Prepare results list
    all_comments = []
    total_combinations = len(all_tickers) * len(quarters)
    processed = 0
    errors = 0
    
    print(f"Starting bulk generation for {total_combinations} combinations...")
    
    for ticker in all_tickers:
        sector = bank_sector_mapping.get(ticker, 'Unknown')
        
        for quarter in quarters:
            processed += 1
            
            # Check if comment already exists
            existing_entry = existing_comments[
                (existing_comments['TICKER'] == ticker) & 
                (existing_comments['QUARTER'] == quarter)
            ]
            
            if not existing_entry.empty:
                print(f"[{processed}/{total_combinations}] Skipping {ticker} {quarter} - already exists")
                # Add existing comment to results
                all_comments.append({
                    'TICKER': ticker,
                    'SECTOR': sector,
                    'QUARTER': quarter,
                    'COMMENT': existing_entry.iloc[0]['COMMENT'],
                    'GENERATED_DATE': existing_entry.iloc[0]['GENERATED_DATE']
                })
                continue
            
            print(f"[{processed}/{total_combinations}] Generating comment for {ticker} ({sector}) - {quarter}")
            
            try:
                # Check if bank has data for this quarter
                bank_data = df_quarter[
                    (df_quarter['TICKER'] == ticker) & 
                    (df_quarter['Date_Quarter'] == quarter)
                ]
                
                if bank_data.empty:
                    print(f"  No data found for {ticker} in {quarter} - skipping")
                    continue
                
                comment = openai_comment_bulk(ticker, sector, quarter, df_quarter, keyitem, df_earnings_quality)
                
                if comment:
                    all_comments.append({
                        'TICKER': ticker,
                        'SECTOR': sector,
                        'QUARTER': quarter,
                        'COMMENT': comment,
                        'GENERATED_DATE': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    print(f"  ✓ Generated successfully")
                else:
                    errors += 1
                    print(f"  ✗ Failed to generate comment")
                
                # Add small delay to avoid rate limiting
                time.sleep(1)
                
            except Exception as e:
                errors += 1
                print(f"  ✗ Error: {str(e)}")
                continue
            
            # Save progress every 10 comments
            if processed % 10 == 0:
                temp_df = pd.DataFrame(all_comments)
                temp_df.to_parquet(f"Data/banking_comments_temp_{processed}.parquet", index=False, engine='pyarrow', compression='snappy')
                print(f"  Saved temporary progress: {len(all_comments)} comments")
    
    # Save final results
    if all_comments:
        final_df = pd.DataFrame(all_comments)
        final_df.to_parquet(comments_file, index=False, engine='pyarrow', compression='snappy')
        print(f"\n✓ Completed! Generated {len(all_comments)} total comments")
        print(f"✓ Saved to: {comments_file}")
        print(f"✗ Errors encountered: {errors}")
        
        # Show summary statistics
        print(f"\nSummary:")
        print(f"- Total banks: {final_df['TICKER'].nunique()}")
        print(f"- Total quarters: {final_df['QUARTER'].nunique()}")
        print(f"- Total comments: {len(final_df)}")
        print(f"- Comments by sector:")
        print(final_df['SECTOR'].value_counts())
        
        return final_df
    else:
        print("\n✗ No comments were generated")
        return None

def run_with_confirmation():
    """Run with user confirmation"""
    print("Starting bulk comment generation...")
    print("This may take a while depending on the number of banks and quarters...")
    
    # Ask for confirmation
    response = input("\nDo you want to proceed with bulk generation? (y/n): ")
    if response.lower() == 'y':
        result = generate_all_comments()
        return result
    else:
        print("Generation cancelled.")
        return None

# Create wrapper class for compatibility with run_generators.py
class BulkCommentGenerator:
    """Wrapper class to maintain compatibility with run_generators.py"""
    
    def __init__(self):
        pass
    
    def get_available_quarters(self):
        """Get available quarters from 2023 onwards"""
        return get_quarters_from_2023()
    
    def generate_bulk_comments(self, start_quarter=None, end_quarter=None, overwrite_existing=False, specific_quarters=None):
        """Generate comments for specified range
        
        Args:
            start_quarter: Start quarter for generation (unused if specific_quarters provided)
            end_quarter: End quarter for generation (unused if specific_quarters provided)
            overwrite_existing: Whether to overwrite existing comments
            specific_quarters: Optional list of specific quarters to generate
        """
        if specific_quarters:
            return generate_all_comments(specific_quarters=specific_quarters)
        else:
            # For now, ignore the start/end parameters and run the full generation
            # You can enhance this later to filter by start/end quarter
            return generate_all_comments()

if __name__ == "__main__":
    run_with_confirmation()
