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

# Load data
print("Loading data...")
df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
keyitem = pd.read_excel('Data/Key_items.xlsx')
bank_type_mapping = pd.read_excel('Data/Bank_Type.xlsx')

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

def openai_comment_bulk(ticker, sector, quarter, df_quarter_data, keyitem_data):
    """Modified version of openai_comment for bulk processing"""
    
    def get_data(ticker, sector, target_quarter):
        cols_keep = pd.DataFrame({
        'Name': [
            'Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE', 'NIM', 'Loan yield',
            'NPL', 'NPL Formation (%)', 'GROUP 2', 'G2 Formation (%)',
            'NPL Coverage ratio'
        ]
        })
        cols_code_keep = cols_keep.merge(keyitem_data, on='Name', how='left')
        cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()
        rename_dict = dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name']))

        # Helper functions for growth calculations
        def calculate_growth(df_data, period, suffix):
            """Calculate growth (%) and return formatted DataFrame."""
            growth = df_data.iloc[:, 1:].pct_change(periods=period)
            growth.columns = growth.columns.map(rename_dict)
            growth = growth.add_suffix(f' {suffix} (%)')
            return pd.concat([df_data['Date_Quarter'], growth], axis=1)

        def calculate_ytd_growth(df_data):
            """Calculate YTD growth (%) from current quarter to Q4 of previous year."""
            df_filtered = df_data.copy()
            
            # Extract year and quarter from Date_Quarter (format: XQ##)
            df_filtered['Quarter'] = df_filtered['Date_Quarter'].str.extract(r'(\d+)Q').astype(int)
            df_filtered['Year'] = df_filtered['Date_Quarter'].str.extract(r'Q(\d+)').astype(int)
            
            # Calculate YTD growth for Loan only
            ytd_growth = pd.DataFrame(index=df_filtered.index)
            ytd_growth['Date_Quarter'] = df_filtered['Date_Quarter']
            
            # Find Loan column
            loan_col = None
            for col in df_filtered.columns:
                if col in rename_dict and rename_dict[col] == 'Loan':
                    loan_col = col
                    break
            
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
        df_ticker = df_ticker[cols_keep_final]
        
        # Sort by date and get data up to target quarter
        # Filter data up to target quarter
        target_numeric = quarter_to_numeric(target_quarter)
        df_ticker['quarter_numeric'] = df_ticker['Date_Quarter'].apply(quarter_to_numeric)
        df_ticker = df_ticker[df_ticker['quarter_numeric'] <= target_numeric]
        df_ticker = df_ticker.sort_values('quarter_numeric')
        df_ticker = df_ticker.drop('quarter_numeric', axis=1)
        
        # Take last 6 quarters for analysis
        df_ticker_base = df_ticker.rename(columns=rename_dict).tail(6)
        
        # Calculate growth metrics for ticker
        df_ticker_qoq = calculate_growth(df_ticker.tail(6), 1, 'QoQ')
        df_ticker_yoy = calculate_growth(df_ticker.tail(6), 4, 'YoY')
        df_ticker_ytd = calculate_ytd_growth(df_ticker.tail(6))
        
        # Combine ticker data with growth metrics
        ticker_combined = df_ticker_base.copy()
        
        # Add specific growth columns
        if not df_ticker_qoq.empty:
            for metric in ['Loan', 'TOI', 'Provision expense', 'PBT']:
                qoq_col = f'{metric} QoQ (%)'
                if qoq_col in df_ticker_qoq.columns:
                    ticker_combined[qoq_col] = df_ticker_qoq[qoq_col]
        
        if not df_ticker_yoy.empty:
            for metric in ['TOI', 'Provision expense', 'PBT']:
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
        
        # Get sector data (similar process)
        df_sector = df_quarter_data[(df_quarter_data['Type'] == sector) & (df_quarter_data['TICKER'].apply(lambda t: len(t) > 3))]
        if not df_sector.empty:
            sector_ticker = df_sector['TICKER'].iloc[0]
            df_sector = df_sector[df_sector['TICKER'] == sector_ticker]
            df_sector = df_sector[cols_keep_final]
            
            # Filter data up to target quarter
            df_sector['quarter_numeric'] = df_sector['Date_Quarter'].apply(quarter_to_numeric)
            df_sector = df_sector[df_sector['quarter_numeric'] <= target_numeric]
            df_sector = df_sector.sort_values('quarter_numeric')
            df_sector = df_sector.drop('quarter_numeric', axis=1)
            
            df_sector_base = df_sector.rename(columns=rename_dict).tail(6)
            
            # Calculate growth metrics for sector
            df_sector_qoq = calculate_growth(df_sector.tail(6), 1, 'QoQ')
            df_sector_yoy = calculate_growth(df_sector.tail(6), 4, 'YoY')
            df_sector_ytd = calculate_ytd_growth(df_sector.tail(6))
            
            # Combine sector data with growth metrics
            sector_combined = df_sector_base.copy()
            
            if not df_sector_qoq.empty:
                for metric in ['Loan', 'TOI', 'Provision expense', 'PBT']:
                    qoq_col = f'{metric} QoQ (%)'
                    if qoq_col in df_sector_qoq.columns:
                        sector_combined[qoq_col] = df_sector_qoq[qoq_col]
            
            if not df_sector_yoy.empty:
                for metric in ['TOI', 'Provision expense', 'PBT']:
                    yoy_col = f'{metric} YoY (%)'
                    if yoy_col in df_sector_yoy.columns:
                        sector_combined[yoy_col] = df_sector_yoy[yoy_col]
            
            if not df_sector_ytd.empty:
                if 'Loan YTD (%)' in df_sector_ytd.columns:
                    sector_combined['Loan YTD (%)'] = df_sector_ytd['Loan YTD (%)']
            
            # Transpose sector data
            df_sector_out = sector_combined.T
            df_sector_out.columns = df_sector_out.iloc[0]
            df_sector_out = df_sector_out[1:]
        else:
            df_sector_out = pd.DataFrame()

        return df_ticker_out, df_sector_out

    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    client = openai.OpenAI(api_key=api_key)
    
    # Get data for both ticker and sector
    ticker_data, sector_data = get_data(ticker, sector, quarter)
    
    # Load writing examples from Excel file
    writing_examples = ""
    try:
        # Use relative path from current directory
        examples_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Data', 'Prompt testing.xlsx')
        
        if os.path.exists(examples_path):
            examples_df = pd.read_excel(examples_path)
            
            writing_examples = "\n4. WRITING STYLE EXAMPLES:\nHere are examples of the preferred writing style and analysis approach you should follow:\n\n"
            
            for i, row in examples_df.iterrows():
                writing_examples += f"EXAMPLE {i+1}:\n"
                for col in examples_df.columns:
                    if pd.notna(row[col]) and str(row[col]).strip():
                        writing_examples += f"{col}: {row[col]}\n"
                writing_examples += "\n---\n\n"
                
            writing_examples += "IMPORTANT: Use the same analytical approach, writing style, tone, and structure as shown in these examples. Pay attention to how data is presented, how insights are developed, and the overall narrative flow.\n\n"
                
    except Exception as e:
        print(f"Warning: Could not load writing examples: {e}")
    
    prompt = f"""
    You are a banking analyst assistant. Analyze the provided banking data with the following guidelines:

    1. Growth Context Rules:
    - The time code is written as 'XQYY' where X is the quarter number (1-4) and YY is the last two digits of the year.
    - Quarter-on-Quarter (QoQ): Always compare with the immediate previous quarter (e.g., 1Q25 vs 4Q24)
    - Year-on-Year (YoY): Always compare with the exact same quarter from the previous year (e.g., 1Q25 vs 1Q24)
    - Never compare quarters from non-consecutive years (e.g., avoid comparing 1Q25 vs 1Q23)
    - Maintain this consistency throughout the analysis

    2. Key Analysis Areas to Cover:
    Focus on these important banking performance areas, prioritizing the bank's own trends. Divide the analysis into 3 segments in this exact order and title:
    
    - Profitability: TOI and Net profit trends, ROA and ROE performance trajectory
    - Loan Growth & NIM: Loan growth momentum (QoQ and YoY), NIM direction and drivers
    - Asset Quality: NPL & G2 ratio evolution, formation trends, coverage ratios. 
    
    PRIMARY FOCUS: The bank's own performance evolution and trend changes. Use sector data only for brief context when relevant.

    3. Writing Approach:
    - Create a narrative thread connecting the bank's key performance drivers. 
    - The writing style should be punchy.
    - Focus on the 'why' behind the numbers - what business dynamics are driving changes?
    - Identify the most compelling performance themes and investment implications
    - Assess historical trends and projected performance, then evaluate whether the latest figures represent a positive or negative surprise versus expectations.
    - Think like an equity analyst telling investors what matters most
    - Use simple and neutral words and tone. Avoid all words like "roaring, resurgence, ..."

    {writing_examples}

    Format Guidelines:
    - Use one decimal point for percentages (e.g., 15.7%) when citing specific figures
    - Weave data points naturally into the narrative rather than listing them. Writing style should be punchy
    - Temperature: 0.2, keep it factual
    - Keep the analysis concise: 250-300 words maximum

    Start with 2-3 key takeaway points, then provide brief supporting analysis.

    Data for Bank: {ticker} (Quarter: {quarter})
    {ticker_data.to_markdown(index=True, tablefmt='grid')}
    
    Sector Benchmark ({sector}):
    {sector_data.to_markdown(index=True, tablefmt='grid') if not sector_data.empty else 'No sector data available'}
    """

    # Send to OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a financial analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API for {ticker} {quarter}: {str(e)}")
        return None

