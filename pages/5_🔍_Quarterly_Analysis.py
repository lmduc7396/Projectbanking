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
from utilities import quarter_sort_key, sort_quarters
from Check_laptopOS import get_data_path, get_comments_file_path

# Page configuration
st.set_page_config(
    page_title="Quarterly Banking Analysis",
    page_icon="🔍",
    layout="wide"
)

def quarterly_analysis_page():
    st.title("🔍 Quarterly Banking Analysis")
    st.markdown("Comprehensive AI-powered analysis of banking comments for specific quarters")
    
    # Check if comments file exists using dynamic path
    comments_file = get_comments_file_path()
    comments_exist = os.path.exists(comments_file)
    
    if comments_exist:
        try:
            comments_df = pd.read_excel(comments_file)
            
            # Get available quarters and sort them properly
            available_quarters_raw = comments_df['QUARTER'].unique().tolist()
            available_quarters = sort_quarters(available_quarters_raw, reverse=True)
            
            # Quarter selection
            st.subheader("Select Quarter for Analysis")
            col1, col2 = st.columns([2, 1])
            
            with col1:
                selected_quarter = st.selectbox(
                    "Choose Quarter:",
                    available_quarters,
                    help="Select the quarter you want to analyze (sorted by most recent first)"
                )
            
            with col2:
                # Show number of comments for selected quarter
                quarter_comments = comments_df[comments_df['QUARTER'] == selected_quarter]
                st.metric("Comments Available", len(quarter_comments))
            
            if selected_quarter and len(quarter_comments) > 0:
                # Display quarter summary
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
                    # Show generation date range
                    if not quarter_comments.empty:
                        gen_dates = pd.to_datetime(quarter_comments['GENERATED_DATE'])
                        latest_gen = gen_dates.max().strftime('%Y-%m-%d')
                        st.metric("Latest Generation", latest_gen)
                
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
                
                # Analysis section
                st.subheader("AI Analysis")
                st.markdown("Generate comprehensive analysis using OpenAI ChatGPT to identify key trends, sentiment, and performance changes.")
                
                # Warning about API usage
                st.info("💡 **Note**: This analysis uses OpenAI API which may consume credits. The analysis will cover:\n"
                       "- Key market trends and changes\n"
                       "- Sentiment analysis across all banks\n" 
                       "- Performance changes by topic (NIM, Credit Growth, Asset Quality)")
                
                # Analysis button
                if st.button("🤖 Generate AI Analysis", type="primary", use_container_width=True):
                    with st.spinner("Analyzing comments with ChatGPT... This may take a moment."):
                        analysis_result = analyze_quarterly_comments(quarter_comments, selected_quarter)
                        if analysis_result:
                            st.success("✅ Analysis completed successfully!")
                            
                            # Display results in a single section
                            st.subheader(f"📊 AI Analysis Results for {selected_quarter}")
                            
                            # Display the complete analysis
                            st.markdown(analysis_result.get('full_analysis', 'No analysis available'))
                        else:
                            st.error("❌ Failed to generate analysis. Please check your OpenAI API key and connection.")
                
                st.markdown("---")
                
                # Show raw data option
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
                st.warning(f"⚠️ No comments found for quarter {selected_quarter}")
                st.info("Please generate comments for this quarter first using the bulk comment generator.")
                
        except Exception as e:
            st.error(f"Error loading quarterly analysis: {e}")
            st.info("Please check that the comments file exists and is accessible.")
    else:
        st.warning("📝 No comments data available")
        st.info("Please generate banking comments first before running quarterly analysis.")
        
        # Provide helpful information
        st.markdown("""
        ### How to get started:
        1. **Generate Comments**: Use the bulk comment generator to create banking analysis comments
        2. **Select Quarter**: Choose a quarter that has available comment data
        3. **Run Analysis**: Use AI to analyze all comments for comprehensive insights
        
        ### What you'll get:
        - **Market Overview**: Key trends and changes across the banking sector
        - **Sentiment Analysis**: Overall market sentiment and notable bank performances  
        - **Performance Insights**: Detailed analysis by topic (NIM, Credit Growth, Asset Quality)
        """)

def analyze_quarterly_comments(quarter_comments_df, quarter):
    """Analyze quarterly comments using ChatGPT"""
    try:
        # Get OpenAI API key from Streamlit secrets or environment variables
        api_key = None
        
        # Try Streamlit secrets first
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except (KeyError, FileNotFoundError):
            # Fallback to environment variables
            api_key = os.getenv("OPENAI_API_KEY")
        
        client = openai.OpenAI(api_key=api_key)
        
        # Prepare comments data for analysis
        comments_text = ""
        bank_count = 0
        for _, row in quarter_comments_df.iterrows():
            comments_text += f"\n\n**{row['TICKER']} ({row['SECTOR']}):**\n{row['COMMENT']}"
            bank_count += 1
        
        # Create the analysis prompt
        prompt = f"""
        You are a senior banking analyst with expertise in Vietnamese banking sector. Please analyze the following {bank_count} banking comments for {quarter} and provide a comprehensive analysis.

        BANKING COMMENTS FOR {quarter}:
        {comments_text}

        Please provide analysis in the following three sections:

        ## 1. KEY CHANGES SUMMARY
        Summarize the most significant trends and changes across all banks in this quarter. Focus on:
        - Overall banking sector performance and market conditions
        - Common themes and patterns across different bank types
        
        ## 2. SENTIMENT ANALYSIS & NOTABLE BANKS  
        Analyze the tone and sentiment of comments:
        - Overall sector sentiment (positive/neutral/negative)
        - Banks with most positive developments and specific reasons why
        - Banks with most concerning issues and specific reasons for concern

        ## 3. SIGNIFICANT BANK CHANGES BY TOPIC
        Identify which specific banks showed the most significant changes in each key area:

        **Net Interest Margin (NIM) & Profitability:**
        - Most improved: [Specific Bank Name] - [detailed reason based on comment data]
        - Most concerning: [Specific Bank Name] - [detailed reason based on comment data]

        **Credit Growth & Lending:**
        - Strongest growth: [Specific Bank Name] - [detailed reason based on comment data]
        - Weakest/declining: [Specific Bank Name] - [detailed reason based on comment data]

        **Asset Quality & Risk Management:**
        - Most improved: [Specific Bank Name] - [detailed reason based on comment data]
        - Most deteriorated: [Specific Bank Name] - [detailed reason based on comment data]

        **Instructions:**
        - Be specific with actual bank names (tickers) mentioned in the comments
        - Write in bullet points format, be punchy and concise
        - Provide clear, data-driven reasoning based on the comments provided
        - Use quantitative insights where available in the comments
        - Maintain professional banking analyst tone
        - If insufficient data for a category, clearly state "Insufficient data available"
        """

        # Send to OpenAI with improved parameters
        response = client.chat.completions.create(
            model="gpt-4.1",  # Use latest model
            messages=[
                {"role": "system", "content": "You are a senior banking analyst with deep expertise in financial analysis, market trends, and Vietnamese banking sector dynamics. Provide detailed, professional analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=5000,  # Increased for more detailed analysis
            top_p=0.9
        )
        
        # Get the full response without parsing
        full_response = response.choices[0].message.content
        
        # Return the complete analysis as one text
        return {'full_analysis': full_response}
        
    except Exception as e:
        st.error(f"Error calling OpenAI API: {str(e)}")
        return None

if __name__ == "__main__":
    quarterly_analysis_page()
