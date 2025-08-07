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
        ["gpt-4-turbo-preview", "gpt-4", "gpt-3.5-turbo"],
        index=0
    )
    
    temperature = st.slider(
        "Response Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1
    )
    
    st.header("Available Data Sources")
    data_sources = st.session_state.discovery_agent.get_available_sources()
    for source in data_sources:
        st.text(f"- {source}")
    
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
            data_context = st.session_state.discovery_agent.find_relevant_data(
                query_analysis
            )
            
            if data_context['data_found']:
                with st.expander("Data Sources Found", expanded=False):
                    for source in data_context['sources']:
                        st.write(f"- {source['file']}: {source['description']}")
        
        with st.spinner("Generating response..."):
            try:
                client = get_openai_client()
                
                enhanced_prompt = f"""
                User Question: {user_question}
                
                Available Data Context:
                {json.dumps(data_context['summary'], indent=2)}
                
                Relevant Data Samples:
                {data_context['sample_data']}
                
                Please provide a comprehensive answer based on the data provided.
                Include specific numbers and trends where relevant.
                """
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a helpful banking data analyst assistant with access to real-time data."},
                        {"role": "user", "content": enhanced_prompt}
                    ],
                    temperature=temperature
                )
                
                answer = response.choices[0].message.content
                st.markdown(answer)
                
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": answer,
                    "data_context": data_context['summary']
                })
                
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