def generate_all_comments():
    """Generate comments for all banks and all quarters"""
    
    print("Getting bank-sector mapping...")
    bank_sector_mapping = get_bank_sector_mapping()
    print(f"Found {len(bank_sector_mapping)} entities (banks and sectors)")
    
    print("Getting quarters from 2023...")
    quarters = get_quarters_from_2023()
    print(f"Found {len(quarters)} quarters: {quarters}")
    
    # Get ALL tickers (both individual banks and sectors)
    all_tickers = list(bank_sector_mapping.keys())
    print(f"Processing {len(all_tickers)} tickers (including individual banks and sectors)")
    
    # Check if comments file already exists
    comments_file = 'Data/banking_comments.xlsx'
    if os.path.exists(comments_file):
        existing_comments = pd.read_excel(comments_file)
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
                
                comment = openai_comment_bulk(ticker, sector, quarter, df_quarter, keyitem)
                
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
                temp_df.to_excel(f"Data/banking_comments_temp_{processed}.xlsx", index=False)
                print(f"  Saved temporary progress: {len(all_comments)} comments")
    
    # Save final results
    if all_comments:
        final_df = pd.DataFrame(all_comments)
        final_df.to_excel(comments_file, index=False)
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
    
    def generate_bulk_comments(self, start_quarter=None, end_quarter=None, overwrite_existing=False):
        """Generate comments for specified range"""
        # For now, ignore the parameters and run the full generation
        # You can enhance this later to filter by start/end quarter
        return generate_all_comments()

if __name__ == "__main__":
    run_with_confirmation()
