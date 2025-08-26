import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import sys
import os

# Page configuration
st.set_page_config(
    page_title="Bank Earnings Quality Dashboard",
    page_icon="Chart",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import from utilities
from utilities.quarter_utils import format_quarter_for_display
try:
    from utilities.style_utils import apply_google_font
    from utilities.sidebar_style import apply_sidebar_style
    # Apply Google Fonts
    apply_google_font()
    # Apply consistent sidebar styling
    apply_sidebar_style()
except ImportError:
    pass  # Continue without custom font if style_utils not available

# Title and description
st.title("Bank Earnings Quality Analysis Dashboard")
st.markdown("### Analyze earnings drivers through revenue growth, cost efficiency, and non-recurring items")

# Load data
@st.cache_data
def load_data():
    """Load quarterly and yearly data"""
    try:
        quarterly_df = pd.read_csv(os.path.join(project_root, 'Data/earnings_quality_quarterly.csv'))
        yearly_df = pd.read_csv(os.path.join(project_root, 'Data/earnings_quality_yearly.csv'))
        return quarterly_df, yearly_df
    except FileNotFoundError:
        st.error("Data files not found. Please run scripts/Prepare_earnings_driver.py first.")
        return None, None

# Load the data
quarterly_df, yearly_df = load_data()

# Color scheme consistent with other pages
color_sequence = px.colors.qualitative.Bold

if quarterly_df is not None and yearly_df is not None:
    
    # Sidebar for navigation
    st.sidebar.header("Navigation")
    page = st.sidebar.radio("Select View", 
                            ["Score Overview", 
                             "Trend Analysis", 
                             "Statistical Summary"])
    
    # Data type selection
    st.sidebar.header("Data Selection")
    data_type = st.sidebar.radio("Select Data Type", ["Yearly", "Quarterly"])
    
    # Comparison period selection for quarterly data
    comparison_suffix = ""
    if data_type == "Quarterly":
        comparison_period = st.sidebar.selectbox(
            "Comparison Period",
            ["T12M (4Q Average)", "QoQ (Previous Quarter)", "YoY (Same Quarter Last Year)"],
            index=0,
            help="Select how to compare quarterly data"
        )
        
        # Map to column suffixes
        if "QoQ" in comparison_period:
            comparison_suffix = "_QoQ"
        elif "YoY" in comparison_period:
            comparison_suffix = "_YoY"
        else:  # T12M
            comparison_suffix = "_T12M"
    
    # Select appropriate dataframe
    if data_type == "Yearly":
        df = yearly_df.copy()
        period_col = 'Year'
    else:
        df = quarterly_df.copy()
        period_col = 'Date_Quarter'
    
    # Filter out rows without scores - use appropriate column based on comparison
    # For quarterly data, check which columns actually exist
    if data_type == "Quarterly":
        # Default to T12M for quarterly as that's the primary comparison
        if comparison_suffix == "_T12M" or comparison_suffix == "":
            # Check if T12M columns exist
            if 'Top_Line_Score_T12M' in df.columns:
                actual_suffix = "_T12M"
                score_col = 'Top_Line_Score_T12M'
            elif 'Top_Line_Score' in df.columns:
                actual_suffix = ""
                score_col = 'Top_Line_Score'
            else:
                st.error("No score columns found in the data")
                actual_suffix = ""
                score_col = 'Top_Line_Score'
        else:
            # For QoQ or YoY
            score_col = f'Top_Line_Score{comparison_suffix}'
            if score_col not in df.columns:
                # Fallback to T12M if specific comparison not available
                if 'Top_Line_Score_T12M' in df.columns:
                    actual_suffix = "_T12M"
                    score_col = 'Top_Line_Score_T12M'
                else:
                    actual_suffix = ""
                    score_col = 'Top_Line_Score'
            else:
                actual_suffix = comparison_suffix
        
        # Store the actual suffix being used
        comparison_suffix = actual_suffix
    else:
        score_col = 'Top_Line_Score'
    
    df_with_scores = df[df[score_col].notna()].copy()
    
    # Page 1: Score Overview
    if page == "Score Overview":
        st.header("Score Overview Table")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Period selection
            periods = sorted(df_with_scores[period_col].unique(), reverse=True)
            if periods:
                selected_period = st.selectbox(f"Select {period_col}", periods)
            else:
                st.error("No data with scores available")
                selected_period = None
        
        with col2:
            # Bank type filter
            bank_types = ['All'] + list(df_with_scores['Type'].unique())
            selected_type = st.selectbox("Filter by Bank Type", bank_types)
        
        with col3:
            # Ticker search
            search_ticker = st.text_input("Search Ticker", "")
        
        if selected_period:
            # Filter data
            filtered_df = df_with_scores[df_with_scores[period_col] == selected_period].copy()
            
            if selected_type != 'All':
                filtered_df = filtered_df[filtered_df['Type'] == selected_type]
            
            if search_ticker:
                filtered_df = filtered_df[filtered_df['TICKER'].str.contains(search_ticker.upper())]
            
            # Display columns - include flags if they exist
            # Use appropriate column names based on comparison type
            if data_type == "Quarterly" and comparison_suffix:
                display_cols = ['TICKER', 'Type', f'PBT_Change{comparison_suffix}', 
                              f'Top_Line_Score{comparison_suffix}', 
                              f'NII_Sub_Score{comparison_suffix}', f'Loan_Growth_Score{comparison_suffix}', 
                              f'NIM_Change_Score{comparison_suffix}', f'Fee_Sub_Score{comparison_suffix}', 
                              f'Cost_Cutting_Score{comparison_suffix}',
                              f'OPEX_Sub_Score{comparison_suffix}', f'Provision_Sub_Score{comparison_suffix}', 
                              f'Non_Recurring_Score{comparison_suffix}', f'Total_Score{comparison_suffix}']
            else:
                display_cols = ['TICKER', 'Type', 'PBT_Change', 'Top_Line_Score', 
                              'NII_Sub_Score', 'Loan_Growth_Score', 'NIM_Change_Score', 'Fee_Sub_Score', 'Cost_Cutting_Score',
                              'OPEX_Sub_Score', 'Provision_Sub_Score', 'Non_Recurring_Score', 'Total_Score']
            
            # Add flag columns if they exist
            if 'Small_PBT_Flag' in filtered_df.columns:
                display_cols.append('Small_PBT_Flag')
            if 'Scores_Capped' in filtered_df.columns:
                display_cols.append('Scores_Capped')
            
            # Filter columns that exist
            display_cols = [col for col in display_cols if col in filtered_df.columns]
            
            # Create display dataframe
            display_df = filtered_df[display_cols].copy()
            
            # Format numbers
            for col in display_cols:
                if col not in ['TICKER', 'Type', 'Small_PBT_Flag', 'Scores_Capped']:
                    display_df[col] = pd.to_numeric(display_df[col], errors='coerce')
            
            # Convert PBT_Change to billions
            pbt_change_col = f'PBT_Change{comparison_suffix}' if data_type == "Quarterly" and comparison_suffix else 'PBT_Change'
            if pbt_change_col in display_df.columns:
                display_df['PBT_Change_Bn'] = display_df[pbt_change_col] / 1_000_000_000
                # Remove original and rename
                display_df = display_df.drop(pbt_change_col, axis=1)
                # Reorder columns to put PBT_Change_Bn in the right position
                cols = display_df.columns.tolist()
                cols.remove('PBT_Change_Bn')
                cols.insert(2, 'PBT_Change_Bn')  # After TICKER and Type
                display_df = display_df[cols]
            
            # Sort by Total Score
            total_score_col = f'Total_Score{comparison_suffix}' if data_type == "Quarterly" and comparison_suffix else 'Total_Score'
            if total_score_col in display_df.columns:
                display_df = display_df.sort_values(total_score_col, ascending=False)
            
            # Use pre-calculated PBT Growth % and weighted impacts from the data
            # Get appropriate column names based on comparison type
            if data_type == "Quarterly" and comparison_suffix:
                pbt_growth_col = f'PBT_Growth_%{comparison_suffix}'
                revenue_impact_col = f'Top_Line_Impact{comparison_suffix}'
                cost_impact_col = f'Cost_Cutting_Impact{comparison_suffix}'
                nonrec_impact_col = f'Non_Recurring_Impact{comparison_suffix}'
                nii_impact_col = f'NII_Impact{comparison_suffix}'
                fee_impact_col = f'Fee_Impact{comparison_suffix}'
                opex_impact_col = f'OPEX_Impact{comparison_suffix}'
                prov_impact_col = f'Provision_Impact{comparison_suffix}'
                loan_impact_col = f'Loan_Impact{comparison_suffix}'
                nim_impact_col = f'NIM_Impact{comparison_suffix}'
            else:
                pbt_growth_col = 'PBT_Growth_%'
                revenue_impact_col = 'Top_Line_Impact'
                cost_impact_col = 'Cost_Cutting_Impact'
                nonrec_impact_col = 'Non_Recurring_Impact'
                nii_impact_col = 'NII_Impact'
                fee_impact_col = 'Fee_Impact'
                opex_impact_col = 'OPEX_Impact'
                prov_impact_col = 'Provision_Impact'
                loan_impact_col = 'Loan_Impact'
                nim_impact_col = 'NIM_Impact'
            
            # Copy pre-calculated impacts from data
            filtered_df['PBT_Growth_%'] = df.loc[filtered_df.index, pbt_growth_col] if pbt_growth_col in df.columns else 0
            filtered_df['Revenue_Impact'] = df.loc[filtered_df.index, revenue_impact_col] if revenue_impact_col in df.columns else 0
            filtered_df['Cost_Impact'] = df.loc[filtered_df.index, cost_impact_col] if cost_impact_col in df.columns else 0
            filtered_df['NonRec_Impact'] = df.loc[filtered_df.index, nonrec_impact_col] if nonrec_impact_col in df.columns else 0
            
            # Copy sub-component weighted impacts
            filtered_df['NII_Impact'] = df.loc[filtered_df.index, nii_impact_col] if nii_impact_col in df.columns else 0
            filtered_df['Fee_Impact'] = df.loc[filtered_df.index, fee_impact_col] if fee_impact_col in df.columns else 0
            filtered_df['OPEX_Impact'] = df.loc[filtered_df.index, opex_impact_col] if opex_impact_col in df.columns else 0
            filtered_df['Provision_Impact'] = df.loc[filtered_df.index, prov_impact_col] if prov_impact_col in df.columns else 0
            filtered_df['Loan_Impact'] = df.loc[filtered_df.index, loan_impact_col] if loan_impact_col in df.columns else 0
            filtered_df['NIM_Impact'] = df.loc[filtered_df.index, nim_impact_col] if nim_impact_col in df.columns else 0
            
            # Display metrics
            st.subheader(f"Weighted Impact Analysis for {selected_period}")
            st.caption("Shows how much each component contributes to the PBT growth rate")
            
            # Summary cards
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_revenue_impact = filtered_df['Revenue_Impact'].mean()
                st.metric("Avg Revenue Impact", f"{avg_revenue_impact:.1f}")
            
            with col2:
                avg_cost_impact = filtered_df['Cost_Impact'].mean()
                st.metric("Avg Cost Impact", f"{avg_cost_impact:.1f}")
            
            with col3:
                avg_nonrec_impact = filtered_df['NonRec_Impact'].mean()
                st.metric("Avg Non-Rec Impact", f"{avg_nonrec_impact:.1f}")
            
            with col4:
                num_banks = len(filtered_df)
                st.metric("Banks Analyzed", num_banks)
            
            # Prepare display columns for weighted table (removed warning flags)
            weighted_display_cols = ['TICKER', 'Type', 'PBT_Growth_%', 'Revenue_Impact',
                                    'NII_Impact', 'Loan_Impact', 'NIM_Impact', 'Fee_Impact', 'Cost_Impact',
                                    'OPEX_Impact', 'Provision_Impact', 'NonRec_Impact']
            
            weighted_display_df = filtered_df[weighted_display_cols].copy()
            
            # Sort by absolute revenue impact as proxy for importance
            weighted_display_df['abs_impact'] = weighted_display_df['Revenue_Impact'].abs()
            weighted_display_df = weighted_display_df.sort_values('abs_impact', ascending=False)
            weighted_display_df = weighted_display_df.drop('abs_impact', axis=1)
            
            # Configure weighted table columns with improved visibility
            weighted_column_config = {
                "TICKER": st.column_config.TextColumn(
                    "Ticker", 
                    width=80
                ),
                "Type": st.column_config.TextColumn(
                    "Type", 
                    width=90
                ),
                "PBT_Growth_%": st.column_config.NumberColumn(
                    "PBT Growth",
                    format="%.1f%%",
                    width=110,
                    help="Year-over-year or T12M PBT growth rate"
                ),
                "Revenue_Impact": st.column_config.NumberColumn(
                    "**Revenue**",
                    format="%.1f",
                    width=100,
                    help="Total weighted revenue contribution"
                ),
                "NII_Impact": st.column_config.NumberColumn(
                    "- NII",
                    format="%.1f",
                    width=75,
                    help="Net Interest Income weighted impact"
                ),
                "Loan_Impact": st.column_config.NumberColumn(
                    "  > Loan",
                    format="%.1f",
                    width=70,
                    help="Loan volume growth contribution (Growth%/2)"
                ),
                "NIM_Impact": st.column_config.NumberColumn(
                    "  > NIM",
                    format="%.1f",
                    width=70,
                    help="Net Interest Margin change contribution"
                ),
                "Fee_Impact": st.column_config.NumberColumn(
                    "- Fees",
                    format="%.1f",
                    width=75,
                    help="Fee income weighted impact"
                ),
                "Cost_Impact": st.column_config.NumberColumn(
                    "**Cost**",
                    format="%.1f",
                    width=95,
                    help="Total weighted cost contribution"
                ),
                "OPEX_Impact": st.column_config.NumberColumn(
                    "- OPEX",
                    format="%.1f",
                    width=75,
                    help="Operating expense weighted impact"
                ),
                "Provision_Impact": st.column_config.NumberColumn(
                    "- Prov",
                    format="%.1f",
                    width=75,
                    help="Provision expense weighted impact"
                ),
                "NonRec_Impact": st.column_config.NumberColumn(
                    "**Non-Rec**",
                    format="%.1f",
                    width=100,
                    help="Non-recurring items weighted impact"
                )
            }
            
            # Apply color styling to the weighted dataframe
            def color_main_scores(val):
                """Color main scores with strong colors and bold text"""
                if pd.isna(val):
                    return ''
                try:
                    num_val = float(val)
                    if num_val > 0:
                        # Strong green for positive with bold
                        intensity = min(abs(num_val) / 200, 1) * 0.7 + 0.2  # Stronger base intensity
                        return f'background-color: rgba(40, 167, 69, {intensity}); font-weight: bold; color: white'
                    elif num_val < 0:
                        # Strong red for negative with bold
                        intensity = min(abs(num_val) / 200, 1) * 0.7 + 0.2  # Stronger base intensity
                        return f'background-color: rgba(220, 53, 69, {intensity}); font-weight: bold; color: white'
                except:
                    return ''
                return ''
            
            def color_sub_scores(val):
                """Color sub-component scores with lighter colors"""
                if pd.isna(val):
                    return ''
                try:
                    num_val = float(val)
                    if num_val > 0:
                        # Light green for positive
                        intensity = min(abs(num_val) / 300, 1) * 0.25 + 0.05  # Much lighter
                        return f'background-color: rgba(40, 167, 69, {intensity})'
                    elif num_val < 0:
                        # Light red for negative
                        intensity = min(abs(num_val) / 300, 1) * 0.25 + 0.05  # Much lighter
                        return f'background-color: rgba(220, 53, 69, {intensity})'
                except:
                    return ''
                return ''
            
            # Style the dataframe
            weighted_styled = weighted_display_df.style
            
            # Apply strong colors to main score columns
            main_score_cols = ['Revenue_Impact', 'Cost_Impact', 'NonRec_Impact']
            for col in main_score_cols:
                if col in weighted_display_df.columns:
                    weighted_styled = weighted_styled.map(color_main_scores, subset=[col])
            
            # Apply lighter colors to sub-component columns
            sub_score_cols = ['NII_Impact', 'Loan_Impact', 'NIM_Impact', 'Fee_Impact', 
                            'OPEX_Impact', 'Provision_Impact']
            for col in sub_score_cols:
                if col in weighted_display_df.columns:
                    weighted_styled = weighted_styled.map(color_sub_scores, subset=[col])
            
            # Color PBT growth
            if 'PBT_Growth_%' in weighted_display_df.columns:
                weighted_styled = weighted_styled.map(
                    lambda x: 'color: #28a745; font-weight: bold' if x > 0 else 'color: #dc3545; font-weight: bold' if x < 0 else '',
                    subset=['PBT_Growth_%']
                )
            
            # Display weighted table with improved height
            st.dataframe(
                weighted_styled,
                column_config=weighted_column_config,
                use_container_width=True,
                height=700,
                hide_index=True
            )
            
            # Add explanation and legend
            st.info(
                "**Weighted Impact Scores**: \n"
                "- Impact Score = Component Score × PBT Growth % / 100\n"
                "- **Loan Impact** = Loan_Growth_% / 2 (direct measure of volume growth)\n"
                "- **NIM Impact** = NII_Impact - Loan_Impact (margin contribution)\n"
                "- Click column headers to sort | Drag borders to resize"
            )
            
            # Download button
            csv = weighted_display_df.to_csv(index=False)
            st.download_button(
                label="Download Impact Analysis as CSV",
                data=csv,
                file_name=f'earnings_impact_{selected_period}.csv',
                mime='text/csv',
                key='download_impact'
            )
    
    # Page 2: Trend Analysis
    elif page == "Trend Analysis":
        st.header("Score Trend Analysis")
        
        # Show comparison period and actual columns being used
        if data_type == "Quarterly":
            st.info(f"Using comparison period: {comparison_period}")
            # Debug info - show which columns are actually being used
            st.caption(f"Data columns suffix: '{comparison_suffix}' (empty means using backward compatibility columns)")
        
        # Ticker selection
        tickers = sorted(df_with_scores['TICKER'].unique())
        selected_tickers = st.multiselect("Select Banks (max 5)", tickers, default=["Sector"], max_selections=5)
        
        if selected_tickers:
            # Filter data for selected tickers
            trend_df = df_with_scores[df_with_scores['TICKER'].isin(selected_tickers)].copy()
            trend_df = trend_df.sort_values([period_col])
            
            # Limit to last 10 data points per ticker
            trend_df_limited = pd.DataFrame()
            for ticker in selected_tickers:
                ticker_data = trend_df[trend_df['TICKER'] == ticker].tail(10)
                trend_df_limited = pd.concat([trend_df_limited, ticker_data])
            trend_df = trend_df_limited
            
            # PBT Growth % is already calculated in the data file, no need to recalculate
            
            # Determine score column names based on comparison type
            if data_type == "Quarterly":
                # Use the actual suffix that was determined when loading data
                top_line_col = f'Top_Line_Score{comparison_suffix}' if comparison_suffix else 'Top_Line_Score'
                cost_col = f'Cost_Cutting_Score{comparison_suffix}' if comparison_suffix else 'Cost_Cutting_Score'
                nonrec_col = f'Non_Recurring_Score{comparison_suffix}' if comparison_suffix else 'Non_Recurring_Score'
                nii_col = f'NII_Sub_Score{comparison_suffix}' if comparison_suffix else 'NII_Sub_Score'
                fee_col = f'Fee_Sub_Score{comparison_suffix}' if comparison_suffix else 'Fee_Sub_Score'
                opex_col = f'OPEX_Sub_Score{comparison_suffix}' if comparison_suffix else 'OPEX_Sub_Score'
                prov_col = f'Provision_Sub_Score{comparison_suffix}' if comparison_suffix else 'Provision_Sub_Score'
                # For Loan, we need the Loan_Growth_% column, not the score
                loan_growth_pct_col = f'Loan_Growth_%{comparison_suffix}' if comparison_suffix else 'Loan_Growth_%'
            else:
                top_line_col = 'Top_Line_Score'
                cost_col = 'Cost_Cutting_Score'
                nonrec_col = 'Non_Recurring_Score'
                nii_col = 'NII_Sub_Score'
                fee_col = 'Fee_Sub_Score'
                opex_col = 'OPEX_Sub_Score'
                prov_col = 'Provision_Sub_Score'
                loan_growth_pct_col = 'Loan_Growth_%'
            
            # Use pre-calculated weighted impact scores from data
            if data_type == "Quarterly" and comparison_suffix:
                pbt_growth_col = f'PBT_Growth_%{comparison_suffix}'
                revenue_impact_col = f'Top_Line_Impact{comparison_suffix}'
                cost_impact_col = f'Cost_Cutting_Impact{comparison_suffix}'
                nonrec_impact_col = f'Non_Recurring_Impact{comparison_suffix}'
                nii_impact_col = f'NII_Impact{comparison_suffix}'
                fee_impact_col = f'Fee_Impact{comparison_suffix}'
                opex_impact_col = f'OPEX_Impact{comparison_suffix}'
                prov_impact_col = f'Provision_Impact{comparison_suffix}'
                loan_impact_col = f'Loan_Impact{comparison_suffix}'
                nim_impact_col = f'NIM_Impact{comparison_suffix}'
            else:
                pbt_growth_col = 'PBT_Growth_%'
                revenue_impact_col = 'Top_Line_Impact'
                cost_impact_col = 'Cost_Cutting_Impact'
                nonrec_impact_col = 'Non_Recurring_Impact'
                nii_impact_col = 'NII_Impact'
                fee_impact_col = 'Fee_Impact'
                opex_impact_col = 'OPEX_Impact'
                prov_impact_col = 'Provision_Impact'
                loan_impact_col = 'Loan_Impact'
                nim_impact_col = 'NIM_Impact'
            
            # Copy pre-calculated impacts from source data
            trend_df['PBT_Growth_%'] = trend_df[pbt_growth_col] if pbt_growth_col in trend_df.columns else 0
            trend_df['Revenue_Impact'] = trend_df[revenue_impact_col] if revenue_impact_col in trend_df.columns else 0
            trend_df['Cost_Impact'] = trend_df[cost_impact_col] if cost_impact_col in trend_df.columns else 0
            trend_df['NonRec_Impact'] = trend_df[nonrec_impact_col] if nonrec_impact_col in trend_df.columns else 0
            trend_df['NII_Impact'] = trend_df[nii_impact_col] if nii_impact_col in trend_df.columns else 0
            trend_df['Fee_Impact'] = trend_df[fee_impact_col] if fee_impact_col in trend_df.columns else 0
            trend_df['OPEX_Impact'] = trend_df[opex_impact_col] if opex_impact_col in trend_df.columns else 0
            trend_df['Provision_Impact'] = trend_df[prov_impact_col] if prov_impact_col in trend_df.columns else 0
            trend_df['Loan_Impact'] = trend_df[loan_impact_col] if loan_impact_col in trend_df.columns else 0
            trend_df['NIM_Impact'] = trend_df[nim_impact_col] if nim_impact_col in trend_df.columns else 0
            
            # Format quarters for display if quarterly data
            if period_col == 'Date_Quarter':
                trend_df['Date_Quarter_Display'] = trend_df['Date_Quarter'].apply(format_quarter_for_display)
                display_col = 'Date_Quarter_Display'
            else:
                display_col = period_col
            
            # Create subplots
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=("Revenue Impact Trend", "Cost Impact Trend",
                              "Non-Recurring Impact Trend", "PBT Growth Trend (%)")
            )
            
            # Plot each weighted impact score
            for ticker in selected_tickers:
                ticker_data = trend_df[trend_df['TICKER'] == ticker]
                
                # Revenue Impact (previously Top Line Score)
                if 'Revenue_Impact' in ticker_data.columns:
                    x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data['Revenue_Impact'],
                                 name=ticker, mode='lines+markers', legendgroup=ticker,
                                 hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'),
                        row=1, col=1
                    )
                
                # Cost Impact (previously Cost Cutting Score)
                if 'Cost_Impact' in ticker_data.columns:
                    x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data['Cost_Impact'],
                                 name=ticker, mode='lines+markers', legendgroup=ticker, showlegend=False,
                                 hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'),
                        row=1, col=2
                    )
                
                # Non-Recurring Impact (previously Non-Recurring Score)
                if 'NonRec_Impact' in ticker_data.columns:
                    x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data['NonRec_Impact'],
                                 name=ticker, mode='lines+markers', legendgroup=ticker, showlegend=False,
                                 hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'),
                        row=2, col=1
                    )
                
                # PBT Growth %
                if 'PBT_Growth_%' in ticker_data.columns:
                    x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data['PBT_Growth_%'],
                                 name=ticker, mode='lines+markers', legendgroup=ticker, showlegend=False,
                                 hovertemplate='%{x}<br>%{y:.1f}%<extra></extra>'),
                        row=2, col=2
                    )
            
            # Update layout with consistent styling
            fig.update_layout(
                height=700, 
                title_text="Score Trends Over Time",
                font=dict(family="Inter, sans-serif", size=12),
                hovermode='x unified',
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            fig.update_xaxes(title_text=period_col, showgrid=True, gridcolor='rgba(0,0,0,0.1)')
            fig.update_yaxes(title_text="Impact / Growth (%)", showgrid=True, gridcolor='rgba(0,0,0,0.1)', 
                           tickformat='.1f')
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Sub-score breakdown chart
            st.subheader("Sub-Score Breakdown")
            
            # Create tabs for different sub-scores
            tab1, tab2, tab3 = st.tabs(["Revenue Sub-Scores", "Cost Sub-Scores", "NII Breakdown (Loan vs NIM)"])
            
            with tab1:
                # NII vs Fee Income impacts
                fig_revenue = go.Figure()
                
                for ticker in selected_tickers:
                    ticker_data = trend_df[trend_df['TICKER'] == ticker]
                    
                    # Use weighted impact columns
                    if 'NII_Impact' in ticker_data.columns:
                        x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                        fig_revenue.add_trace(go.Scatter(
                            x=x_data, 
                            y=ticker_data['NII_Impact'],
                            name=f"{ticker} - NII",
                            mode='lines+markers',
                            hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'
                        ))
                    
                    if 'Fee_Impact' in ticker_data.columns:
                        x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                        fig_revenue.add_trace(go.Scatter(
                            x=x_data, 
                            y=ticker_data['Fee_Impact'],
                            name=f"{ticker} - Fees",
                            mode='lines+markers',
                            line=dict(dash='dash'),
                            hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'
                        ))
                
                fig_revenue.update_layout(
                    title="Revenue Component Impacts (NII vs Fees)",
                    xaxis_title=period_col,
                    yaxis_title="Score (%)",
                    height=400,
                    font=dict(family="Inter, sans-serif", size=12),
                    hovermode='x unified',
                    showlegend=True
                )
                fig_revenue.update_xaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
                fig_revenue.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)', tickformat='.1f')
                
                st.plotly_chart(fig_revenue, use_container_width=True)
            
            with tab2:
                # OPEX vs Provision impacts
                fig_cost = go.Figure()
                
                for ticker in selected_tickers:
                    ticker_data = trend_df[trend_df['TICKER'] == ticker]
                    
                    # Use weighted impact columns
                    if 'OPEX_Impact' in ticker_data.columns:
                        x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                        fig_cost.add_trace(go.Scatter(
                            x=x_data, 
                            y=ticker_data['OPEX_Impact'],
                            name=f"{ticker} - OPEX",
                            mode='lines+markers',
                            hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'
                        ))
                    
                    if 'Provision_Impact' in ticker_data.columns:
                        x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                        fig_cost.add_trace(go.Scatter(
                            x=x_data, 
                            y=ticker_data['Provision_Impact'],
                            name=f"{ticker} - Provision",
                            mode='lines+markers',
                            line=dict(dash='dash'),
                            hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'
                        ))
                
                fig_cost.update_layout(
                    title="Cost Component Impacts (OPEX vs Provisions)",
                    xaxis_title=period_col,
                    yaxis_title="Score (%)",
                    height=400,
                    font=dict(family="Inter, sans-serif", size=12),
                    hovermode='x unified',
                    showlegend=True
                )
                fig_cost.update_xaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
                fig_cost.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)', tickformat='.1f')
                
                st.plotly_chart(fig_cost, use_container_width=True)
            
            with tab3:
                # NII Breakdown: Loan Growth vs NIM Change impacts
                fig_nii = go.Figure()
                
                for ticker in selected_tickers:
                    ticker_data = trend_df[trend_df['TICKER'] == ticker]
                    
                    # Use weighted impact columns
                    if 'Loan_Impact' in ticker_data.columns:
                        x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                        fig_nii.add_trace(go.Scatter(
                            x=x_data, 
                            y=ticker_data['Loan_Impact'],
                            name=f"{ticker} - Loan Growth",
                            mode='lines+markers',
                            hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'
                        ))
                    
                    if 'NIM_Impact' in ticker_data.columns:
                        x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                        fig_nii.add_trace(go.Scatter(
                            x=x_data, 
                            y=ticker_data['NIM_Impact'],
                            name=f"{ticker} - NIM Change",
                            mode='lines+markers',
                            line=dict(dash='dash'),
                            hovertemplate='%{x}<br>%{y:.1f}<extra></extra>'
                        ))
                
                fig_nii.update_layout(
                    title="NII Breakdown: Loan Growth vs NIM Change Impact",
                    xaxis_title=period_col,
                    yaxis_title="Score (%)",
                    height=400,
                    font=dict(family="Inter, sans-serif", size=12),
                    hovermode='x unified',
                    showlegend=True
                )
                fig_nii.update_xaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)')
                fig_nii.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.1)', tickformat='.1f')
                
                st.plotly_chart(fig_nii, use_container_width=True)
                
                # Add explanation
                st.caption(
                    "**NII Breakdown Interpretation:**\n"
                    "- **Loan Growth Score** = Loan_Growth_% / 2 (volume-driven NII growth)\n"
                    "- **NIM Change Score** = NII_Sub_Score - Loan_Growth_Score (margin-driven NII growth)\n"
                    "- Positive values indicate contribution to profit growth"
                )
    
    # Page 3: Statistical Summary
    elif page == "Statistical Summary":
        st.header("Statistical Summary")
        
        # Get latest period
        latest_period = df_with_scores[period_col].max()
        latest_df = df_with_scores[df_with_scores[period_col] == latest_period].copy()
        
        # Summary by bank type
        st.subheader(f"Average Scores by Bank Type ({latest_period})")
        
        # Use the same suffix that was determined earlier for consistency
        if data_type == "Quarterly":
            # Build column names with the actual suffix being used
            suffix = comparison_suffix if comparison_suffix else ''
            agg_dict = {
                f'Top_Line_Score{suffix}': 'mean',
                f'NII_Sub_Score{suffix}': 'mean',
                f'Fee_Sub_Score{suffix}': 'mean',
                f'Cost_Cutting_Score{suffix}': 'mean',
                f'OPEX_Sub_Score{suffix}': 'mean',
                f'Provision_Sub_Score{suffix}': 'mean',
                f'Non_Recurring_Score{suffix}': 'mean',
                f'Total_Score{suffix}': 'mean'
            }
            # Filter to only include columns that exist
            agg_dict = {k: v for k, v in agg_dict.items() if k in latest_df.columns}
        else:
            agg_dict = {
                'Top_Line_Score': 'mean',
                'NII_Sub_Score': 'mean',
                'Fee_Sub_Score': 'mean',
                'Cost_Cutting_Score': 'mean',
                'OPEX_Sub_Score': 'mean',
                'Provision_Sub_Score': 'mean',
                'Non_Recurring_Score': 'mean',
                'Total_Score': 'mean'
            }
            # Filter to only include columns that exist
            agg_dict = {k: v for k, v in agg_dict.items() if k in latest_df.columns}
        
        if agg_dict:
            summary_by_type = latest_df.groupby('Type').agg(agg_dict).round(1)
        else:
            summary_by_type = pd.DataFrame()
        
        # Display with formatting and color coding
        def color_scores(val):
            """Color scores based on value"""
            if pd.isna(val):
                return ''
            try:
                num_val = float(val)
                if num_val > 50:
                    return 'color: green'
                elif num_val < -50:
                    return 'color: red'
                elif num_val > 0:
                    return 'color: darkgreen'
                elif num_val < 0:
                    return 'color: darkred'
            except:
                pass
            return ''
        
        styled_summary = summary_by_type.style.format("{:.1f}")
        for col in summary_by_type.columns:
            styled_summary = styled_summary.map(color_scores, subset=[col])
        
        st.dataframe(
            styled_summary,
            use_container_width=True
        )
        
        # Distribution plots with dynamic bins
        st.subheader("Score Distributions")
        
        # Create custom bins - smaller near 0, larger at extremes
        def create_dynamic_bins(min_val, max_val):
            """Create bins that are smaller near 0 and larger at extremes"""
            bins = []
            
            # Negative side bins (from min to 0)
            if min_val < -200:
                bins.extend([min_val, -500, -300, -200])
            elif min_val < -100:
                bins.extend([min_val, -200])
            
            # Core negative bins (smaller intervals)
            bins.extend([-150, -100, -75, -50, -30, -20, -10, -5])
            
            # Zero and positive core bins
            bins.extend([0, 5, 10, 20, 30, 50, 75, 100, 150])
            
            # Positive extreme bins
            if max_val > 200:
                bins.extend([200, 300, 500, max_val])
            elif max_val > 100:
                bins.extend([200, max_val])
            
            # Filter bins to be within actual data range
            bins = [b for b in bins if b >= min_val and b <= max_val]
            
            # Ensure we have min and max
            if min_val not in bins:
                bins.insert(0, min_val)
            if max_val not in bins:
                bins.append(max_val)
            
            return sorted(list(set(bins)))  # Remove duplicates and sort
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Top Line Score distribution with custom bins
            # Use the same suffix that was determined earlier
            if data_type == "Quarterly":
                top_line_col = f'Top_Line_Score{comparison_suffix}' if comparison_suffix else 'Top_Line_Score'
            else:
                top_line_col = 'Top_Line_Score'
            if top_line_col in latest_df.columns:
                top_line_data = latest_df[top_line_col].dropna()
            else:
                top_line_data = pd.Series([])
            bins1 = create_dynamic_bins(top_line_data.min(), top_line_data.max())
            
            # Calculate histogram with custom bins
            counts1, _ = np.histogram(top_line_data, bins=bins1)
            
            fig_dist1 = go.Figure()
            
            # Create bars for each bin
            for i in range(len(bins1)-1):
                bin_center = (bins1[i] + bins1[i+1]) / 2
                bin_width = bins1[i+1] - bins1[i]
                
                fig_dist1.add_trace(go.Bar(
                    x=[bin_center],
                    y=[counts1[i]],
                    width=bin_width * 0.9,  # Small gap between bars
                    marker=dict(
                        color='rgba(40, 167, 69, 0.6)' if bin_center >= 0 else 'rgba(220, 53, 69, 0.6)',
                        line=dict(color='rgba(40, 167, 69, 1)' if bin_center >= 0 else 'rgba(220, 53, 69, 1)', width=1)
                    ),
                    showlegend=False,
                    hovertemplate=f'Range: {bins1[i]:.0f} to {bins1[i+1]:.0f}<br>Count: {counts1[i]}<extra></extra>'
                ))
            
            fig_dist1.update_layout(
                title="Top Line Score Distribution",
                xaxis_title="Score (%)",
                yaxis_title="Number of Banks",
                bargap=0.02,
                showlegend=False,
                font=dict(family="Inter, sans-serif", size=12),
                xaxis=dict(
                    range=[bins1[0], bins1[-1]],
                    tickmode='linear',
                    tick0=-500,
                    dtick=50,
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                )
            )
            st.plotly_chart(fig_dist1, use_container_width=True)
        
        with col2:
            # Cost Cutting Score distribution with custom bins
            # Use the same suffix that was determined earlier
            if data_type == "Quarterly":
                cost_col = f'Cost_Cutting_Score{comparison_suffix}' if comparison_suffix else 'Cost_Cutting_Score'
            else:
                cost_col = 'Cost_Cutting_Score'
            if cost_col in latest_df.columns:
                cost_data = latest_df[cost_col].dropna()
            else:
                cost_data = pd.Series([])
            bins2 = create_dynamic_bins(cost_data.min(), cost_data.max())
            
            # Calculate histogram with custom bins
            counts2, _ = np.histogram(cost_data, bins=bins2)
            
            fig_dist2 = go.Figure()
            
            # Create bars for each bin
            for i in range(len(bins2)-1):
                bin_center = (bins2[i] + bins2[i+1]) / 2
                bin_width = bins2[i+1] - bins2[i]
                
                fig_dist2.add_trace(go.Bar(
                    x=[bin_center],
                    y=[counts2[i]],
                    width=bin_width * 0.9,  # Small gap between bars
                    marker=dict(
                        color='rgba(0, 123, 255, 0.6)' if bin_center >= 0 else 'rgba(255, 193, 7, 0.6)',
                        line=dict(color='rgba(0, 123, 255, 1)' if bin_center >= 0 else 'rgba(255, 193, 7, 1)', width=1)
                    ),
                    showlegend=False,
                    hovertemplate=f'Range: {bins2[i]:.0f} to {bins2[i+1]:.0f}<br>Count: {counts2[i]}<extra></extra>'
                ))
            
            fig_dist2.update_layout(
                title="Cost Cutting Score Distribution",
                xaxis_title="Score (%)",
                yaxis_title="Number of Banks",
                bargap=0.02,
                showlegend=False,
                font=dict(family="Inter, sans-serif", size=12),
                xaxis=dict(
                    range=[bins2[0], bins2[-1]],
                    tickmode='linear',
                    tick0=-500,
                    dtick=50,
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                )
            )
            st.plotly_chart(fig_dist2, use_container_width=True)
        
        # Top and bottom performers
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"Top 10 Performers - Total Score ({latest_period})")
            # Use the same suffix that was determined earlier
            if data_type == "Quarterly":
                total_col = f'Total_Score{comparison_suffix}' if comparison_suffix else 'Total_Score'
                top_line_col = f'Top_Line_Score{comparison_suffix}' if comparison_suffix else 'Top_Line_Score'
                cost_col = f'Cost_Cutting_Score{comparison_suffix}' if comparison_suffix else 'Cost_Cutting_Score'
            else:
                total_col = 'Total_Score'
                top_line_col = 'Top_Line_Score'
                cost_col = 'Cost_Cutting_Score'
            
            if total_col in latest_df.columns:
                display_cols = ['TICKER', 'Type'] + [c for c in [total_col, top_line_col, cost_col] if c in latest_df.columns]
                top_performers = latest_df.nlargest(10, total_col)[display_cols]
                # Format columns that exist
                format_dict = {}
                for col in display_cols:
                    if 'Score' in col:
                        format_dict[col] = '{:.1f}%'
                if format_dict:
                    st.dataframe(top_performers.style.format(format_dict))
                else:
                    st.dataframe(top_performers)
            else:
                st.info("No data available for selected comparison period")
        
        with col2:
            st.subheader(f"Bottom 10 Performers - Total Score ({latest_period})")
            # Use the same suffix that was determined earlier
            if data_type == "Quarterly":
                total_col = f'Total_Score{comparison_suffix}' if comparison_suffix else 'Total_Score'
                top_line_col = f'Top_Line_Score{comparison_suffix}' if comparison_suffix else 'Top_Line_Score'
                cost_col = f'Cost_Cutting_Score{comparison_suffix}' if comparison_suffix else 'Cost_Cutting_Score'
            else:
                total_col = 'Total_Score'
                top_line_col = 'Top_Line_Score'
                cost_col = 'Cost_Cutting_Score'
            
            if total_col in latest_df.columns:
                display_cols = ['TICKER', 'Type'] + [c for c in [total_col, top_line_col, cost_col] if c in latest_df.columns]
                bottom_performers = latest_df.nsmallest(10, total_col)[display_cols]
                # Format columns that exist
                format_dict = {}
                for col in display_cols:
                    if 'Score' in col:
                        format_dict[col] = '{:.1f}%'
                if format_dict:
                    st.dataframe(bottom_performers.style.format(format_dict))
                else:
                    st.dataframe(bottom_performers)
            else:
                st.info("No data available for selected comparison period")
        
        # Correlation heatmap
        st.subheader("Score Correlations")
        
        # Determine score columns for correlation matrix
        # Use the same suffix that was determined earlier
        if data_type == "Quarterly":
            suffix = comparison_suffix if comparison_suffix else ''
            score_cols = [f'Top_Line_Score{suffix}', f'NII_Sub_Score{suffix}', 
                         f'Fee_Sub_Score{suffix}', f'Cost_Cutting_Score{suffix}', 
                         f'OPEX_Sub_Score{suffix}', f'Provision_Sub_Score{suffix}', 
                         f'Non_Recurring_Score{suffix}']
        else:
            score_cols = ['Top_Line_Score', 'NII_Sub_Score', 'Fee_Sub_Score', 
                         'Cost_Cutting_Score', 'OPEX_Sub_Score', 'Provision_Sub_Score', 
                         'Non_Recurring_Score']
        
        # Filter to only include columns that exist
        score_cols = [col for col in score_cols if col in latest_df.columns]
        
        if score_cols:
            corr_matrix = latest_df[score_cols].corr()
            
            if not corr_matrix.empty:
                fig_corr = px.imshow(corr_matrix, 
                                   labels=dict(color="Correlation"),
                                   x=score_cols,
                                   y=score_cols,
                                   color_continuous_scale='RdBu',
                                   aspect="auto")
                
                fig_corr.update_layout(
                    title="Score Correlation Matrix",
                    font=dict(family="Inter, sans-serif", size=12)
                )
                st.plotly_chart(fig_corr, use_container_width=True)
            else:
                st.info("Insufficient data for correlation matrix")
        else:
            st.info("No score columns available for correlation analysis")

else:
    st.error("Unable to load data files. Please ensure earnings_quality_quarterly.csv and earnings_quality_yearly.csv exist in the Data folder.")
    st.info("Run the scripts/Prepare_earnings_driver.py script first to generate the required data files.")

# Footer
st.markdown("---")
st.markdown("### About this Dashboard")
st.markdown("""
This dashboard analyzes bank earnings quality by breaking down profit changes into three main components:
- **Top Line Growth**: Revenue-driven changes (NII and Fee income)
- **Cost Cutting**: Efficiency improvements (OPEX and Provision expense reductions)
- **Non-Recurring Items**: One-time or unusual income

Scores show each component's contribution as a percentage of the absolute PBT change.
""")