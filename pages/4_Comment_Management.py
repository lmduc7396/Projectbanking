import streamlit as st
import pandas as pd
import os
import subprocess
import time
from datetime import datetime
import sys
import platform
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import utilities
from utilities.quarter_utils import quarter_to_numeric

# Define path functions
def get_data_path():
    return os.path.join(project_root, 'Data')

def get_comments_file_path():
    return os.path.join(get_data_path(), 'banking_comments.xlsx')

def show_comment_management():
    st.title("🤖 Banking Comment Management")
    st.markdown("Manage bulk generation and cached comments for banking analysis")
    
    # Check if comments file exists using dynamic path
    comments_file = get_comments_file_path()
    comments_exist = os.path.exists(comments_file)
    
    # Sidebar for navigation
    st.sidebar.subheader("Comment Management")
    tab = st.sidebar.radio("Choose Action", [
        "📊 View Cached Comments", 
        "📈 Statistics",
        "🔍 Quarterly Analysis"
    ])
    
    if tab == "📊 View Cached Comments":
        st.header("Cached Comments Overview")
        
        if comments_exist:
            try:
                comments_df = pd.read_excel(comments_file)
                
                # Display summary statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Comments", len(comments_df))
                with col2:
                    st.metric("Unique Banks", comments_df['TICKER'].nunique())
                with col3:
                    st.metric("Unique Quarters", comments_df['QUARTER'].nunique())
                with col4:
                    # Convert GENERATED_DATE to datetime for finding the latest
                    if not comments_df.empty:
                        comments_df_temp = comments_df.copy()
                        comments_df_temp['GENERATED_DATE'] = pd.to_datetime(comments_df_temp['GENERATED_DATE'])
                        latest_date = comments_df_temp['GENERATED_DATE'].max().strftime('%Y-%m-%d')
                    else:
                        latest_date = "N/A"
                    st.metric("Latest Update", latest_date)
                
                # Filter options
                st.subheader("Filter Comments")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    selected_ticker = st.selectbox(
                        "Select Bank:", 
                        ["All"] + sorted(comments_df['TICKER'].unique().tolist())
                    )
                
                with col2:
                    selected_sector = st.selectbox(
                        "Select Sector:", 
                        ["All"] + sorted(comments_df['SECTOR'].unique().tolist())
                    )
                
                with col3:
                    selected_quarter = st.selectbox(
                        "Select Quarter:", 
                        ["All"] + sorted(comments_df['QUARTER'].unique().tolist(), reverse=True)
                    )
                
                # Apply filters
                filtered_df = comments_df.copy()
                if selected_ticker != "All":
                    filtered_df = filtered_df[filtered_df['TICKER'] == selected_ticker]
                if selected_sector != "All":
                    filtered_df = filtered_df[filtered_df['SECTOR'] == selected_sector]
                if selected_quarter != "All":
                    filtered_df = filtered_df[filtered_df['QUARTER'] == selected_quarter]
                
                # Display filtered results
                st.subheader(f"Comments ({len(filtered_df)} results)")
                
                if not filtered_df.empty:
                    # Create a summary table
                    summary_df = filtered_df[['TICKER', 'SECTOR', 'QUARTER', 'GENERATED_DATE']].copy()
                    # Convert to datetime and format for display
                    summary_df['GENERATED_DATE'] = pd.to_datetime(summary_df['GENERATED_DATE']).dt.strftime('%Y-%m-%d %H:%M')
                    
                    # Display table with row selection
                    selected_rows = st.dataframe(
                        summary_df,
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row"
                    )
                    
                    # Display selected comment
                    if selected_rows and hasattr(selected_rows, 'selection') and selected_rows.selection.rows:
                        selected_idx = selected_rows.selection.rows[0]
                        selected_comment = filtered_df.iloc[selected_idx]
                        
                        st.subheader(f"Analysis: {selected_comment['TICKER']} - {selected_comment['QUARTER']}")
                        st.info(f"Generated: {selected_comment['GENERATED_DATE']} | Sector: {selected_comment['SECTOR']}")
                        
                        with st.container():
                            st.markdown(selected_comment['COMMENT'])
                
                else:
                    st.info("No comments found matching the selected filters.")
                    
            except Exception as e:
                st.error(f"Error loading comments: {e}")
        else:
            st.info("No cached comments found. Run bulk generation first.")
    
    elif tab == "📈 Statistics":
        st.header("Comment Statistics")
        
        if comments_exist:
            try:
                comments_df = pd.read_excel(comments_file)
                
                # Overall statistics
                st.subheader("Overall Statistics")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Comments", len(comments_df))
                with col2:
                    st.metric("Unique Banks", comments_df['TICKER'].nunique())
                with col3:
                    st.metric("Unique Quarters", comments_df['QUARTER'].nunique())
                with col4:
                    avg_length = comments_df['COMMENT'].str.len().mean()
                    st.metric("Avg Comment Length", f"{avg_length:.0f} chars")
                
                # Comments by sector
                st.subheader("Comments by Sector")
                sector_counts = comments_df['SECTOR'].value_counts()
                st.bar_chart(sector_counts)
                
                # Comments by quarter
                st.subheader("Comments by Quarter")
                quarter_counts = comments_df['QUARTER'].value_counts()
                st.bar_chart(quarter_counts)
                
                # Timeline
                st.subheader("Generation Timeline")
                comments_df_timeline = comments_df.copy()
                comments_df_timeline['GENERATED_DATE'] = pd.to_datetime(comments_df_timeline['GENERATED_DATE'])
                comments_df_timeline['Generation_Day'] = comments_df_timeline['GENERATED_DATE'].dt.date
                daily_counts = comments_df_timeline['Generation_Day'].value_counts().sort_index()
                st.line_chart(daily_counts)
                
                # Missing data analysis
                st.subheader("Coverage Analysis")
                
                # Load original data to check coverage
                data_path = get_data_path()
                df_quarter = pd.read_csv(os.path.join(data_path, "dfsectorquarter.csv"))
                all_banks = df_quarter[df_quarter['TICKER'].str.len() == 3]['TICKER'].unique()
                all_quarters = df_quarter['Date_Quarter'].unique()
                
                coverage_data = []
                for bank in all_banks:
                    bank_comments = comments_df[comments_df['TICKER'] == bank]
                    coverage_data.append({
                        'Bank': bank,
                        'Comments': len(bank_comments),
                        'Coverage': f"{len(bank_comments)}/{len(all_quarters)}"
                    })
                
                coverage_df = pd.DataFrame(coverage_data)
                st.dataframe(coverage_df, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"Error generating statistics: {e}")
        else:
            st.info("No comments data available for statistics.")
    
    elif tab == "🔍 Quarterly Analysis":
        st.header("Quarterly Banking Analysis")
        st.markdown("Analyze all banking comments for a specific quarter using AI")
        
        if comments_exist:
            try:
                comments_df = pd.read_excel(comments_file)
                
                # Get available quarters
                available_quarters = sorted(comments_df['QUARTER'].unique().tolist(), reverse=True)
                
                # Quarter selection
                st.subheader("Select Quarter for Analysis")
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    selected_quarter = st.selectbox(
                        "Choose Quarter:",
                        available_quarters,
                        help="Select the quarter you want to analyze"
                    )
                
                with col2:
                    # Show number of comments for selected quarter
                    quarter_comments = comments_df[comments_df['QUARTER'] == selected_quarter]
                    st.metric("Comments Available", len(quarter_comments))
                
                if selected_quarter and len(quarter_comments) > 0:
                    # Display quarter summary
                    st.subheader(f"Quarter {selected_quarter} Overview")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Banks", quarter_comments['TICKER'].nunique())
                    with col2:
                        sectors = quarter_comments['SECTOR'].nunique()
                        st.metric("Sectors Covered", sectors)
                    with col3:
                        avg_length = quarter_comments['COMMENT'].str.len().mean()
                        st.metric("Avg Comment Length", f"{avg_length:.0f} chars")
                    
                    # Show sector breakdown
                    sector_breakdown = quarter_comments['SECTOR'].value_counts()
                    st.write("**Sector Breakdown:**")
                    st.write(sector_breakdown.to_dict())
                    
                    # Analysis button
                    if st.button("🤖 Generate AI Analysis", type="primary"):
                        if st.session_state.get('confirm_analysis', False):
                            with st.spinner("Analyzing comments with ChatGPT..."):
                                analysis_result = analyze_quarterly_comments(quarter_comments, selected_quarter)
                                if analysis_result:
                                    st.success("✅ Analysis completed!")
                                    
                                    # Display results
                                    st.subheader(f"AI Analysis for {selected_quarter}")
                                    
                                    # Create tabs for different analysis sections
                                    analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs([
                                        "📋 Key Changes Summary", 
                                        "😊 Sentiment Analysis", 
                                        "🏦 Bank Performance Changes"
                                    ])
                                    
                                    with analysis_tab1:
                                        st.markdown("### Key Changes Across All Banks")
                                        st.markdown(analysis_result.get('summary', 'No summary available'))
                                    
                                    with analysis_tab2:
                                        st.markdown("### Sentiment Analysis & Notable Banks")
                                        st.markdown(analysis_result.get('sentiment', 'No sentiment analysis available'))
                                    
                                    with analysis_tab3:
                                        st.markdown("### Significant Bank Changes by Topic")
                                        st.markdown(analysis_result.get('bank_changes', 'No bank change analysis available'))
                                    
                                    # Option to download analysis
                                    if st.button("📥 Download Analysis Report"):
                                        download_analysis_report(analysis_result, selected_quarter)
                                else:
                                    st.error("❌ Failed to generate analysis. Please check your OpenAI API key and try again.")
                        else:
                            st.session_state['confirm_analysis'] = True
                            st.warning("⚠️ This will use OpenAI API credits. Click again to confirm.")
                    
                    # Reset confirmation
                    if st.button("Cancel Analysis"):
                        st.session_state['confirm_analysis'] = False
                        st.info("Analysis cancelled")
                    
                    # Show raw data option
                    with st.expander("📄 View Raw Comments Data"):
                        st.dataframe(
                            quarter_comments[['TICKER', 'SECTOR', 'COMMENT']],
                            use_container_width=True,
                            hide_index=True
                        )
                
                else:
                    st.warning(f"No comments found for quarter {selected_quarter}")
                    
            except Exception as e:
                st.error(f"Error loading quarterly analysis: {e}")
        else:
            st.info("No comments data available. Please generate comments first.")

