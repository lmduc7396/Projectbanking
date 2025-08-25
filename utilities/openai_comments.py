import pandas as pd
import numpy as np
import streamlit as st
import openai
import os
from dotenv import load_dotenv

def load_cached_comment(ticker, quarter):
    """Load a previously generated comment from the cache file"""
    try:
        comments_file = r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\banking_comments.xlsx"
        
        if os.path.exists(comments_file):
            comments_df = pd.read_excel(comments_file)
            
            # Find the comment for this ticker and quarter
            comment_row = comments_df[
                (comments_df['TICKER'] == ticker) & 
                (comments_df['QUARTER'] == quarter)
            ]
            
            if not comment_row.empty:
                comment_data = comment_row.iloc[0]
                return {
                    'comment': comment_data['COMMENT'],
                    'generated_date': comment_data['GENERATED_DATE'],
                    'sector': comment_data['SECTOR']
                }
        
        return None
        
    except Exception as e:
        st.error(f"Error loading cached comment: {e}")
        return None

def get_latest_quarter(ticker, df_quarter):
    """Get the most recent quarter for a given ticker"""
    ticker_data = df_quarter[df_quarter['TICKER'] == ticker]
    if not ticker_data.empty:
        # Sort quarters to get the latest
        def quarter_to_numeric(q):
            if 'Q' in str(q):
                parts = str(q).split('Q')
                quarter_num = int(parts[0])
                year = int(parts[1])
                if year < 50:
                    year += 2000
                elif year < 100:
                    year += 1900
                return year * 10 + quarter_num
            return 0
        
        ticker_data['quarter_numeric'] = ticker_data['Date_Quarter'].apply(quarter_to_numeric)
        latest_quarter = ticker_data.loc[ticker_data['quarter_numeric'].idxmax(), 'Date_Quarter']
        return latest_quarter
    return None

