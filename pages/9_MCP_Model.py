"""
MCP Model - AI Banking Analysis Assistant
Streamlit interface for OpenAI-powered banking analysis with tool execution
"""

import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import the banking tool system
from utilities.Banking_MCP import get_tool_system

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="DucGPT MCP version",
    layout="wide"
)

# Initialize session state
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'tool_executions' not in st.session_state:
    st.session_state.tool_executions = []
if 'openai_client' not in st.session_state:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.session_state.openai_client = None
if 'tool_system' not in st.session_state:
    st.session_state.tool_system = get_tool_system()


def execute_tool_call(tool_name: str, arguments: Dict) -> Dict:
    """Execute a tool and return results"""
    tool_system = st.session_state.tool_system
    
    # Log the tool execution
    execution_log = {
        "tool": tool_name,
        "arguments": arguments,
        "timestamp": datetime.now().isoformat()
    }
    
    # Execute the tool
    result = tool_system.execute_tool(tool_name, arguments)
    
    execution_log["result"] = result
    st.session_state.tool_executions.append(execution_log)
    
    return result


def format_tool_result(result: Dict) -> str:
    """Format tool result for display"""
    if result.get("status") == "failed":
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    
    # Remove status field for cleaner display
    display_result = {k: v for k, v in result.items() if k != "status"}
    
    # Format based on content type
    if "data" in display_result and isinstance(display_result["data"], list):
        # If data is a list of records, show as table
        if display_result["data"]:
            df = pd.DataFrame(display_result["data"])
            return f"Found {len(display_result['data'])} records:\n{df.to_string()}"
    
    # Default JSON formatting
    return json.dumps(display_result, indent=2, default=str)


def chat_with_ai(user_message: str) -> str:
    """
    Send message to OpenAI and handle tool calls
    Allows unlimited tool execution rounds for complete analysis
    """
    if not st.session_state.openai_client:
        return "❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file."
    
    # Prepare messages
    messages = []
    
    # Add system message
    messages.append({
        "role": "system",
        "content": """You are a Vietnamese banking analyst assistant with access to comprehensive banking data.

INSTRUCTIONS:
1. Call get_data_availability() first when asked for "latest" or "current" data
2. All 'tickers' parameters require arrays: ["VCB"] for single, ["VCB", "ACB", "BID"] for multiple
3. For sector queries: call list_all_banks() first, then use the returned ticker array
4. Provide specific numbers and detailed analysis

Available tools:
- get_data_availability(): Current date and latest data periods
- get_bank_info(tickers[]): Bank sector classification
- list_all_banks(): All banks grouped by sector
- query_historical_data(tickers[], period, metric_group): Historical metrics
- query_forecast_data(tickers[]): Forecast data 
- calculate_growth_metrics(tickers[], metric, periods): Growth rates and CAGR calculation
- get_valuation_analysis(tickers[], metric): Valuation with Z-scores
- compare_banks(tickers[], metrics, period): Compare multiple banks
- get_ai_commentary(tickers[], quarter): analysis for deeper insights
- get_sector_performance(sector, period): Pre-aggregated sector metrics
- get_stock_performance(tickers[], start_date, end_date): Stock performance

"""
    })
    
    # Add conversation history
    for msg in st.session_state.conversation_history:
        messages.append(msg)
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})
    
    # Get tool schemas

    tools = st.session_state.tool_system.get_openai_tools()
    
    # Initialize progress tracking
    max_rounds = 50  # Safety limit to prevent infinite loops
    with st.spinner("DucGPT is typing ..."):
        rounds = 0
        final_response = None
        tool_call_count = 0
        
        while rounds < max_rounds:
            rounds += 1
            
            # Call OpenAI
            try:
                response = st.session_state.openai_client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.5
                )
            except Exception as e:
                return f"❌ Error calling OpenAI: {str(e)}"
            
            # Get assistant message
            assistant_message = response.choices[0].message
            messages.append(assistant_message.model_dump())
            
            # Check if there are tool calls
            if assistant_message.tool_calls:
                # Show tool execution status
                tool_status = st.empty()
                tool_results_container = st.container()
                
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Update status with counter
                    tool_call_count += 1
                    tool_status.info(f"🔧 Executing tool #{tool_call_count}: **{function_name}**")
                    
                    # Execute the tool
                    tool_result = execute_tool_call(function_name, function_args)
                    
                    # Show tool result in expander
                    with tool_results_container.expander(f"Tool: {function_name}", expanded=False):
                        st.code(json.dumps(function_args, indent=2))
                        if tool_result.get("status") == "success":
                            st.success("✅ Success")
                            # Show summary of result
                            if "records" in tool_result:
                                st.write(f"Found {tool_result['records']} records")
                            if "data" in tool_result and isinstance(tool_result["data"], list) and tool_result["data"]:
                                df = pd.DataFrame(tool_result["data"][:5])  # Show first 5 rows
                                st.dataframe(df)
                        else:
                            st.error(f"❌ {tool_result.get('error', 'Failed')}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str)
                    })
                
                # Clear the status
                tool_status.empty()
                
                # Continue to next round
                continue
            else:
                # No more tool calls, we have the final response
                final_response = assistant_message.content
                # Add tool count summary if tools were used
                if tool_call_count > 0:
                    final_response = f"{final_response}\n\n---\n*Analysis completed using {tool_call_count} tool{'s' if tool_call_count > 1 else ''}.*"
                break
        
        if not final_response:
            if rounds >= max_rounds:
                final_response = f"I've executed {tool_call_count} tools but may need more to fully answer your question. The analysis so far is incomplete. Please ask me to continue if you need more details."
            else:
                final_response = "Your question is too generic, please ask actual Duc"
        
        return final_response


