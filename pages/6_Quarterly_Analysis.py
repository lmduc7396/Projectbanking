import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Quarterly Banking Analysis",
    page_icon="Analysis",
    layout="wide"
)

import pandas as pd
import os
import sys
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
from utilities.quarter_utils import sort_quarters

try:
    from utilities.db import read_sql
    SQL_IMPORT_ERROR = None
except Exception as exc:  # pymssql or connection string issues
    read_sql = None  # type: ignore
    SQL_IMPORT_ERROR = exc


QUARTERLY_ANALYSIS_QUERY = """
    SELECT quarter,
           analysis_text,
           bank_count,
           generated_date,
           status
    FROM dbo.QuarterlyAnalysis
"""

COMMENTS_QUERY = """
    SELECT TICKER,
           SECTOR,
           QUARTER,
           COMMENT,
           GENERATED_DATE,
           GENERATED_AT
    FROM dbo.Banking_Comments
"""


def _normalize_generated_columns(df: pd.DataFrame, column_candidates: list[str]) -> pd.Series:
    generated = pd.Series(pd.NaT, index=df.index)
    for col in column_candidates:
        if col in df.columns:
            generated = generated.fillna(pd.to_datetime(df[col], errors='coerce'))
    return generated


@st.cache_data(ttl=1800)
def _fetch_quarterly_analysis_sql() -> pd.DataFrame:
    if read_sql is None:
        raise RuntimeError("SQL access is not available: pymssql driver missing or connection string unset")

    df = read_sql(QUARTERLY_ANALYSIS_QUERY, db="target")
    if df.empty:
        return df

    df = df.rename(columns=str.lower)
    df['generated_date'] = _normalize_generated_columns(df, ['generated_date', 'generated_at'])

    if 'bank_count' not in df.columns:
        df['bank_count'] = pd.NA
    if 'status' not in df.columns:
        df['status'] = 'success'

    expected_cols = ['quarter', 'analysis_text', 'bank_count', 'generated_date', 'status']
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[expected_cols]
    df['quarter'] = df['quarter'].astype(str)
    return df


@st.cache_data(ttl=600)
def _fetch_comments_sql() -> pd.DataFrame:
    if read_sql is None:
        raise RuntimeError("SQL access is not available: pymssql driver missing or connection string unset")

    df = read_sql(COMMENTS_QUERY, db="target")
    if df.empty:
        return df

    df = df.rename(columns={col: col.lower() for col in df.columns})
    df['generated_date'] = _normalize_generated_columns(df, ['generated_date', 'generated_at'])
    df['generated_display'] = df['generated_date']

    expected_cols = ['ticker', 'sector', 'quarter', 'comment', 'generated_date', 'generated_display']
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA

    df['quarter'] = df['quarter'].astype(str)
    return df


def quarterly_analysis_page():
    st.title("Quarterly Banking Analysis")
    st.markdown("Comprehensive AI-powered analysis of banking comments for specific quarters")
    
    if read_sql is None:
        st.error("SQL access is unavailable. Please install the SQL driver and set the TARGET_DB connection string.")
        if SQL_IMPORT_ERROR:
            st.caption(f"Driver import error: {SQL_IMPORT_ERROR}")
        return

    try:
        analysis_df = _fetch_quarterly_analysis_sql()
    except Exception as exc:
        st.error("Unable to load quarterly analysis from the SQL database.")
        st.caption(str(exc))
        return

    try:
        comments_df = _fetch_comments_sql()
    except Exception as exc:
        st.warning("Banking comments could not be loaded from SQL; continuing without comments.")
        st.caption(str(exc))
        comments_df = pd.DataFrame()

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
                    quarter_comments = comments_df[comments_df['quarter'] == selected_quarter]

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
                            display_df['generated'] = display_df['generated_display'].dt.strftime('%Y-%m-%d %H:%M')
                        else:
                            display_df['generated'] = ''

                        display_df = display_df[['ticker', 'sector', 'comment', 'generated']]

                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "ticker": st.column_config.TextColumn("Bank", width="small"),
                                "sector": st.column_config.TextColumn("Sector", width="small"),
                                "comment": st.column_config.TextColumn("Analysis Comment", width="large"),
                                "generated": st.column_config.TextColumn("Generated", width="small")
                            }
                        )
            
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
