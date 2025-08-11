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

#%% Function to auto-detect question type
def auto_detect_question_type(question: str) -> str:
    """
    Automatically detect if a question is Quantitative or Qualitative using OpenAI
    """
    try:
        client = get_openai_client()
        
        prompt = """
        Classify this banking question as either 'Quantitative' or 'Qualitative':
        
        Quantitative questions ask for:
        - SPECIFIC single metrics or data points (ROE, NIM, NPL, loan amount, etc.)
        - Pure numerical values with no analysis needed
        - Exact values like "What is the ROE value?", "Show me the NIM number"
        - Questions explicitly asking for calculations or specific percentages
        - Raw data without interpretation
        
        Qualitative questions ask for:
        - Comparisons between banks (even if numbers are involved, comparisons need analysis)
        - Analysis, commentary, insights, or narrative explanations
        - Performance discussions, results interpretation, or assessments
        - Questions with "compare", "versus", "vs", "better", "worse"
        - Questions starting with "why", "how is", "what's the outlook"
        - Explanations of causes, implications, or interpretations
        - General performance questions like "How is X performing?"
        - Questions about results, trends, or relative performance
        
        IMPORTANT: Questions with "compare" or asking about "results" are usually Qualitative 
        because they want analysis and insights, not just raw numbers.
        
        Examples:
        Quantitative: "What is ACB's ROE value?", "Show NIM number for VCB", "Calculate loan amount"
        Qualitative: "Compare ACB and VPB", "How are ACB's results?", "ACB vs VPB performance", "Which bank is better?"
        
        Question: "{}"
        
        Return ONLY one word: either 'Quantitative' or 'Qualitative'
        """.format(question)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Use faster model for classification
            messages=[
                {"role": "system", "content": "You are a question classifier. Return only 'Quantitative' or 'Qualitative'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip()
        
        # Validate response
        if result in ["Quantitative", "Qualitative"]:
            # Double-check: if question contains comparison keywords, lean towards Qualitative
            comparison_keywords = ['compare', 'versus', ' vs ', ' vs.', 'better', 'worse', 'comparison']
            question_lower = question.lower()
            if any(keyword in question_lower for keyword in comparison_keywords):
                # Override to Qualitative for comparison questions unless it's clearly asking for specific metrics
                metric_keywords = ['what is the', 'show me the', 'calculate the']
                if not any(metric in question_lower for metric in metric_keywords):
                    return "Qualitative"
            return result
        else:
            # Default to Quantitative if unclear
            return "Quantitative"
            
    except Exception as e:
        st.warning(f"Could not auto-detect question type: {e}. Defaulting to Quantitative.")
        return "Quantitative"

#%% Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    
    # Auto-detection settings
    auto_detect = st.checkbox(
        "Auto-detect question type",
        value=True,
        help="Automatically determine if your question is Quantitative or Qualitative"
    )
    
    if not auto_detect:
        # Manual question type selector
        question_type = st.radio(
            "Question Type",
            ["Quantitative", "Qualitative"],
            help="Quantitative: Numbers and metrics from data tables\nQualitative: Analysis and commentary from AI-generated reports"
        )
    else:
        question_type = None  # Will be determined automatically
    
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
        if "data_context" in message:
            with st.expander("View Data Context"):
                st.json(message["data_context"])

user_question = st.chat_input("Ask anything about your banking data...")

if user_question:
    st.session_state.chat_history.append({"role": "user", "content": user_question})
    
    with st.chat_message("user"):
        st.markdown(user_question)
    
    with st.chat_message("assistant"):
        # Auto-detect question type if enabled
        if auto_detect and question_type is None:
            with st.spinner("Detecting question type..."):
                detected_type = auto_detect_question_type(user_question)
                
                # Show detected type with override option
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.info(f"Detected as: **{detected_type}** question")
                with col2:
                    if st.button("Change type", key=f"override_{len(st.session_state.chat_history)}"):
                        # Toggle the type
                        detected_type = "Qualitative" if detected_type == "Quantitative" else "Quantitative"
                        st.success(f"Changed to: **{detected_type}**")
                
                question_type = detected_type
        
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
            with st.expander("Data Table and Context (Debug)", expanded=False):
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
                        with st.expander("Full Prompt to OpenAI (Debug)", expanded=False):
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
1. TICKERS: List ALL bank codes or sector names mentioned. Valid sectors are:
   - Sector (overall banking sector)
   - SOCB (state-owned commercial banks)
   - Private_1, Private_2, Private_3 (private bank groups)
   IMPORTANT: 
   - Return ALL tickers mentioned in the question as a list
   - Preserve the exact format with underscore for Private sectors (e.g., "Private_1" not "Private 1")
   
2. TIMEFRAME: List of quarters mentioned (e.g., ["1Q24", "2Q24"])
   - If "current" or "latest", return ["{st.session_state.query_router.latest_quarter}"]
   - If no timeframe, return latest 4 quarters: {st.session_state.query_router._get_latest_4_quarters()}

Question: "{user_question}"

Return JSON: {{"tickers": [...], "timeframe": [...], "has_sectors": true/false}}

Examples:
- "Compare Private_1 and Private_2 in 2Q25" → {{"tickers": ["Private_1", "Private_2"], "timeframe": ["2Q25"], "has_sectors": true}}
- "Private_1 in 2Q25" → {{"tickers": ["Private_1"], "timeframe": ["2Q25"], "has_sectors": true}}
- "Compare ACB, VCB and TCB performance" → {{"tickers": ["ACB", "VCB", "TCB"], "timeframe": {st.session_state.query_router._get_latest_4_quarters()}, "has_sectors": false}}
- "SOCB vs Private_1 in current quarter" → {{"tickers": ["SOCB", "Private_1"], "timeframe": ["{st.session_state.query_router.latest_quarter}"], "has_sectors": true}}
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
                
                # Ensure tickers preserve underscores for Private sectors
                tickers = parsed.get('tickers', [])
                normalized_tickers = []
                for ticker in tickers:
                    if ticker.startswith('Private'):
                        # Normalize Private sector format
                        ticker_parts = ticker.replace(' ', '_').split('_')
                        if len(ticker_parts) >= 2 and ticker_parts[1].isdigit():
                            normalized_tickers.append(f"Private_{ticker_parts[1]}")
                        else:
                            normalized_tickers.append(ticker)
                    else:
                        normalized_tickers.append(ticker)
                parsed['tickers'] = normalized_tickers
                
                with st.expander("Qualitative Query Analysis", expanded=False):
                    st.json(parsed)
                    st.info(f"Parsed tickers: {parsed.get('tickers', [])} | Timeframe: {parsed.get('timeframe', [])}")
            
            with st.spinner("Retrieving qualitative data..."):
                # Get qualitative data for all tickers mentioned
                tickers = parsed.get('tickers', [])
                timeframe = parsed.get('timeframe', [])
                has_sectors = parsed.get('has_sectors', False)
                
                # Collect data for all tickers
                all_qualitative_data = []
                for ticker in tickers:
                    # Determine if this specific ticker is a sector
                    is_sector = ticker in ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
                    
                    ticker_data = st.session_state.qualitative_handler.format_qualitative_data(
                        ticker=ticker,
                        timeframe=timeframe,
                        is_sector=is_sector
                    )
                    all_qualitative_data.append(ticker_data)
                
                # Combine all data
                qualitative_data = "\n\n".join(all_qualitative_data)
                
                with st.expander("Qualitative Data Retrieved", expanded=False):
                    st.text(qualitative_data[:3000] + "..." if len(qualitative_data) > 3000 else qualitative_data)
            
            with st.spinner("Generating qualitative analysis..."):
                try:
                    # Create qualitative prompt
                    qual_prompt = f"""
Question: {user_question}

Available Analysis and Commentary:
{qualitative_data}

Instructions:
- Open with a concise conclusion of key findings, afterward followed with detailed analysis
- Provide a narrative response drawing from the available analysis
- Write fluently and naturally, like a banking analyst report.
- Focus on key themes, trends, and insights
- Use specific examples and data points from the analysis
- Be punchy and assertive, max 2 paragraphs. Don't divert from the question
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
                        "data_context": {"type": "qualitative", "tickers": tickers, "timeframe": timeframe}
                    })
                    
                except Exception as e:
                    st.error(f"Error generating qualitative response: {str(e)}")