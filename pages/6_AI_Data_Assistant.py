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
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

#%% Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    
    model = st.selectbox(
        "OpenAI Model",
        ["gpt-4o", "gpt-3.5-turbo"],
        index=0
    )
    
    temperature = st.slider(
        "Response Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
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