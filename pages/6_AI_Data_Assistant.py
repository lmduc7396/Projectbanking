#%% Import libraries

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.openai_utils import get_openai_client
from utilities.data_discovery import DataDiscoveryAgent
from utilities.query_router import QueryRouter
from utilities.qualitative_data_handler import QualitativeDataHandler

st.set_page_config(
    page_title="AI Data Assistant",
    layout="wide"
)

st.title("AI Data Assistant")
st.markdown("Ask questions about banking data. AI finds relevant data and provides answers.")

#%% Initialize components
if 'discovery_agent' not in st.session_state:
    st.session_state.discovery_agent = DataDiscoveryAgent()
if 'query_router' not in st.session_state:
    st.session_state.query_router = QueryRouter()
if 'qualitative_handler' not in st.session_state:
    st.session_state.qualitative_handler = QualitativeDataHandler()
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

#%% Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    
    # Question type selector
    question_type = st.radio(
        "Question Type",
        ["Quantitative", "Qualitative"],
        help="Quantitative: Numbers and metrics from data tables\nQualitative: Analysis and commentary from AI-generated reports"
    )
    
    model = st.selectbox(
        "OpenAI Model",
        ["gpt-4o", "gpt-3.5-turbo"],
        index=0
    )
    
    temperature = st.slider(
        "Response Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.2 if question_type == "Quantitative" else 0.5,
        step=0.1
    )
    
    st.header("Available Data Sources")
    st.text("- dfsectorquarter.csv (Quarterly data)")
    st.text("- dfsectoryear.csv (Yearly data)")
    st.text("- Key_items.xlsx (Metric mappings)")
    
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

#%% Main chat interface
st.header("Ask Your Question")

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "data_context" in message:
            with st.expander("View Data Context"):
                st.json(message["data_context"])

user_question = st.chat_input("Ask anything about your banking data...")

