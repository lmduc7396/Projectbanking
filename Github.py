#%%
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import openai
import os
from dotenv import load_dotenv
import requests
from datetime import datetime

# Load your data
df_quarter = pd.read_csv('Data/dfsectorquarter.csv')
df_year = pd.read_csv('Data/dfsectoryear.csv')
keyitem=pd.read_excel('Data/Key_items.xlsx')
color_sequence=px.colors.qualitative.Bold
load_dotenv()

# Sidebar: Choose pages
page= st.sidebar.selectbox("Choose a page", ("Banking plot","Company Table","OpenAI Comment"))

# Sidebar: Choose database
db_option = st.sidebar.radio("Choose database:", ("Quarterly", "Yearly"))

if db_option == "Quarterly":
    df = df_quarter.copy()
else:
    df = df_year.copy()


def Bankplot():
    # Define your options
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    tickers = sorted([x for x in df['TICKER'].unique() if isinstance(x, str) and len(x) == 3])
    x_options = bank_type + tickers
    
    col1,col2,col3 = st.columns(3)
    with col1:
        X = st.multiselect("Select Stock Ticker or Bank Type (X):", x_options,
                          default = ['Private_1']
                          )
    with col2:
        Y = st.number_input("Number of latest periods to plot (Y):", min_value=1, max_value=20, value=10)
    with col3:
        Z = st.multiselect(
        "Select Value Column(s) (Z):", 
        keyitem['Name'].tolist(),
        default = ['NIM','Loan yield','NPL','GROUP 2','NPL Formation (%)', 'G2 Formation (%)']
    )
    
    #Setup subplot
    
    rows = len(Z) // 2 + 1
    cols = 2 if len(Z) > 1 else 1
    
    fig = make_subplots(
        rows=rows, 
        cols=cols, 
        subplot_titles=Z
    )
    
    #Draw chart
    
    for idx, z_name in enumerate(Z):
        value_col = keyitem[keyitem['Name']==z_name]['KeyCode'].iloc[0]
        metric_values=df[value_col].dropna()
        median_value=metric_values.median()
        median_value=abs(median_value)
        row = idx // 2 + 1
        col = idx % 2 + 1
        if median_value > 10:
            tick_format = ",.2s"  # SI units: k, M, B
        else:
            tick_format = ".2%"   # Percent
    
        for i, x in enumerate(X):
            show_legend = (idx == 0)
            if len(x) == 3:  # Stock ticker
                matched_rows = df[df['TICKER'] == x]
                if not matched_rows.empty:
                    df_tempY = matched_rows.tail(Y)
                    fig.add_trace(
                        go.Scatter(
                            x=df_tempY['Date_Quarter'],
                            y=df_tempY[value_col],
                            mode='lines+markers',
                            name=str(x),
                            line=dict(color=color_sequence[i % len(color_sequence)]),
                            showlegend = show_legend
                        ),
                        row=row,
                        col=col
                    )
            else:  # Bank type
                matched_rows = df[(df['Type'] == x) & (df['TICKER'].apply(len) > 3)]
                if not matched_rows.empty:
                    primary_ticker = matched_rows.iloc[0]['TICKER']
                    df_tempY = matched_rows[matched_rows['TICKER'] == primary_ticker].tail(Y)
                    fig.add_trace(
                        go.Scatter(
                            x=df_tempY['Date_Quarter'],
                            y=df_tempY[value_col],
                            mode='lines+markers',
                            name=str(x),
                            line=dict(color=color_sequence[i % len(color_sequence)]),
                            showlegend = show_legend
                        ),
                        row=row,
                        col=col
                    )
  
    fig.update_layout(
        width=1400,
        height=1200,
        title_text=f"Banking Metrics: {', '.join(Z)}",
        legend_title="Ticker/Type"
    )
    #Sort x asis
    def quarter_sort_key(q):
        # Example: "5Q21" → (21, 5)
        if 'Q' in q:
            parts = q.split('Q')
            return (int(parts[1]), int(parts[0]))
        return (0, 0)
    date_order = df[['Date_Quarter']].drop_duplicates().copy()
    date_order['Sortkey'] = date_order['Date_Quarter'].apply(quarter_sort_key)
    date_order = date_order.sort_values(by='Sortkey')
    fig.update_xaxes(categoryorder='array', categoryarray=date_order['Date_Quarter'])

    for i in range(1, len(Z)+1):
        fig.update_yaxes(tickformat=tick_format, row=(i-1)//2 + 1, col=(i-1)%2 + 1)    
    st.plotly_chart(fig, use_container_width=True)

def Banking_table(X, Y, Z):

    # --- Prepare List of Columns to Keep ---
    cols_keep_table1 = pd.DataFrame({
        'Name': [
            'Loan', 'TOI', 'Provision expense', 'PBT', 'ROA', 'ROE'
        ]
    })
    
    cols_keep_table2 = pd.DataFrame({
        'Name': [
            'NIM', 'Loan yield', 'NPL', 'NPL Formation (%)', 'GROUP 2', 'G2 Formation (%)',
            'NPL Coverage ratio', 'Provision/ Total Loan'
        ]
    })
    
    cols_code_keep_table1 = cols_keep_table1.merge(keyitem, on='Name', how='left')
    cols_code_keep_table2 = cols_keep_table2.merge(keyitem, on='Name', how='left')
    
    cols_keep_final_table1 = ['Date_Quarter'] + cols_code_keep_table1['KeyCode'].tolist()
    cols_keep_final_table2 = ['Date_Quarter'] + cols_code_keep_table2['KeyCode'].tolist()

    # --- Filter Data for Table ---
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    if X in bank_type:
        # Filter by Type (e.g. Sector, SOCB, etc.)
        df_temp = df[(df['Type'] == X) & (df['TICKER'].apply(lambda t: len(t) > 3))]
        df_temp = df_temp[df_temp['TICKER'] == df_temp['TICKER'].iloc[0]]
    else:
        # Filter by specific ticker
        df_temp = df[df['TICKER'] == X]

    # --- Calculate Growth Tables ---
    def get_growth_table(df_, period, suffix, cols_code_keep):
        """Calculate growth (%) and return formatted DataFrame."""
        cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()
        df_filtered = df_[cols_keep_final]
        growth = df_filtered.iloc[:, 1:].pct_change(periods=period)
        growth.columns = growth.columns.map(dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name'])))
        growth = growth.add_suffix(f' {suffix} (%)')
        return pd.concat([df_filtered['Date_Quarter'], growth.iloc[:, :4]], axis=1)

    def create_table(cols_code_keep, table_name):
        cols_keep_final = ['Date_Quarter'] + cols_code_keep['KeyCode'].tolist()
        df_temp_table = df_temp[cols_keep_final]
        
        # --- Rename Columns to Friendly Names, Remove Date_Quarter ---
        df_temp_table.columns = df_temp_table.columns.map(dict(zip(cols_code_keep['KeyCode'], cols_code_keep['Name'])))
        df_temp_table = df_temp_table.iloc[:, 1:]

        # --- Only add growth columns for table 1 (Earnings metrics) ---
        if table_name == "Earnings metrics":
            QoQ_change = get_growth_table(df_temp, 1, 'QoQ', cols_code_keep)
            YoY_change = get_growth_table(df_temp, 4, 'YoY', cols_code_keep)
            
            # --- Combine Data Based on User Choice (QoQ or YoY) ---
            if Z == 'QoQ':
                df_out = pd.concat([df_temp[['Date_Quarter']], df_temp_table, QoQ_change.iloc[:, 1:]], axis=1)
                # Create column order dynamically
                col_order = ['Date_Quarter']
                for i, name in enumerate(cols_code_keep['Name'].tolist()):
                    col_order.append(name)
                    if i < 4:  # Only first 4 get growth columns
                        col_order.append(f"{name} QoQ (%)")
            else:
                df_out = pd.concat([df_temp[['Date_Quarter']], df_temp_table, YoY_change.iloc[:, 1:]], axis=1)
                # Create column order dynamically
                col_order = ['Date_Quarter']
                for i, name in enumerate(cols_code_keep['Name'].tolist()):
                    col_order.append(name)
                    if i < 4:  # Only first 4 get growth columns
                        col_order.append(f"{name} YoY (%)")
        else:
            # For table 2 (Ratios), don't add growth columns
            df_out = pd.concat([df_temp[['Date_Quarter']], df_temp_table], axis=1)
            col_order = ['Date_Quarter'] + cols_code_keep['Name'].tolist()

        # --- Reindex, Select Last Y Periods, Transpose for Display ---
        df_out = df_out[col_order].tail(Y).T
        df_out.columns = df_out.iloc[0]
        df_out = df_out[1:]
        
        # Return the table without displaying the title here
        return df_out

    # Create and display both tables
    df_table1 = create_table(cols_code_keep_table1, "Earnings metrics")
    df_table2 = create_table(cols_code_keep_table2, "Ratios")
    
    return df_table1, df_table2

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

def Stock_price_plot(X):
    # Fetch historical price data
    df = fetch_historical_price(X)
    if df is not None:
        # Filter data to show only last 2 years
        current_year = datetime.now().year
        two_years_ago = current_year - 2
        df['year'] = df['tradingDate'].dt.year
        df = df[df['year'] >= two_years_ago].copy()
        df = df.drop('year', axis=1)  # Remove the helper column
        
        # Create subplots with secondary y-axis for volume
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(f'{X} Stock Price', 'Volume'),
            row_width=[0.2, 0.7]
        )
        
        # Add candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=df['tradingDate'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )
        
        # Add volume bars
        fig.add_trace(
            go.Bar(
                x=df['tradingDate'],
                y=df['volume'],
                name='Volume',
                marker_color='lightblue',
                opacity=0.7
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=f'{X} Stock Analysis',
            xaxis_rangeslider_visible=False,
            height=600,
            showlegend=False
        )
        
        # Update y-axes
        fig.update_yaxes(title_text="Price (VND)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        
        # Display in Streamlit
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("No data available for plotting.")

def quarter_sort_key(q):
    # Example: "5Q21" → (21, 5)
    if 'Q' in q:
        parts = q.split('Q')
        return (int(parts[1]), int(parts[0]))
    return (0, 0)
date_order = df_year[['Date_Quarter']].drop_duplicates().copy()
date_order['Sortkey'] = date_order['Date_Quarter'].apply(quarter_sort_key)
date_order = date_order.sort_values(by='Sortkey')


def conditional_format(df):
    def human_format(num):
        try:
            num = float(num)
        except:
            return ""
        abs_num = abs(num)
        if abs_num >= 1_000_000_000:
            return f"{num/1_000_000_000:,.0f}"
        else:
            return f"{num:.1f}"
    
    def format_row(row):
        vals = pd.to_numeric(row, errors='coerce').values  # Ensures a NumPy array
        numeric_vals = vals[~np.isnan(vals)]
        if len(numeric_vals) == 0:
            return pd.Series([str(v) if v is not None else "" for v in row], index=row.index)
        median_val = np.median(np.abs(numeric_vals))
        if median_val > 100:
            return pd.Series([human_format(v) if pd.notnull(v) and v != '' else "" for v in row], index=row.index)
        else:
            return pd.Series(["{:.2f}%".format(float(v)*100) if pd.notnull(v) and v != '' else "" for v in row], index=row.index)
    
    # Apply formatting row-wise, axis=1
    formatted = df.apply(format_row, axis=1)
    return formatted


def openai_comment(ticker, sector):
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

        # Get ticker data
        df_ticker = df_quarter[df_quarter['TICKER'] == ticker]
        df_ticker = df_ticker[cols_keep_final]
        df_ticker_out = df_ticker.rename(columns=rename_dict).tail(6).T
        df_ticker_out.columns = df_ticker_out.iloc[0]
        df_ticker_out = df_ticker_out[1:]
        
        # Get sector data (filter out individual tickers - length = 3)
        df_sector = df_quarter[(df_quarter['Type'] == sector) & (df_quarter['TICKER'].apply(lambda t: len(t) > 3))]
        if not df_sector.empty:
            # Take the first representative ticker for the sector
            sector_ticker = df_sector['TICKER'].iloc[0]
            df_sector = df_sector[df_sector['TICKER'] == sector_ticker]
            df_sector = df_sector[cols_keep_final]
            df_sector_out = df_sector.rename(columns=rename_dict).tail(6).T
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
    
    prompt = f"""
    You are a banking analyst assistant. Analyze the provided banking data with the following guidelines:

    1. Growth Calculations Rules:
    - The time code is written as 'XQYY' where X is the quarter number (1-4) and YY is the last two digits of the year.
    - Quarter-on-Quarter (QoQ): Always compare with the immediate previous quarter (e.g., 1Q25 vs 4Q24)
    - Year-on-Year (YoY): Always compare with the exact same quarter from the previous year (e.g., 1Q25 vs 1Q24)
    - Never compare quarters from non-consecutive years (e.g., avoid comparing 1Q25 vs 1Q23)
    - Maintain this consistency throughout the analysis

    2. Key Analysis Areas to Cover:
    Focus on these important banking performance areas, prioritizing the bank's own trends:
    
    - Profitability & Returns: Net profit trends, ROA and ROE performance trajectory
    - Loan Growth & NIM: Loan growth momentum (QoQ and YoY), NIM direction and drivers
    - Asset Quality: NPL & G2 ratio evolution, formation trends, coverage ratios
    
    PRIMARY FOCUS: The bank's own performance evolution and trend changes. Use sector data only for brief context when relevant.

    3. Analysis Approach:
    - Think about what are the upside/downside to each of the metrics. what should the investors watch for, how would these factors impact the financial performance? What are your expectations on the previous metrics?
    - Focus primarily on the bank's own performance trajectory and improvements/deteriorations
    - Identify the most significant trend changes and inflection points in the bank's metrics
    - Use sector comparison sparingly - only when it adds meaningful context
    - Stay strictly factual and data-driven

    Format Guidelines:
    - Use one decimal point for percentages (e.g., 15.7%)
    - Always specify the time period for comparisons
    - Keep the analysis very concise: 250-300 words maximum
    - Write in flowing paragraphs, focus on the most important trends only

    Start with 2-3 key takeaway points, then provide brief supporting analysis.

    Data for Bank: {ticker}
    {ticker_data.to_markdown(index=True, tablefmt='grid')}
    
    Sector Benchmark ({sector}):
    {sector_data.to_markdown(index=True, tablefmt='grid') if not sector_data.empty else 'No sector data available'}
    """

    # 4. Send to OpenAI
    response = client.chat.completions.create(
        model="gpt-4.1",   # or "gpt-4-turbo"
        messages=[
            {"role": "system", "content": "You are a financial analyst."},
            {"role": "user", "content": prompt}
        ]
    )

    st.markdown(response.choices[0].message.content)


if page == "Banking plot":
    #Setup page:
    st.set_page_config(
        page_title="Project Banking Online",
        layout="wide")
    st.subheader("Project Banking Online")
    Bankplot()

elif page == "Company Table":
    st.subheader("Company Table")
    # --- Define User Selection Options ---
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    tickers = sorted([x for x in df['TICKER'].unique() if isinstance(x, str) and len(x) == 3])
    x_options = bank_type + tickers

    col1, col2, col3 = st.columns(3)
    with col1:
        X = st.selectbox("Select Stock Ticker or Bank Type (X):", x_options)
    with col2:
        Y = st.number_input("Number of latest periods to plot (Y):", min_value=1, max_value=20, value=6)
    with col3:
        if db_option == "Quarterly":
            Z = st.selectbox("QoQ or YoY growth (Z):", ['QoQ', 'YoY'], index=0)
        else:
            Z = st.selectbox("QoQ or YoY growth (Z):", ['YoY'], index=0)

    if len(X) == 3:
        Stock_price_plot(X)

    df_table1, df_table2 = Banking_table(X, Y, Z)
    
    # Format and display first table
    st.subheader("Earnings metrics")
    formatted1 = conditional_format(df_table1)
    st.dataframe(formatted1, use_container_width=True)
    
    # Format and display second table
    st.subheader("Ratios")
    formatted2 = conditional_format(df_table2)
    st.dataframe(formatted2, use_container_width=True)

elif page == "OpenAI Comment":
    st.subheader("OpenAI Comment")
    
    # Define options
    bank_type = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
    tickers = sorted([x for x in df_quarter['TICKER'].unique() if isinstance(x, str) and len(x) == 3])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker = st.selectbox("Select Bank Ticker:", tickers, index=tickers.index('ACB') if 'ACB' in tickers else 0)
    with col2:
        sector = st.selectbox("Select Sector for Comparison:", bank_type, index=0)
    with col3:
        generate_button = st.button("Generate", type="primary")
    
    if ticker and sector and generate_button:
        openai_comment(ticker, sector)

   
