#%% Import libraries

import streamlit as st
import pandas as pd
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.openai_utils import get_openai_client
from AI_MPC.data_discovery import DataDiscoveryAgent
from AI_MPC.query_router import QueryRouter
from AI_MPC.qualitative_data_handler import QualitativeDataHandler
from AI_MPC.qualitative_query_parser import parse_qualitative_query
from AI_MPC.valuation_formatter import format_valuation_data, format_valuation_data_batch
from AI_MPC.response_generator import generate_quantitative_response, generate_qualitative_response
from AI_MPC.qualitative_data_collector import collect_qualitative_data, collect_qualitative_data_batch
from AI_MPC.parallel_data_fetcher import fetch_quantitative_data_parallel, fetch_qualitative_data_parallel

st.set_page_config(
    page_title="Duc GPT",
    layout="wide"
)

st.title("Duc GPT")
st.markdown("Only banking related questions are supported. Please refer to the rules below for guidance.")

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
    
    # Manual question type selector
    question_type = st.radio(
        "Question Type",
        ["Qualitative", "Quantitative"],
        help="Quantitative: Numbers and metrics from data tables\nQualitative: Analysis and commentary from AI-generated reports"
    )
    
    model = st.selectbox(
        "OpenAI Model",
        ["gpt-4o", "gpt-4o-mini"],
        index=0,
        help="gpt-4o: Most capable model (recommended)\ngpt-4o-mini: Faster and more cost-effective"
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

#%% Rules section
with st.expander("Rules for questions"):
    st.markdown("""
    1. Always include a timeframe (e.g: 1Q25, current, latest, 2024)
    2. For quantitative questions, specify the metrics (e.g: ROE, NIM, NPL)
    3. For qualitative questions, provide context (e.g: "What is the outlook for SOCB in 2024?")
    4. Use clear bank codes (e.g: ACB, VCB, SOCB) or sector names (e.g: "Private_1", "SOCB")
    5. If asking for comparisons, specify the banks or among which sectors (Best among Private_1)
    6. If no timeframe is specified, the system will assume the latest 4 quarters
    """)

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_question = st.chat_input("Ask anything about banking.")

if user_question:
    st.session_state.chat_history.append({"role": "user", "content": user_question})
    
    with st.chat_message("user"):
        st.markdown(user_question)
    
    with st.chat_message("assistant"):
        if question_type == "Quantitative":
            # Original quantitative flow
            with st.spinner("Duc is analyzing..."):
                query_analysis = st.session_state.query_router.analyze_query(user_question)
            
            with st.spinner("Duc is searching data..."):
                # Use parallel fetching for better performance
                parallel_results = fetch_quantitative_data_parallel(
                    query_analysis,
                    st.session_state.discovery_agent,
                    format_valuation_data_batch if len(query_analysis.get('tickers', [])) > 1 else format_valuation_data
                )
                
                data_result = parallel_results['data_result']
                valuation_data_text = parallel_results['valuation_data']
            
            with st.spinner("Duc is typing..."):
                try:
                    if data_result and data_result.get('data_found'):
                        client = get_openai_client()
                        
                        # Prepare the final prompt for debugging
                        final_prompt = f"""
Question: {user_question}

Data Table:
{data_result['data_table']}{valuation_data_text}

Instructions:
- Give a concise and punchy answer. If asked for data only provide the most relevant data.
- Convert decimals to percentages (0.02 = 2%, 0.134 = 13.4%)
- Round numbers appropriately (billions, millions, percentages to 1 decimal)
- Be direct and specific with bank names and numbers
"""
                        
                        answer = generate_quantitative_response(
                            user_question=user_question,
                            data_result=data_result,
                            valuation_data_text=valuation_data_text,
                            client=client,
                            model=model,
                            temperature=temperature
                        )
                        
                        st.markdown(answer)
                        
                        # Show debug information in expander
                        with st.expander("🔍 Debug: View Final OpenAI Prompt"):
                            st.text("System Message:")
                            st.code("You are a concise banking analyst. Give short, punchy answers with properly formatted numbers. Convert decimals to percentages, use billions/millions for large numbers. Maximum 2-3 sentences.")
                            st.text("User Prompt:")
                            st.code(final_prompt)
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": answer,
                            "data_context": data_result.get('summary', {})
                        })
                    else:
                        answer = "No data found to answer your question. Please try rephrasing or check if the data exists for the specified timeframe and banks."
                        st.warning(answer)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": answer,
                            "data_context": {"error": "No data found"}
                        })
                    
                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")
        
        else:  # Qualitative
            # New qualitative flow
            with st.spinner("Duc is analyzing..."):
                # Parse the query to extract tickers and timeframe
                client = get_openai_client()
                
                parsed = parse_qualitative_query(
                    user_question=user_question,
                    client=client,
                    latest_quarter=st.session_state.query_router.latest_quarter,
                    latest_4_quarters=st.session_state.query_router._get_latest_4_quarters()
                )
            
            with st.spinner("Duc is gathering insights..."):
                # Get qualitative data for all tickers mentioned
                tickers = parsed.get('tickers', [])
                timeframe = parsed.get('timeframe', [])
                has_sectors = parsed.get('has_sectors', False)
                
                # Use parallel fetching and batch processing
                parallel_results = fetch_qualitative_data_parallel(
                    tickers=tickers,
                    timeframe=timeframe,
                    qualitative_handler=st.session_state.qualitative_handler,
                    valuation_formatter=format_valuation_data_batch if len(tickers) > 1 else format_valuation_data,
                    need_valuation=parsed.get('valuation', False),
                    need_components=parsed.get('need_components', False)
                )
                
                qualitative_data = parallel_results['qualitative_data']
                valuation_data_text = parallel_results['valuation_data']
            
            with st.spinner("Duc is typing..."):
                try:
                    # Prepare the final prompt for debugging
                    final_qual_prompt = f"""
Question: {user_question}

Available Analysis and Commentary:
{qualitative_data}{valuation_data_text}

Instructions:
- Open with a concise conclusion of key findings, afterward followed with detailed analysis
- Give a concise and punchy answer, narrative driven like a financial analyst
- Use specific examples and data points from the analysis
- Convert decimals to percentages (0.02 = 2%, 0.134 = 13.4%)
- Be punchy and assertive, max 2 paragraphs.
- Reference specific quarters and banks when relevant
"""
                    
                    answer = generate_qualitative_response(
                        user_question=user_question,
                        qualitative_data=qualitative_data,
                        valuation_data_text=valuation_data_text,
                        client=client,
                        model=model,
                        temperature=temperature
                    )
                    
                    st.markdown(answer)
                    
                    # Show debug information in expander
                    with st.expander("🔍 Debug: View Final OpenAI Prompt"):
                        st.text("System Message:")
                        st.code("You are a senior banking analyst writing comprehensive sector analysis. Draw insights from the provided commentary and analysis to answer questions with depth and nuance.")
                        st.text("User Prompt:")
                        st.code(final_qual_prompt)
                        st.text("Parsed Query Info:")
                        st.json(parsed)
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "data_context": {"type": "qualitative", "tickers": tickers, "timeframe": timeframe}
                    })
                    
                except Exception as e:
                    st.error(f"Error generating qualitative response: {str(e)}")