if user_question:
    st.session_state.chat_history.append({"role": "user", "content": user_question})
    
    with st.chat_message("user"):
        st.markdown(user_question)
    
    with st.chat_message("assistant"):
        if question_type == "Quantitative":
            # Original quantitative flow
            with st.spinner("Analyzing your question..."):
                query_analysis = st.session_state.query_router.analyze_query(user_question)
                
                with st.expander("Query Analysis", expanded=False):
                    st.json(query_analysis)
            
            with st.spinner("Discovering relevant data..."):
                data_result = st.session_state.discovery_agent.find_relevant_data(
                    query_analysis
                )
                
                if data_result['data_found']:
                    st.success(f"Found {data_result['row_count']} rows with {data_result['column_count']} columns")
            
            st.info("Debug: Data Being Sent to OpenAI")
            with st.expander("Data Table and Context (Debug)", expanded=True):
                st.subheader("1. Data Summary:")
                st.json(data_result.get('summary', {}))
                
                st.subheader("2. Actual Data Table:")
                if data_result.get('data_table'):
                    st.code(data_result['data_table'], language='text')
                    
                    # Try to display as dataframe
                    try:
                        import io
                        df_display = pd.read_csv(io.StringIO(data_result['data_table']), sep=r'\s\s+', engine='python')
                        st.dataframe(df_display)
                    except:
                        pass
                else:
                    st.warning("No data found matching the query")
            
            with st.spinner("Generating response..."):
                try:
                    if data_result['data_found']:
                        client = get_openai_client()
                        
                        # Create prompt with question and data
                        enhanced_prompt = f"""
Question: {user_question}

Data Table:
{data_result['data_table']}

Instructions:
- Give a concise and punchy answer. If asked for data only provide the most relevant data.
- Convert decimals to percentages (0.02 = 2%, 0.134 = 13.4%)
- Round numbers appropriately (billions, millions, percentages to 1 decimal)
- Highlight only the most important findings
- Be direct and specific with bank names and numbers
"""
                        
                        st.info("Debug: Prompt Being Sent to OpenAI")
                        with st.expander("Full Prompt to OpenAI (Debug)", expanded=True):
                            st.code(enhanced_prompt, language='text')
                        
                        response = client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": "You are a concise banking analyst. Give short, punchy answers with properly formatted numbers. Convert decimals to percentages, use billions/millions for large numbers. Maximum 2-3 sentences."},
                                {"role": "user", "content": enhanced_prompt}
                            ],
                            temperature=temperature
                        )
                        
                        answer = response.choices[0].message.content
                        
                        st.success("OpenAI Response:")
                        st.markdown(answer)
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": answer,
                            "data_context": data_result.get('summary', {})
                        })
                    else:
                        st.warning("No data found to answer your question. Please try rephrasing or check if the data exists for the specified timeframe and banks.")
                    
                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")
        
        else:  # Qualitative
            # New qualitative flow
            with st.spinner("Analyzing your qualitative question..."):
                # First parse the query to extract tickers and timeframe
                client = get_openai_client()
                
                parse_prompt = f"""
Analyze this qualitative banking question and extract:
1. TICKER: The bank code (3 letters like ACB, VCB) or sector (SOCB, Private_1, etc)
2. TIMEFRAME: List of quarters mentioned (e.g., ["1Q24", "2Q24"])
   - If "current" or "latest", return ["{st.session_state.query_router.latest_quarter}"]
   - If no timeframe, return latest 4 quarters: {st.session_state.query_router._get_latest_4_quarters()}

Question: "{user_question}"

Return JSON: {{"ticker": "...", "timeframe": [...], "is_sector": true/false}}
"""
                
                parse_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Extract structured data from banking questions."},
                        {"role": "user", "content": parse_prompt}
                    ],
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                
                import json
                parsed = json.loads(parse_response.choices[0].message.content)
                
                with st.expander("Qualitative Query Analysis", expanded=False):
                    st.json(parsed)
            
            with st.spinner("Retrieving qualitative data..."):
                # Get qualitative data based on ticker type
                ticker = parsed.get('ticker', '')
                timeframe = parsed.get('timeframe', [])
                is_sector = parsed.get('is_sector', False)
                
                qualitative_data = st.session_state.qualitative_handler.format_qualitative_data(
                    ticker=ticker,
                    timeframe=timeframe,
                    is_sector=is_sector
                )
                
                with st.expander("Qualitative Data Retrieved", expanded=True):
                    st.text(qualitative_data[:2000] + "..." if len(qualitative_data) > 2000 else qualitative_data)
            
            with st.spinner("Generating qualitative analysis..."):
                try:
                    # Create qualitative prompt
                    qual_prompt = f"""
Question: {user_question}

Available Analysis and Commentary:
{qualitative_data}

Instructions:
- Provide a narrative response drawing from the available analysis
- Write fluently and naturally, like a banking analyst report
- Focus on key themes, trends, and insights
- Use specific examples and data points from the analysis
- Be comprehensive but clear, 2-4 paragraphs as needed
- Reference specific quarters and banks when relevant
"""
                    
                    with st.expander("Qualitative Prompt to OpenAI", expanded=False):
                        st.code(qual_prompt[:1000] + "...", language='text')
                    
                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": "You are a senior banking analyst writing comprehensive sector analysis. Draw insights from the provided commentary and analysis to answer questions with depth and nuance."},
                            {"role": "user", "content": qual_prompt}
                        ],
                        temperature=temperature
                    )
                    
                    answer = response.choices[0].message.content
                    
                    st.success("Qualitative Analysis:")
                    st.markdown(answer)
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "data_context": {"type": "qualitative", "ticker": ticker, "timeframe": timeframe}
                    })
                    
                except Exception as e:
                    st.error(f"Error generating qualitative response: {str(e)}")

#%% Examples and export
with st.expander("Example Questions"):
    st.markdown("""
    Try asking:
    - "What's the trend in loan growth for VCB in 2024?"
    - "Compare NPL ratios across all state-owned banks"
    - "Which banks have the highest ROE this quarter?"
    - "Show me the capital adequacy trends for private banks"
    - "What are the key risks in the banking sector?"
    - "Analyze provision coverage for banks with high NPLs"
    """)

st.divider()
col1, col2 = st.columns(2)

with col1:
    if st.button("Export Chat History"):
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "messages": st.session_state.chat_history
        }
        st.download_button(
            label="Download JSON",
            data=json.dumps(export_data, indent=2),
            file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

with col2:
    if st.button("Analyze Data Quality"):
        with st.spinner("Analyzing data quality..."):
            quality_report = st.session_state.discovery_agent.analyze_data_quality()
            st.json(quality_report)