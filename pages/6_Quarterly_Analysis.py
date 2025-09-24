import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Quarterly Banking Analysis",
    page_icon="Analysis",
    layout="wide"
)

import pandas as pd
import os
from datetime import datetime
import sys
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import and apply Google Fonts
from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style
apply_google_font()

# Apply consistent sidebar styling
apply_sidebar_style()

# Import utilities
from utilities.quarter_utils import quarter_sort_key, sort_quarters
from utilities.data_access import load_comments, load_quarterly_analysis, load_earnings_quality
import plotly.graph_objects as go


@st.cache_data(ttl=1800)
def _load_quarterly_analysis():
    df = load_quarterly_analysis()
    if not df.empty:
        df['generated_date'] = pd.to_datetime(df['generated_date'], errors='coerce')
    return df


@st.cache_data(ttl=600)
def _load_comments():
    df = load_comments()
    if not df.empty:
        generated_col = 'GENERATED_AT' if 'GENERATED_AT' in df.columns else 'GENERATED_DATE'
        df['generated_display'] = pd.to_datetime(df[generated_col], errors='coerce')
    return df


@st.cache_data(ttl=600)
def _load_earnings_quality():
    return load_earnings_quality('Q')

def quarterly_analysis_page():
    st.title("Quarterly Banking Analysis")
    st.markdown("Comprehensive AI-powered analysis of banking comments for specific quarters")
    
    analysis_df = _load_quarterly_analysis()
    comments_df = _load_comments()

    if not analysis_df.empty:
        try:
            # Get available quarters from analysis results
            available_quarters_raw = analysis_df['quarter'].dropna().unique().tolist()
            available_quarters = sort_quarters(available_quarters_raw, reverse=True)
            
            # Quarter selection
            st.subheader("Select Quarter for Analysis")
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                selected_quarter = st.selectbox(
                    "Choose Quarter:",
                    available_quarters,
                    help="Select the quarter you want to view analysis for (sorted by most recent first)"
                )
            
            quarter_analysis = analysis_df[analysis_df['quarter'] == selected_quarter]

            with col2:
                if not quarter_analysis.empty:
                    status = quarter_analysis.iloc[0].get('status', 'unknown')
                    if status == 'success':
                        st.success("Analysis Available")
                    else:
                        st.error("Analysis Error")

            with col3:
                if not quarter_analysis.empty:
                    gen_date = quarter_analysis.iloc[0].get('generated_date')
                    if pd.notna(gen_date):
                        st.metric("Generated", gen_date.strftime('%Y-%m-%d'))
                    else:
                        st.metric("Generated", "Unknown")
            
            if selected_quarter and not quarter_analysis.empty:
                # Load comments data for raw data viewer (if available)
                quarter_comments = pd.DataFrame()
                if not comments_df.empty:
                    quarter_comments = comments_df[comments_df['QUARTER'] == selected_quarter]

                analysis_tab, trend_tab = st.tabs(["Narrative", "Trend Analysis"])

                with analysis_tab:
                    st.subheader(f"AI Analysis Results for {selected_quarter}")

                    analysis_text = quarter_analysis.iloc[0]['analysis_text']

                    if quarter_analysis.iloc[0]['status'] == 'success':
                        st.markdown(analysis_text)
                    else:
                        st.error("Analysis generation failed for this quarter")
                        st.code(analysis_text)

                    if not quarter_comments.empty:
                        with st.expander("View Raw Comments Data"):
                            st.markdown(f"**All {len(quarter_comments)} comments for {selected_quarter}:**")

                            display_df = quarter_comments.copy()
                            if 'generated_display' in display_df.columns:
                                display_df['Generated'] = display_df['generated_display'].dt.strftime('%Y-%m-%d %H:%M')
                            elif 'GENERATED_DATE' in display_df.columns:
                                display_df['Generated'] = pd.to_datetime(display_df['GENERATED_DATE'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
                            else:
                                display_df['Generated'] = ''

                            display_df = display_df[['TICKER', 'SECTOR', 'COMMENT', 'Generated']]

                            st.dataframe(
                                display_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "TICKER": st.column_config.TextColumn("Bank", width="small"),
                                    "SECTOR": st.column_config.TextColumn("Sector", width="small"),
                                    "COMMENT": st.column_config.TextColumn("Analysis Comment", width="large"),
                                    "Generated": st.column_config.TextColumn("Generated", width="small")
                                }
                            )

                with trend_tab:
                    st.subheader(f"Growth Contribution Waterfall — {selected_quarter}")
                    earnings_df = _load_earnings_quality()

                    if earnings_df.empty:
                        st.info("Earnings quality data not available for trend analysis.")
                    else:
                        period_col = 'Date_Quarter'
                        available_rows = earnings_df[earnings_df[period_col] == selected_quarter]

                        if available_rows.empty:
                            st.info("No earnings driver data found for this quarter.")
                        else:
                            if not quarter_comments.empty:
                                ticker_choices = sorted(quarter_comments['TICKER'].dropna().unique().tolist())
                            else:
                                ticker_choices = sorted(available_rows['TICKER'].dropna().unique().tolist())

                            if not ticker_choices:
                                st.info("No tickers available for trend analysis.")
                            else:
                                selected_ticker = st.selectbox(
                                    "Primary ticker",
                                    ticker_choices,
                                    index=0,
                                    help="Select the bank to visualise contribution drivers"
                                )

                                timeframe = st.radio(
                                    "Comparison timeframe",
                                    ["QoQ", "YoY", "T12M"],
                                    horizontal=True,
                                )

                                suffix_map = {"QoQ": "_QoQ", "YoY": "_YoY", "T12M": "_T12M"}
                                suffix = suffix_map.get(timeframe, "_QoQ")

                                row = available_rows[available_rows['TICKER'] == selected_ticker]

                                if row.empty:
                                    st.warning(f"No driver data for {selected_ticker} in {selected_quarter}.")
                                else:
                                    row = row.iloc[0]

                                    def get_metric(base: str):
                                        candidates = [f"{base}{suffix}", base]
                                        for candidate in candidates:
                                            if candidate in row.index and pd.notna(row[candidate]):
                                                return float(row[candidate])
                                        return None

                                    contributions = {
                                        "Top Line": get_metric('Top_Line_Impact'),
                                        "Cost Cutting": get_metric('Cost_Cutting_Impact'),
                                        "Non-Recurring": get_metric('Non_Recurring_Impact'),
                                    }
                                    total_impact = get_metric('Total_Impact')
                                    if total_impact is None:
                                        total_impact = sum(v for v in contributions.values() if v is not None)

                                    if all(v is None for v in contributions.values()):
                                        st.info("No impact metrics available for the selected ticker/timeframe.")
                                    else:
                                        waterfall = go.Figure(go.Waterfall(
                                            name="growth",
                                            orientation="v",
                                            measure=["relative", "relative", "relative", "total"],
                                            x=list(contributions.keys()) + ["Total"],
                                            y=[contributions.get(k, 0.0) or 0.0 for k in contributions.keys()] + [total_impact or 0.0],
                                            textposition="outside",
                                            connector={"line": {"color": "#7F7F7F"}}
                                        ))
                                        waterfall.update_layout(
                                            showlegend=False,
                                            yaxis_title="Contribution (pp)",
                                            waterfallgap=0.3,
                                        )
                                        st.plotly_chart(waterfall, use_container_width=True)

                                        detail_df = pd.DataFrame({
                                            "Component": list(contributions.keys()) + ["Total"],
                                            "Contribution": [round(contributions.get(k, 0.0) or 0.0, 2) for k in contributions.keys()] + [round(total_impact or 0.0, 2)]
                                        })
                                        st.dataframe(detail_df, hide_index=True, use_container_width=True)
            
            else:
                st.warning(f"No analysis found for quarter {selected_quarter}")
                
        except Exception as e:
            st.error(f"Error loading quarterly analysis: {e}")
            st.info("Please check that the analysis file exists and is accessible.")
    
    else:
        st.warning("No analysis data available")
        st.info("Please generate quarterly analysis first using the bulk analysis generator.")
        
if __name__ == "__main__":
    quarterly_analysis_page()
