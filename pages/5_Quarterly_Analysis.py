import streamlit as st
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

# Import utilities
from utilities.quarter_utils import quarter_sort_key, sort_quarters

# Define path functions
def get_data_path():
    return os.path.join(project_root, 'Data')

def get_comments_file_path():
    return os.path.join(get_data_path(), 'banking_comments.xlsx')

# Page configuration
st.set_page_config(
    page_title="Quarterly Banking Analysis",
    page_icon="🔍",
    layout="wide"
)

def quarterly_analysis_page():
    st.title("🔍 Quarterly Banking Analysis")
    st.markdown("Comprehensive AI-powered analysis of banking comments for specific quarters")
    
    # Check if analysis results file exists
    analysis_file = os.path.join(get_data_path(), "quarterly_analysis_results.xlsx")
    analysis_exists = os.path.exists(analysis_file)
    
    # Check if comments file exists using dynamic path
    comments_file = get_comments_file_path()
    comments_exist = os.path.exists(comments_file)
    
    if analysis_exists:
        try:
            # Load pre-generated analysis results
            analysis_df = pd.read_excel(analysis_file)
            
            # Get available quarters from analysis results
            available_quarters_raw = analysis_df['quarter'].unique().tolist()
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
            
            with col2:
                # Show analysis status
                quarter_analysis = analysis_df[analysis_df['quarter'] == selected_quarter]
                if not quarter_analysis.empty:
                    status = quarter_analysis.iloc[0]['status']
                    if status == 'success':
                        st.success("✅ Analysis Available")
                    else:
                        st.error("❌ Analysis Error")
            
            with col3:
                # Show generation date
                if not quarter_analysis.empty:
                    gen_date = pd.to_datetime(quarter_analysis.iloc[0]['generated_date'])
                    st.metric("Generated", gen_date.strftime('%Y-%m-%d'))
            
            if selected_quarter and not quarter_analysis.empty:
                # Load comments data for overview (if available)
                quarter_comments = pd.DataFrame()
                if comments_exist:
                    try:
                        comments_df = pd.read_excel(comments_file)
                        quarter_comments = comments_df[comments_df['QUARTER'] == selected_quarter]
                    except:
                        pass
                
                # Display quarter summary if comments data is available
                if not quarter_comments.empty:
                    st.subheader(f"Quarter {selected_quarter} Overview")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Banks", quarter_comments['TICKER'].nunique())
                    with col2:
                        sectors = quarter_comments['SECTOR'].nunique()
                        st.metric("Sectors Covered", sectors)
                    with col3:
                        avg_length = quarter_comments['COMMENT'].str.len().mean()
                        st.metric("Avg Comment Length", f"{avg_length:.0f} chars")
                    with col4:
                        # Show bank count from analysis
                        bank_count = quarter_analysis.iloc[0]['bank_count']
                        st.metric("Banks Analyzed", bank_count)
                    
                    # Show sector breakdown
                    st.subheader("Sector Distribution")
                    sector_breakdown = quarter_comments['SECTOR'].value_counts()
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.bar_chart(sector_breakdown)
                    
                    with col2:
                        st.write("**Sector Breakdown:**")
                        for sector, count in sector_breakdown.items():
                            percentage = (count / len(quarter_comments)) * 100
                            st.write(f"• **{sector}**: {count} banks ({percentage:.1f}%)")
                
                st.markdown("---")
                
                # Display analysis results
                st.subheader(f"📊 AI Analysis Results for {selected_quarter}")
                
                analysis_text = quarter_analysis.iloc[0]['analysis_text']
                
                if quarter_analysis.iloc[0]['status'] == 'success':
                    # Display the pre-generated analysis
                    st.markdown(analysis_text)
                else:
                    st.error("❌ Analysis generation failed for this quarter")
                    st.code(analysis_text)  # Show error message
                
                st.markdown("---")
                
                # Show raw data option (if comments are available)
                if not quarter_comments.empty:
                    with st.expander("📄 View Raw Comments Data"):
                        st.markdown(f"**All {len(quarter_comments)} comments for {selected_quarter}:**")
                        
                        # Create a display dataframe with better formatting
                        display_df = quarter_comments[['TICKER', 'SECTOR', 'COMMENT', 'GENERATED_DATE']].copy()
                        display_df['GENERATED_DATE'] = pd.to_datetime(display_df['GENERATED_DATE']).dt.strftime('%Y-%m-%d %H:%M')
                        
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "TICKER": st.column_config.TextColumn("Bank", width="small"),
                                "SECTOR": st.column_config.TextColumn("Sector", width="small"),
                                "COMMENT": st.column_config.TextColumn("Analysis Comment", width="large"),
                                "GENERATED_DATE": st.column_config.TextColumn("Generated", width="small")
                            }
                        )
            
            else:
                st.warning(f"⚠️ No analysis found for quarter {selected_quarter}")
                
        except Exception as e:
            st.error(f"Error loading quarterly analysis: {e}")
            st.info("Please check that the analysis file exists and is accessible.")
    
    else:
        st.warning("📝 No analysis data available")
        st.info("Please generate quarterly analysis first using the bulk analysis generator.")
        
if __name__ == "__main__":
    quarterly_analysis_page()
