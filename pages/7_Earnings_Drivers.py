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
    page_title="Bank Earnings Drivers Dashboard",
    page_icon="📊",
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
st.title("Bank Earnings Drivers Analysis Dashboard")
st.markdown("### Analyze earnings drivers through revenue growth, cost efficiency, and non-recurring items")

# Load data
@st.cache_data
def load_data():
    """Load quarterly and yearly data"""
    try:
        quarterly_df = pd.read_parquet(os.path.join(project_root, 'Data/earnings_quality_quarterly.parquet'))
        yearly_df = pd.read_parquet(os.path.join(project_root, 'Data/earnings_quality_yearly.parquet'))
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
                            ["Impact Analysis", 
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
    
    # Filter out rows without impacts
    impact_col = f'Top_Line_Impact{comparison_suffix}' if data_type == "Quarterly" else 'Top_Line_Impact'
    df_with_impacts = df[df[impact_col].notna()].copy() if impact_col in df.columns else df.copy()
    
    # Page 1: Impact Analysis
    if page == "Impact Analysis":
        st.header("Weighted Impact Analysis")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Period selection
            periods = sorted(df_with_impacts[period_col].unique(), reverse=True)
            if periods:
                selected_period = st.selectbox(f"Select {period_col}", periods)
            else:
                st.error("No data available")
                selected_period = None
        
        with col2:
            # Bank type filter
            bank_types = ['All'] + list(df_with_impacts['Type'].unique())
            selected_type = st.selectbox("Filter by Bank Type", bank_types)
        
        with col3:
            # Ticker search
            search_ticker = st.text_input("Search Ticker", "")
        
        if selected_period:
            # Filter data
            filtered_df = df_with_impacts[df_with_impacts[period_col] == selected_period].copy()
            
            if selected_type != 'All':
                filtered_df = filtered_df[filtered_df['Type'] == selected_type]
            
            if search_ticker:
                filtered_df = filtered_df[filtered_df['TICKER'].str.contains(search_ticker.upper())]
            
            # Get appropriate column names based on comparison type
            if data_type == "Quarterly":
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
                total_impact_col = f'Total_Impact{comparison_suffix}'
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
                total_impact_col = 'Total_Impact'
            
            # Display metrics
            st.subheader(f"Weighted Impact Analysis for {selected_period}")
            st.caption("Shows how much each component contributes to the PBT growth rate (in percentage points)")
            
            # Summary cards
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if revenue_impact_col in filtered_df.columns:
                    avg_revenue_impact = filtered_df[revenue_impact_col].mean()
                    st.metric("Avg Revenue Impact", f"{avg_revenue_impact:.1f}pp")
            
            with col2:
                if cost_impact_col in filtered_df.columns:
                    avg_cost_impact = filtered_df[cost_impact_col].mean()
                    st.metric("Avg Cost Impact", f"{avg_cost_impact:.1f}pp")
            
            with col3:
                if nonrec_impact_col in filtered_df.columns:
                    avg_nonrec_impact = filtered_df[nonrec_impact_col].mean()
                    st.metric("Avg Non-Rec Impact", f"{avg_nonrec_impact:.1f}pp")
            
            with col4:
                num_banks = len(filtered_df)
                st.metric("Banks Analyzed", num_banks)
            
            # Prepare display dataframe
            display_cols = ['TICKER', 'Type']
            
            # Add columns that exist
            for col_name, col_var in [
                ('PBT Growth %', pbt_growth_col),
                ('Revenue Impact', revenue_impact_col),
                ('- NII', nii_impact_col),
                ('  > Loan', loan_impact_col),
                ('  > NIM', nim_impact_col),
                ('- Fees', fee_impact_col),
                ('Cost Impact', cost_impact_col),
                ('- OPEX', opex_impact_col),
                ('- Provisions', prov_impact_col),
                ('Non-Recurring', nonrec_impact_col),
                ('Total Impact', total_impact_col)
            ]:
                if col_var in filtered_df.columns:
                    filtered_df[col_name] = filtered_df[col_var]
                    display_cols.append(col_name)
            
            display_df = filtered_df[display_cols].copy()
            
            # Sort by absolute revenue impact
            if 'Revenue Impact' in display_df.columns:
                display_df['abs_impact'] = display_df['Revenue Impact'].abs()
                display_df = display_df.sort_values('abs_impact', ascending=False)
                display_df = display_df.drop('abs_impact', axis=1)
            
            # Configure table columns
            column_config = {
                "TICKER": st.column_config.TextColumn("Ticker", width=80),
                "Type": st.column_config.TextColumn("Type", width=90),
                "PBT Growth %": st.column_config.NumberColumn(
                    "PBT Growth", format="%.1f%%", width=100,
                    help="PBT growth rate"
                ),
                "Revenue Impact": st.column_config.NumberColumn(
                    "**Revenue**", format="%.1fpp", width=100,
                    help="Total revenue contribution to PBT growth"
                ),
                "Cost Impact": st.column_config.NumberColumn(
                    "**Cost**", format="%.1fpp", width=95,
                    help="Total cost contribution to PBT growth"
                ),
                "Non-Recurring": st.column_config.NumberColumn(
                    "**Non-Rec**", format="%.1fpp", width=100,
                    help="Non-recurring items contribution"
                ),
                "Total Impact": st.column_config.NumberColumn(
                    "**Total**", format="%.1fpp", width=95,
                    help="Total impact (should equal PBT growth)"
                )
            }
            
            # Add sub-component configurations
            for col in display_cols:
                if col.startswith('-') or col.startswith(' '):
                    column_config[col] = st.column_config.NumberColumn(
                        col, format="%.1fpp", width=75
                    )
            
            # Apply color styling
            def color_main_impacts(val):
                """Color main impact columns"""
                if pd.isna(val):
                    return ''
                try:
                    num_val = float(val)
                    if num_val > 0:
                        intensity = min(abs(num_val) / 50, 1) * 0.4 + 0.1
                        return f'background-color: rgba(40, 167, 69, {intensity}); font-weight: bold'
                    elif num_val < 0:
                        intensity = min(abs(num_val) / 50, 1) * 0.4 + 0.1
                        return f'background-color: rgba(220, 53, 69, {intensity}); font-weight: bold'
                except:
                    return ''
                return ''
            
            def color_sub_impacts(val):
                """Color sub-component impacts"""
                if pd.isna(val):
                    return ''
                try:
                    num_val = float(val)
                    if num_val > 0:
                        intensity = min(abs(num_val) / 50, 1) * 0.15 + 0.05
                        return f'background-color: rgba(40, 167, 69, {intensity})'
                    elif num_val < 0:
                        intensity = min(abs(num_val) / 50, 1) * 0.15 + 0.05
                        return f'background-color: rgba(220, 53, 69, {intensity})'
                except:
                    return ''
                return ''
            
            # Style the dataframe
            styled_df = display_df.style
            
            # Apply colors to main columns
            main_cols = ['Revenue Impact', 'Cost Impact', 'Non-Recurring', 'Total Impact']
            for col in main_cols:
                if col in display_df.columns:
                    styled_df = styled_df.map(color_main_impacts, subset=[col])
            
            # Apply colors to sub-columns
            sub_cols = [col for col in display_df.columns if col.startswith('-') or col.startswith(' ')]
            for col in sub_cols:
                styled_df = styled_df.map(color_sub_impacts, subset=[col])
            
            # Display table
            st.dataframe(
                styled_df,
                column_config=column_config,
                use_container_width=True,
                height=600,
                hide_index=True
            )
            
            # Add explanation
            st.info(
                "**Weighted Impact Analysis**: \n"
                "- Each value shows the percentage point contribution to PBT growth\n"
                "- **Loan Impact** = Loan_Growth_% / 2 (volume-driven growth)\n"
                "- **NIM Impact** = NII_Impact - Loan_Impact (margin contribution)\n"
                "- Positive values add to profit growth, negative values reduce it"
            )
            
            # Download button
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Download Impact Analysis as CSV",
                data=csv,
                file_name=f'earnings_impact_{selected_period}.csv',
                mime='text/csv'
            )
    
    # Page 2: Trend Analysis
    elif page == "Trend Analysis":
        st.header("Impact Trend Analysis")
        
        # Show comparison period
        if data_type == "Quarterly":
            st.info(f"Using comparison period: {comparison_period}")
        
        # Ticker selection
        tickers = sorted(df_with_impacts['TICKER'].unique())
        selected_tickers = st.multiselect("Select Banks (max 5)", tickers, default=["Sector"], max_selections=5)
        
        if selected_tickers:
            # Filter data for selected tickers
            trend_df = df_with_impacts[df_with_impacts['TICKER'].isin(selected_tickers)].copy()
            trend_df = trend_df.sort_values([period_col])
            
            # Limit to last 10 data points per ticker
            trend_df_limited = pd.DataFrame()
            for ticker in selected_tickers:
                ticker_data = trend_df[trend_df['TICKER'] == ticker].tail(10)
                trend_df_limited = pd.concat([trend_df_limited, ticker_data])
            trend_df = trend_df_limited
            
            # Get column names
            if data_type == "Quarterly":
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
            
            # Plot each impact
            for ticker in selected_tickers:
                ticker_data = trend_df[trend_df['TICKER'] == ticker]
                x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                
                # Revenue Impact
                if revenue_impact_col in ticker_data.columns:
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data[revenue_impact_col],
                                 name=ticker, mode='lines+markers', legendgroup=ticker,
                                 hovertemplate='%{x}<br>%{y:.1f}pp<extra></extra>'),
                        row=1, col=1
                    )
                
                # Cost Impact
                if cost_impact_col in ticker_data.columns:
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data[cost_impact_col],
                                 name=ticker, mode='lines+markers', legendgroup=ticker, showlegend=False,
                                 hovertemplate='%{x}<br>%{y:.1f}pp<extra></extra>'),
                        row=1, col=2
                    )
                
                # Non-Recurring Impact
                if nonrec_impact_col in ticker_data.columns:
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data[nonrec_impact_col],
                                 name=ticker, mode='lines+markers', legendgroup=ticker, showlegend=False,
                                 hovertemplate='%{x}<br>%{y:.1f}pp<extra></extra>'),
                        row=2, col=1
                    )
                
                # PBT Growth %
                if pbt_growth_col in ticker_data.columns:
                    fig.add_trace(
                        go.Scatter(x=x_data, y=ticker_data[pbt_growth_col],
                                 name=ticker, mode='lines+markers', legendgroup=ticker, showlegend=False,
                                 hovertemplate='%{x}<br>%{y:.1f}%<extra></extra>'),
                        row=2, col=2
                    )
            
            # Update layout
            fig.update_layout(
                height=700, 
                title_text="Impact Trends Over Time",
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
            fig.update_yaxes(title_text="Impact (pp) / Growth (%)", showgrid=True, gridcolor='rgba(0,0,0,0.1)')
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Sub-component breakdown
            st.subheader("Sub-Component Breakdown")
            
            tab1, tab2, tab3 = st.tabs(["Revenue Components", "Cost Components", "NII Breakdown"])
            
            with tab1:
                fig_revenue = go.Figure()
                for ticker in selected_tickers:
                    ticker_data = trend_df[trend_df['TICKER'] == ticker]
                    x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                    
                    if nii_impact_col in ticker_data.columns:
                        fig_revenue.add_trace(go.Scatter(
                            x=x_data, y=ticker_data[nii_impact_col],
                            name=f"{ticker} - NII", mode='lines+markers'
                        ))
                    
                    if fee_impact_col in ticker_data.columns:
                        fig_revenue.add_trace(go.Scatter(
                            x=x_data, y=ticker_data[fee_impact_col],
                            name=f"{ticker} - Fees", mode='lines+markers', line=dict(dash='dash')
                        ))
                
                fig_revenue.update_layout(
                    title="Revenue Component Impacts",
                    xaxis_title=period_col,
                    yaxis_title="Impact (pp)",
                    height=400
                )
                st.plotly_chart(fig_revenue, use_container_width=True)
            
            with tab2:
                fig_cost = go.Figure()
                for ticker in selected_tickers:
                    ticker_data = trend_df[trend_df['TICKER'] == ticker]
                    x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                    
                    if opex_impact_col in ticker_data.columns:
                        fig_cost.add_trace(go.Scatter(
                            x=x_data, y=ticker_data[opex_impact_col],
                            name=f"{ticker} - OPEX", mode='lines+markers'
                        ))
                    
                    if prov_impact_col in ticker_data.columns:
                        fig_cost.add_trace(go.Scatter(
                            x=x_data, y=ticker_data[prov_impact_col],
                            name=f"{ticker} - Provisions", mode='lines+markers', line=dict(dash='dash')
                        ))
                
                fig_cost.update_layout(
                    title="Cost Component Impacts",
                    xaxis_title=period_col,
                    yaxis_title="Impact (pp)",
                    height=400
                )
                st.plotly_chart(fig_cost, use_container_width=True)
            
            with tab3:
                fig_nii = go.Figure()
                for ticker in selected_tickers:
                    ticker_data = trend_df[trend_df['TICKER'] == ticker]
                    x_data = ticker_data[display_col] if period_col == 'Date_Quarter' else ticker_data[period_col]
                    
                    if loan_impact_col in ticker_data.columns:
                        fig_nii.add_trace(go.Scatter(
                            x=x_data, y=ticker_data[loan_impact_col],
                            name=f"{ticker} - Loan Growth", mode='lines+markers'
                        ))
                    
                    if nim_impact_col in ticker_data.columns:
                        fig_nii.add_trace(go.Scatter(
                            x=x_data, y=ticker_data[nim_impact_col],
                            name=f"{ticker} - NIM", mode='lines+markers', line=dict(dash='dash')
                        ))
                
                fig_nii.update_layout(
                    title="NII Breakdown: Loan vs NIM Impact",
                    xaxis_title=period_col,
                    yaxis_title="Impact (pp)",
                    height=400
                )
                st.plotly_chart(fig_nii, use_container_width=True)
    
    # Page 3: Statistical Summary
    elif page == "Statistical Summary":
        st.header("Statistical Summary")
        
        # Get latest period
        latest_period = df_with_impacts[period_col].max()
        latest_df = df_with_impacts[df_with_impacts[period_col] == latest_period].copy()
        
        st.subheader(f"Average Impacts by Bank Type ({latest_period})")
        
        # Get column names
        if data_type == "Quarterly":
            suffix = comparison_suffix
            agg_dict = {
                f'Top_Line_Impact{suffix}': 'mean',
                f'Cost_Cutting_Impact{suffix}': 'mean',
                f'Non_Recurring_Impact{suffix}': 'mean',
                f'Total_Impact{suffix}': 'mean'
            }
        else:
            agg_dict = {
                'Top_Line_Impact': 'mean',
                'Cost_Cutting_Impact': 'mean',
                'Non_Recurring_Impact': 'mean',
                'Total_Impact': 'mean'
            }
        
        # Filter to existing columns
        agg_dict = {k: v for k, v in agg_dict.items() if k in latest_df.columns}
        
        if agg_dict:
            summary_by_type = latest_df.groupby('Type').agg(agg_dict).round(1)
            st.dataframe(summary_by_type.style.format("{:.1f}pp"))
        
        # Top and bottom performers
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Top 10 Performers")
            total_col = f'Total_Impact{comparison_suffix}' if data_type == "Quarterly" else 'Total_Impact'
            if total_col in latest_df.columns:
                top_df = latest_df.nlargest(10, total_col)[['TICKER', 'Type', total_col]]
                st.dataframe(top_df.style.format({total_col: '{:.1f}pp'}))
        
        with col2:
            st.subheader("Bottom 10 Performers")
            if total_col in latest_df.columns:
                bottom_df = latest_df.nsmallest(10, total_col)[['TICKER', 'Type', total_col]]
                st.dataframe(bottom_df.style.format({total_col: '{:.1f}pp'}))

else:
    st.error("Unable to load data files. Please ensure earnings_quality_quarterly.csv and earnings_quality_yearly.csv exist in the Data folder.")
    st.info("Run the scripts/Prepare_earnings_driver.py script first to generate the required data files.")

# Footer
st.markdown("---")
st.markdown("### About this Dashboard")
st.markdown("""
This dashboard analyzes bank earnings drivers by showing the weighted impact of each component on PBT growth:
- **Revenue Impact**: Contribution from NII and Fee income growth
- **Cost Impact**: Contribution from OPEX and Provision expense changes
- **Non-Recurring Impact**: Contribution from one-time or unusual items

All values are shown as percentage point contributions to the PBT growth rate.
""")