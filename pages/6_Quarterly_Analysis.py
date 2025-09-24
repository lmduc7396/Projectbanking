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
from utilities.data_access import load_comments, load_quarterly_analysis


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
                
                # Display analysis results
                st.subheader(f"AI Analysis Results for {selected_quarter}")
                
                analysis_text = quarter_analysis.iloc[0]['analysis_text']
                
                if quarter_analysis.iloc[0]['status'] == 'success':
                    # Display the pre-generated analysis
                    st.markdown(analysis_text)
                else:
                    st.error("Analysis generation failed for this quarter")
                    st.code(analysis_text)  # Show error message
                
                # Show raw data option (if comments are available)
                if not quarter_comments.empty:
                    with st.expander("View Raw Comments Data"):
                        st.markdown(f"**All {len(quarter_comments)} comments for {selected_quarter}:**")
                        
                        # Create a display dataframe with better formatting
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