def main():
    st.title("DucGPT MCP version")
    st.markdown("Only banking related questions are supported.")
    
    # Check API key
    if not st.session_state.openai_client:
        st.error("⚠️ OpenAI API key not configured!")
        st.info("Please create a `.env` file with your OpenAI API key:")
        st.code("OPENAI_API_KEY=your-api-key-here")
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Model selection
        model = st.selectbox(
            "Model",
            ["gpt-4-turbo-preview", "gpt-3.5-turbo"],
            index=0
        )
        os.environ["OPENAI_MODEL"] = model
        
        
        # Show available tools
        with st.expander("📋 Available Tools", expanded=False):
            tools = st.session_state.tool_system.get_tool_list()
            for tool in tools:
                st.write(f"• {tool}")
        
        # Clear conversation
        if st.button("🗑️ Clear Conversation"):
            st.session_state.conversation_history = []
            st.session_state.tool_executions = []
            st.rerun()
        
        # Export conversation
        if st.button("📥 Export Conversation"):
            export_data = {
                "conversation": st.session_state.conversation_history,
                "tool_executions": st.session_state.tool_executions,
                "timestamp": datetime.now().isoformat()
            }
            st.download_button(
                "Download JSON",
                json.dumps(export_data, indent=2, default=str),
                "conversation_export.json",
                "application/json"
            )
    
    # Main chat interface
    st.header("💬 Chat")
    
    # Display conversation history
    for i, msg in enumerate(st.session_state.conversation_history):
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        elif msg["role"] == "assistant" and msg.get("content"):
            with st.chat_message("assistant"):
                st.write(msg["content"])
    
    # Example queries
    if len(st.session_state.conversation_history) == 0:
        st.info("💡 **Example queries:**")
        col1, col2 = st.columns(2)
        with col1:
            st.write("• What is VCB's NPL ratio for the latest quarter?")
            st.write("• Compare ROE of all SOCB banks in 2024")
            st.write("• Which Private_1 bank has the best growth?")
        with col2:
            st.write("• Show me ACB's forecast for 2025-2026")
            st.write("• What's the sector outlook for Q3 2024?")
            st.write("• Which bank has the best valuation right now?")
    
    # Chat input
    user_input = st.chat_input("Ask DucGPT")
    
    if user_input:
        # Add user message to display
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get AI response
        with st.chat_message("assistant"):
            response_container = st.empty()
            
            # Get response with tool execution
            response = chat_with_ai(user_input)
            
            # Display response
            response_container.write(response)
        
        # Update conversation history
        st.session_state.conversation_history.append({"role": "user", "content": user_input})
        st.session_state.conversation_history.append({"role": "assistant", "content": response})
    
    # Tool execution history (in expander)
    if st.session_state.tool_executions:
        with st.expander(f"🔧 Tool Execution History ({len(st.session_state.tool_executions)} executions)"):
            for i, execution in enumerate(reversed(st.session_state.tool_executions[-10:])):
                st.write(f"**{execution['tool']}** - {execution['timestamp']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.code(json.dumps(execution['arguments'], indent=2), language="json")
                with col2:
                    if execution['result'].get('status') == 'success':
                        st.success("✅ Success")
                    else:
                        st.error(f"❌ {execution['result'].get('error', 'Failed')}")
                st.divider()


if __name__ == "__main__":
    main()