def analyze_quarterly_comments(quarter_comments_df, quarter):
    """Analyze quarterly comments using ChatGPT"""
    try:
        # Get OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("OPENAI_API_KEY not found in environment variables")
            return None
        
        client = openai.OpenAI(api_key=api_key)
        
        # Prepare comments data for analysis
        comments_text = ""
        for _, row in quarter_comments_df.iterrows():
            comments_text += f"\n\n**{row['TICKER']} ({row['SECTOR']}):**\n{row['COMMENT']}"
        
        # Create the analysis prompt
        prompt = f"""
        You are a senior banking analyst. Please analyze the following banking comments for Q{quarter} and provide a comprehensive analysis.

        BANKING COMMENTS FOR {quarter}:
        {comments_text}

        Please provide analysis in the following three sections:

        ## 1. KEY CHANGES SUMMARY
        Summarize the most significant trends and changes across all banks in this quarter. Focus on:
        - Overall market conditions and banking environment
        - Common themes and patterns across the sector
        - Major regulatory or economic impacts
        - Key performance indicators trends

        ## 2. SENTIMENT ANALYSIS & NOTABLE BANKS  
        Analyze the tone and sentiment of comments:
        - Overall sentiment (positive/neutral/negative) with percentages
        - List banks with most positive outlook and why
        - List banks with most concerning developments and why
        - Rate overall market confidence level (1-10)

        ## 3. SIGNIFICANT BANK CHANGES BY TOPIC
        Identify which banks showed the most significant changes in each area:

        **Net Interest Margin (NIM):**
        - Most improved: [Bank] - [reason]
        - Most concerning: [Bank] - [reason]

        **Credit Growth:**
        - Strongest growth: [Bank] - [reason] 
        - Weakest/declining: [Bank] - [reason]

        **Asset Quality:**
        - Most improved: [Bank] - [reason]
        - Most deteriorated: [Bank] - [reason]

        Please be specific with bank names and provide clear reasoning based on the comments provided.
        """

        # Send to OpenAI
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a senior banking analyst with expertise in financial analysis and market trends."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        
        # Parse the response into sections
        full_response = response.choices[0].message.content
        
        # Split response into sections (basic parsing)
        sections = full_response.split("## ")
        
        result = {}
        for section in sections:
            if "KEY CHANGES SUMMARY" in section:
                result['summary'] = section.replace("1. KEY CHANGES SUMMARY", "").strip()
            elif "SENTIMENT ANALYSIS" in section:
                result['sentiment'] = section.replace("2. SENTIMENT ANALYSIS & NOTABLE BANKS", "").strip()
            elif "SIGNIFICANT BANK CHANGES" in section:
                result['bank_changes'] = section.replace("3. SIGNIFICANT BANK CHANGES BY TOPIC", "").strip()
        
        # If parsing fails, return the full response
        if not result:
            result = {
                'summary': full_response,
                'sentiment': "Analysis completed - see summary section",
                'bank_changes': "Analysis completed - see summary section"
            }
        
        return result
        
    except Exception as e:
        st.error(f"Error calling OpenAI API: {str(e)}")
        return None

def download_analysis_report(analysis_result, quarter):
    """Create a downloadable analysis report"""
    try:
        report_content = f"""
# Banking Analysis Report - {quarter}
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Key Changes Summary
{analysis_result.get('summary', 'No summary available')}

## Sentiment Analysis & Notable Banks
{analysis_result.get('sentiment', 'No sentiment analysis available')}

## Significant Bank Changes by Topic
{analysis_result.get('bank_changes', 'No bank change analysis available')}

---
Report generated by Banking Comment Management System
        """
        
        st.download_button(
            label="📥 Download Report as Text",
            data=report_content,
            file_name=f"banking_analysis_{quarter}_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )
        
    except Exception as e:
        st.error(f"Error creating download: {e}")
            
if __name__ == "__main__":
    show_comment_management()