def openai_comment(ticker, sector, df_quarter=None, keyitem=None, force_regenerate=False):
    # Use global variables or session state if not provided as parameters
    if df_quarter is None:
        df_quarter = st.session_state.get('df_quarter')
    if keyitem is None:
        keyitem = st.session_state.get('keyitem')

    # Get the latest quarter for this ticker
    latest_quarter = get_latest_quarter(ticker, df_quarter)
    
    if not latest_quarter:
        st.error(f"No data found for ticker: {ticker}")
        return
    
    # Try to load cached comment first (unless force_regenerate is True)
    if not force_regenerate:
        cached_comment = load_cached_comment(ticker, latest_quarter)
        
        if cached_comment:
            st.success(f"✓ Loaded cached analysis for {ticker} - {latest_quarter}")
            st.info(f"Analysis generated on: {cached_comment['generated_date']}")
            st.markdown(cached_comment['comment'])
            
            # Add option to regenerate
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("Regenerate", key=f"regen_{ticker}_{latest_quarter}"):
                    st.rerun()
            
            return
        else:
            st.warning(f"No cached analysis found for {ticker} - {latest_quarter}. Generating new analysis...")
    
    # If no cached comment or force_regenerate is True, generate new comment
    def get_data(ticker, sector):
        cols_keep = pd.DataFrame({
        'Name': [
            'Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE', 'NIM', 'Loan yield',
            'NPL', 'NPL Formation (%)', 'GROUP 2', 'G2 Formation (%)',
            'NPL Coverage ratio'
        ]
        })
        cols_code_keep = cols_keep.merge(keyitem, on='Name', how='left')
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

        # Get ticker data
        df_ticker = df_quarter[df_quarter['TICKER'] == ticker]
        df_ticker = df_ticker[cols_keep_final]
        df_ticker_base = df_ticker.rename(columns=rename_dict).tail(6)
        
        # Calculate growth metrics for ticker
        df_ticker_qoq = calculate_growth(df_ticker.tail(6), 1, 'QoQ')
        df_ticker_yoy = calculate_growth(df_ticker.tail(6), 4, 'YoY')
        df_ticker_ytd = calculate_ytd_growth(df_ticker.tail(6))
        
        # Combine ticker data with growth metrics
        ticker_combined = df_ticker_base.copy()
        
        # Add specific growth columns
        if not df_ticker_qoq.empty:
            # Add QoQ for Loan, TOI, Provision expense, PBT
            for metric in ['Loan', 'TOI', 'Provision expense', 'PBT']:
                qoq_col = f'{metric} QoQ (%)'
                if qoq_col in df_ticker_qoq.columns:
                    ticker_combined[qoq_col] = df_ticker_qoq[qoq_col]
        
        if not df_ticker_yoy.empty:
            # Add YoY for TOI, Provision expense, PBT
            for metric in ['TOI', 'Provision expense', 'PBT']:
                yoy_col = f'{metric} YoY (%)'
                if yoy_col in df_ticker_yoy.columns:
                    ticker_combined[yoy_col] = df_ticker_yoy[yoy_col]
        
        if not df_ticker_ytd.empty:
            # Add YTD for Loan
            if 'Loan YTD (%)' in df_ticker_ytd.columns:
                ticker_combined['Loan YTD (%)'] = df_ticker_ytd['Loan YTD (%)']
        
        # Transpose ticker data
        df_ticker_out = ticker_combined.T
        df_ticker_out.columns = df_ticker_out.iloc[0]
        df_ticker_out = df_ticker_out[1:]
        
        # Get sector data (filter out individual tickers - length = 3)
        df_sector = df_quarter[(df_quarter['Type'] == sector) & (df_quarter['TICKER'].apply(lambda t: len(t) > 3))]
        if not df_sector.empty:
            # Take the first representative ticker for the sector
            sector_ticker = df_sector['TICKER'].iloc[0]
            df_sector = df_sector[df_sector['TICKER'] == sector_ticker]
            df_sector = df_sector[cols_keep_final]
            df_sector_base = df_sector.rename(columns=rename_dict).tail(6)
            
            # Calculate growth metrics for sector
            df_sector_qoq = calculate_growth(df_sector.tail(6), 1, 'QoQ')
            df_sector_yoy = calculate_growth(df_sector.tail(6), 4, 'YoY')
            df_sector_ytd = calculate_ytd_growth(df_sector.tail(6))
            
            # Combine sector data with growth metrics
            sector_combined = df_sector_base.copy()
            
            # Add specific growth columns
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


    # 3. Build the analysis prompt
    try:
        # Try to get API key from Streamlit secrets first (for deployed apps)
        api_key = st.secrets["OPENAI_API_KEY"]
    except:
        # Fall back to environment variable (for local development)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("OPENAI_API_KEY not found in secrets or environment variables")
            return
    
    client = openai.OpenAI(api_key=api_key)
    
    # Get data for both ticker and sector
    ticker_data, sector_data = get_data(ticker, sector)
    
    # Load writing examples from Excel file
    writing_examples = ""
    try:
        # Define the absolute path to the examples file
        examples_path = r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\Prompt testing.xlsx"
        
        # Debug info
        st.info(f"Looking for examples file at: {examples_path}")
        st.info(f"File exists: {os.path.exists(examples_path)}")
        
        if os.path.exists(examples_path):
            st.info("File found! Loading examples...")
            examples_df = pd.read_excel(examples_path)
            
            st.success(f"Successfully loaded {len(examples_df)} rows from examples file")
            st.info(f"Columns found: {examples_df.columns.tolist()}")
            
            writing_examples = "\n4. WRITING STYLE EXAMPLES:\nHere are examples of the preferred writing style and analysis approach you should follow:\n\n"
            
            for i, row in examples_df.iterrows():
                writing_examples += f"EXAMPLE {i+1}:\n"
                for col in examples_df.columns:
                    if pd.notna(row[col]) and str(row[col]).strip():
                        writing_examples += f"{col}: {row[col]}\n"
                writing_examples += "\n---\n\n"
                
            writing_examples += "IMPORTANT: Use the same analytical approach, writing style, tone, and structure as shown in these examples. Pay attention to how data is presented, how insights are developed, and the overall narrative flow.\n\n"
            
            # Show preview of what was loaded
            with st.expander("Preview of loaded writing examples"):
                st.dataframe(examples_df)
                
        else:
            st.warning("Writing examples file not found at expected location.")
            st.info("Please ensure the file exists at: " + examples_path)
            
    except Exception as e:
        st.error(f"Error loading writing examples: {e}")
        st.info("Using default writing style.")
    
    prompt = f"""
    You are a banking analyst assistant. Analyze the provided banking data with the following guidelines:

    1. Growth Context Rules:
    - The time code is written as 'YYYY-Q#' where YYYY is the 4-digit year and # is the quarter number (1-4). For example: 2024-Q1, 2024-Q2, 2024-Q3, 2024-Q4.
    - Quarter-on-Quarter (QoQ): Always compare with the immediate previous quarter (e.g., 2025-Q1 vs 2024-Q4)
    - Year-on-Year (YoY): Always compare with the exact same quarter from the previous year (e.g., 2025-Q1 vs 2024-Q1)
    - Never compare quarters from non-consecutive years (e.g., avoid comparing 2025-Q1 vs 2023-Q1)
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

    Data for Bank: {ticker}
    {ticker_data.to_markdown(index=True, tablefmt='grid')}
    
    Sector Benchmark ({sector}):
    {sector_data.to_markdown(index=True, tablefmt='grid') if not sector_data.empty else 'No sector data available'}
    """

    # 4. Send to OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-4",   # or "gpt-4-turbo"
            messages=[
                {"role": "system", "content": "You are a financial analyst."},
                {"role": "user", "content": prompt}
            ]
        )

        generated_comment = response.choices[0].message.content
        
        # Save the newly generated comment to cache
        try:
            save_comment_to_cache(ticker, sector, latest_quarter, generated_comment)
            st.success("✓ New analysis generated and saved to cache")
        except Exception as e:
            st.warning(f"Analysis generated but could not save to cache: {e}")
        
        st.markdown(generated_comment)
        
    except Exception as e:
        st.error(f"Error calling OpenAI API: {str(e)}")
        st.info("Please check your API key and internet connection.")

def save_comment_to_cache(ticker, sector, quarter, comment):
    """Save a newly generated comment to the cache file"""
    try:
        comments_file = r"c:\Users\ducle\OneDrive\Work-related\VS - Code project\Data\banking_comments.xlsx"
        
        # Load existing comments or create new DataFrame
        if os.path.exists(comments_file):
            comments_df = pd.read_excel(comments_file)
        else:
            comments_df = pd.DataFrame(columns=['TICKER', 'SECTOR', 'QUARTER', 'COMMENT', 'GENERATED_DATE'])
        
        # Check if comment already exists
        existing_entry = comments_df[
            (comments_df['TICKER'] == ticker) & 
            (comments_df['QUARTER'] == quarter)
        ]
        
        new_entry = {
            'TICKER': ticker,
            'SECTOR': sector,
            'QUARTER': quarter,
            'COMMENT': comment,
            'GENERATED_DATE': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if not existing_entry.empty:
            # Update existing entry
            idx = existing_entry.index[0]
            for key, value in new_entry.items():
                comments_df.loc[idx, key] = value
        else:
            # Add new entry
            comments_df = pd.concat([comments_df, pd.DataFrame([new_entry])], ignore_index=True)
        
        # Save to Excel
        comments_df.to_excel(comments_file, index=False)
        
    except Exception as e:
        raise Exception(f"Failed to save comment to cache: {e}")
