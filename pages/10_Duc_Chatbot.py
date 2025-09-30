#%%
"""
MCP Model - AI Banking Analysis Assistant
Streamlit interface for OpenAI-powered banking analysis with tool execution
"""

import streamlit as st

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Duc Chatbot",
    layout="wide"
)

import pandas as pd
import json
import os
import sys
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import threading
import plotly.graph_objects as go
import plotly.express as px

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Import and apply Google Fonts
from utilities.style_utils import apply_google_font
from utilities.sidebar_style import apply_sidebar_style
apply_google_font()
apply_sidebar_style()

# Load environment variables
load_dotenv()

# Initialize session state
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'facts_memory' not in st.session_state:
    st.session_state.facts_memory = []
if 'tool_cache' not in st.session_state:
    st.session_state.tool_cache = {}
if 'tool_executions' not in st.session_state:
    st.session_state.tool_executions = []
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "gpt-5-mini"
if 'pending_charts' not in st.session_state:
    st.session_state.pending_charts = []
if 'developer_mode' not in st.session_state:
    st.session_state.developer_mode = False
if 'tool_cache_ttl' not in st.session_state:
    # Cache TTL for per-call cache in UI layer (seconds)
    st.session_state.tool_cache_ttl = int(os.getenv("UI_TOOL_CACHE_TTL", "300"))
if 'max_tool_concurrency' not in st.session_state:
    # Bound tool parallelism to avoid oversubscription
    default_workers = max(2, min(8, (os.cpu_count() or 4) * 2))
    st.session_state.max_tool_concurrency = int(os.getenv("MAX_TOOL_CONCURRENCY", str(default_workers)))

# Initialize tool system (respect developer mode for reloads)
import importlib
try:
    if st.session_state.developer_mode and 'utilities.Banking_MCP' in sys.modules:
        importlib.reload(sys.modules['utilities.Banking_MCP'])
    from utilities.Banking_MCP import BankingToolSystem
    if 'tool_system' not in st.session_state or st.session_state.developer_mode:
        st.session_state.tool_system = BankingToolSystem()
    st.session_state.tool_system_error = None
except Exception as e:
    st.session_state.tool_system = None
    st.session_state.tool_system_error = str(e)

# Initialize OpenAI client
if 'openai_client' not in st.session_state:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.session_state.openai_client = None


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate estimated cost based on token usage"""
    # Pricing per 1K tokens (as of late 2024)
    # Note: gpt-5 doesn't exist yet, using GPT-4 pricing as placeholder
    pricing = {
        "gpt-5": {"input": 0.03, "output": 0.06},  # Using GPT-4 Turbo pricing
        "gpt-5-mini": {"input": 0.0015, "output": 0.002},  # Using GPT-3.5 Turbo pricing
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
    }
    
    # Default to GPT-4 pricing if model not found
    model_pricing = pricing.get(model, pricing["gpt-4"])
    
    input_cost = (input_tokens / 1000) * model_pricing["input"]
    output_cost = (output_tokens / 1000) * model_pricing["output"]
    
    return input_cost + output_cost


def execute_tool_call_sync(tool_name: str, arguments: Dict, tool_system) -> Dict:
    """Execute a tool synchronously without accessing session state"""
    # Create cache key
    cache_key = f"{tool_name}_{json.dumps(arguments, sort_keys=True)}"
    
    # Execute the tool
    result = tool_system.execute_tool(tool_name, arguments)
    
    return result, cache_key


async def execute_tool_async(tool_name: str, arguments: Dict, tool_system) -> Dict:
    """Async wrapper for tool execution"""
    loop = asyncio.get_event_loop()
    # Run in executor without accessing session state
    result, cache_key = await loop.run_in_executor(
        None, 
        execute_tool_call_sync, 
        tool_name, 
        arguments,
        tool_system
    )
    return result


async def execute_parallel_tools(tool_calls: List[Dict], tool_system) -> List[Dict]:
    """Execute multiple tools in parallel"""
    # Fallback async executor using threads under the hood
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=st.session_state.max_tool_concurrency) as pool:
        tasks = []
        for tool_call in tool_calls:
            function_name = tool_call['function']['name']
            function_args = json.loads(tool_call['function']['arguments'])
            tasks.append(loop.run_in_executor(pool, execute_tool_call_sync, function_name, function_args, tool_system))
        results = await asyncio.gather(*tasks)
        # unwrap (result, cache_key)
        return [r[0] for r in results]


def _cache_get(cache_key: str):
    item = st.session_state.tool_cache.get(cache_key)
    if not item:
        return None
    ts = item.get('timestamp')
    if not ts:
        return None
    if (datetime.now() - ts).total_seconds() > st.session_state.tool_cache_ttl:
        return None
    return item['result']


def _cache_set(cache_key: str, result: Dict):
    st.session_state.tool_cache[cache_key] = {
        'result': result,
        'timestamp': datetime.now()
    }


def compact_tool_result_for_llm(result: Dict, max_rows: int = None) -> Dict:
    """Trim large payloads before sending to the LLM to reduce tokens."""
    try:
        max_rows = max_rows or int(os.getenv("LLM_TOOL_MAX_ROWS", "200"))
    except Exception:
        max_rows = 200
    if not isinstance(result, dict):
        return result
    out = dict(result)
    data = out.get('data')
    if isinstance(data, list) and len(data) > max_rows:
        head_n = max(5, min(20, int(os.getenv("LLM_TOOL_HEAD_ROWS", "10"))))
        tail_n = max(0, min(10, int(os.getenv("LLM_TOOL_TAIL_ROWS", "5"))))
        out['data_head'] = data[:head_n]
        out['data_tail'] = data[-tail_n:] if tail_n else []
        out['data'] = []
    return out


def _normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def batch_tool_calls(tool_calls: List[Dict]):
    """Batch compatible tool calls by merging tickers where args match.
    Returns (batched_calls, batch_meta) where batch_meta aligns to batched_calls and holds mapping to original indices and original args.
    """
    groups = {}
    meta = {}
    for idx, tc in enumerate(tool_calls):
        name = tc['function']['name']
        args = json.loads(tc['function']['arguments']) if isinstance(tc['function']['arguments'], str) else tc['function']['arguments']
        key = None
        if name == 'query_historical_data':
            key = (
                name,
                args.get('frequency'),
                tuple(sorted(_normalize_list(args.get('periods')))) if args.get('periods') else args.get('period'),
                args.get('metric'),
                args.get('metric_group', 'all'),
            )
        elif name == 'get_valuation_analysis':
            key = (name, args.get('metric', 'PB'))
        elif name == 'query_forecast_data':
            key = (name,)
        elif name == 'get_earnings_drivers':
            key = (name, args.get('period'), args.get('timeframe', 'QoQ'), args.get('frequency', 'quarterly'))
        elif name == 'get_commentary':
            key = (name, args.get('quarter'))
        elif name == 'get_stock_performance':
            key = (name, args.get('start_date'), args.get('end_date'))
        else:
            key = (name, json.dumps({k: v for k, v in args.items() if k != 'tickers'}, sort_keys=True))

        if key not in groups:
            groups[key] = {
                'name': name,
                'args': {k: v for k, v in args.items() if k != 'tickers'},
                'tickers': set(_normalize_list(args.get('tickers')))
            }
            meta[key] = {'originals': [{'index': idx, 'args': args}]}
        else:
            groups[key]['tickers'].update(_normalize_list(args.get('tickers')))
            meta[key]['originals'].append({'index': idx, 'args': args})

    batched_calls = []
    batch_meta = []
    for key, payload in groups.items():
        batched_args = dict(payload['args'])
        if payload['tickers']:
            batched_args['tickers'] = sorted(list(payload['tickers']))
        batched_call = {
            'id': None,
            'type': 'function',
            'function': {
                'name': payload['name'],
                'arguments': json.dumps(batched_args, sort_keys=True)
            }
        }
        batched_calls.append(batched_call)
        batch_meta.append({'key': key, 'originals': meta[key]['originals']})
    return batched_calls, batch_meta


def _subset_query_historical_data(batched_result: Dict, orig_args: Dict) -> Dict:
    tickers = set(_normalize_list(orig_args.get('tickers')))
    if not tickers:
        return batched_result
    data = batched_result.get('data', [])
    subset = [row for row in data if row.get('TICKER') in tickers]
    out = dict(batched_result)
    out['data'] = subset
    out['records'] = len(subset)
    return out


def _subset_map_dict(batched_result: Dict, key_field: str, subset_keys: List[str], single_when_one: bool = False, extra_fields: List[str] = None, constant_fields: Dict = None) -> Dict:
    extra_fields = extra_fields or []
    constant_fields = constant_fields or {}
    # Generic helper to subset mapping results like {'results': {ticker: {...}}}
    if 'results' in batched_result and isinstance(batched_result['results'], dict):
        results = {k: v for k, v in batched_result['results'].items() if k in subset_keys}
        if single_when_one and len(results) == 1:
            return list(results.values())[0]
        out = {**{f: batched_result.get(f) for f in extra_fields}, 'results': results, **constant_fields}
        out['requested'] = len(subset_keys)
        out['found'] = len(results)
        out['status'] = 'success' if results else 'failed'
        return out
    # Valuation specific: detailed_results dict
    if 'detailed_results' in batched_result and isinstance(batched_result['detailed_results'], dict):
        details = {k: v for k, v in batched_result['detailed_results'].items() if k in subset_keys}
        if single_when_one and len(details) == 1:
            t = list(details.keys())[0]
            single = details[t].copy()
            single['ticker'] = t
            single['metric'] = batched_result.get('metric')
            single['status'] = 'success'
            return single
        out = {
            'metric': batched_result.get('metric'),
            'detailed_results': details,
            'comparison': [c for c in batched_result.get('comparison', []) if c.get('ticker') in subset_keys]
        }
        out['requested'] = len(subset_keys)
        out['found'] = len(details)
        out['status'] = 'success' if details else 'failed'
        return out
    return batched_result


def create_plotly_chart(chart_spec: Dict) -> go.Figure:
    """Create a Plotly chart from the specification"""
    chart_type = chart_spec.get("chart_type", "line")
    data = chart_spec.get("data", {})
    title = chart_spec.get("title", "")
    x_label = chart_spec.get("x_label", "")
    y_label = chart_spec.get("y_label", "")
    y_format = chart_spec.get("y_format", "number")
    
    # Define custom color palette - #398278 (teal) and #cc7c5e (terracotta)
    custom_colors = ['#398278', '#cc7c5e', '#5A8A7F', '#e6a085', '#2D5E52', '#b5694f']
    
    # Create figure
    fig = go.Figure()
    
    # Add data series
    x_values = data.get("x", [])
    for idx, series in enumerate(data.get("series", [])):
        name = series.get("name", "Series")
        y_values = series.get("y", [])
        color = custom_colors[idx % len(custom_colors)]
        
        if chart_type == "line":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='lines+markers',
                name=name,
                line=dict(width=2, color=color),
                marker=dict(size=6, color=color)
            ))
        elif chart_type == "bar":
            fig.add_trace(go.Bar(
                x=x_values,
                y=y_values,
                name=name,
                marker=dict(color=color)
            ))
        elif chart_type == "scatter":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='markers',
                name=name,
                marker=dict(size=8, color=color)
            ))
        elif chart_type == "area":
            fig.add_trace(go.Scatter(
                x=x_values,
                y=y_values,
                mode='lines',
                name=name,
                fill='tozeroy',
                line=dict(width=2, color=color),
                fillcolor=color
            ))
    
    # Format y-axis based on type
    yaxis_config = {"title": y_label}
    if y_format == "percent":
        yaxis_config["tickformat"] = ".1%"
    elif y_format == "currency":
        yaxis_config["tickformat"] = "$,.0f"
    
    # Update layout
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis=yaxis_config,
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50),
        height=400
    )
    
    return fig


def compress_assistant_response(response: str, tool_calls_made: List[str], user_message: str) -> Dict:
    """Compress assistant response to structured data to save tokens"""
    import re
    
    compressed = {
        "tickers": [],
        "periods": [],
        "metrics": {},
        "tools": tool_calls_made[:5],
        "summary": ""
    }
    
    # Extract tickers
    tickers = re.findall(r'\b[A-Z]{3,4}\b', response + " " + user_message)
    compressed["tickers"] = list(set(tickers))[:10]
    
    # Extract periods
    quarters = re.findall(r'\b\d{4}-Q\d\b|\bQ\d\s*\d{4}\b|\b20\d{2}\b', response)
    compressed["periods"] = list(set(quarters))[:5]
    
    # Extract key metrics
    roe_match = re.search(r'ROE[\s]+([0-9.]+)%', response)
    if roe_match:
        compressed["metrics"]["ROE"] = roe_match.group(1) + "%"
    
    # Create summary
    if compressed["tickers"] and compressed["periods"]:
        compressed["summary"] = f"{compressed['tickers'][0]} {compressed['periods'][0]}"
    elif compressed["tickers"]:
        compressed["summary"] = f"Analyzed {', '.join(compressed['tickers'][:2])}"
    else:
        compressed["summary"] = "Banking analysis"
    
    return compressed


def reconstruct_context(compressed_history: List[Dict]) -> str:
    """Reconstruct concise context from compressed history"""
    if not compressed_history:
        return ""
    
    context_parts = []
    
    for item in compressed_history[-3:]:  # Last 3 items
        if item.get("role") == "user":
            content = item.get("content", "")
            if len(content) > 100:
                context_parts.append(f"User asked: {content[:100]}...")
            else:
                context_parts.append(f"User asked: {content}")
        elif item.get("role") == "assistant_compressed":
            data = item.get("data", {})
            parts = []
            if data.get("tickers"):
                parts.append(f"Discussed {', '.join(data['tickers'][:3])}")
            if data.get("periods"):
                parts.append(f"for {', '.join(data['periods'][:2])}")
            if parts:
                context_parts.append(" ".join(parts))
    
    return " | ".join(context_parts) if context_parts else ""


def chat_with_ai_streaming(user_message: str):
    """
    Enhanced chat function with streaming responses and parallel tool execution
    """
    if not st.session_state.openai_client:
        st.error("❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file.")
        return
    
    if 'tool_system' not in st.session_state or not st.session_state.tool_system:
        st.error("❌ Tool system not initialized. Please refresh the page.")
        return
    
    # Clear any pending charts from previous messages
    st.session_state.pending_charts = []
    
    # Get tool system reference before async operations
    tool_system = st.session_state.tool_system
    
    # Initialize usage tracking
    cumulative_usage = None  # Will accumulate usage across all rounds
    
    # Prepare messages
    messages = []
    context_str = reconstruct_context(st.session_state.conversation_history)
    
    system_content = """You are a banking analyst assistant. Use tools to get data, then provide CONCISE analysis.
IMPORTANT: ALWAYS call get_data_availability() first when user asks for 'latest', 'recent', 'current' data.
Tickers must be arrays: ["VCB"] for single, ["VCB", "ACB"] for multiple."""
    
    if context_str:
        system_content += f"\n\nPrevious context: {context_str}"
    
    messages.append({"role": "system", "content": system_content})
    messages.append({"role": "user", "content": user_message})
    
    # Get tool schemas
    tools = tool_system.get_openai_tools()
    
    # Create containers for streaming
    typing_container = st.empty()  # Separate container for "Duc is typing"
    response_container = st.empty()
    tool_status_container = st.container()
    
    accumulated_response = ""
    tool_call_count = 0
    tool_calls_made = []
    max_rounds = 20
    rounds = 0
    
    # Show initial typing indicator with custom styling
    typing_container.markdown(
        '<div style="background-color: #DDDDD6; padding: 8px 16px; border-radius: 8px; display: inline-block; font-size: 14px; color: #333;">Duc is typing...</div>',
        unsafe_allow_html=True
    )
    
    # Main chat loop
    while rounds < max_rounds:
        rounds += 1
        
        try:
            # Call OpenAI with streaming and request usage stats
            stream = st.session_state.openai_client.chat.completions.create(
                model=st.session_state.selected_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
                stream_options={"include_usage": True}  # Get exact token usage from OpenAI
            )
            
            # Process streaming response
            current_tool_calls = []
            assistant_content = ""
            is_tool_call = False
            
            for chunk in stream:
                # Check if this is the final chunk with usage data
                if hasattr(chunk, 'usage') and chunk.usage is not None:
                    # Accumulate usage across rounds
                    if cumulative_usage is None:
                        cumulative_usage = chunk.usage
                    else:
                        # Add to cumulative totals
                        cumulative_usage.prompt_tokens += chunk.usage.prompt_tokens
                        cumulative_usage.completion_tokens += chunk.usage.completion_tokens
                        cumulative_usage.total_tokens += chunk.usage.total_tokens
                    continue  # Final chunk has empty choices, skip processing
                
                # Skip chunks with no choices (safety check)
                if not chunk.choices:
                    continue
                    
                delta = chunk.choices[0].delta
                
                # Check for tool calls
                if delta.tool_calls:
                    is_tool_call = True
                    for tool_call in delta.tool_calls:
                        # Accumulate tool call data
                        if len(current_tool_calls) <= tool_call.index:
                            current_tool_calls.append({
                                "id": "",
                                "function": {"name": "", "arguments": ""}
                            })
                        
                        if tool_call.id:
                            current_tool_calls[tool_call.index]["id"] = tool_call.id
                        if tool_call.function.name:
                            current_tool_calls[tool_call.index]["function"]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            current_tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments
                
                # Check for content (non-tool response)
                if delta.content and not is_tool_call:
                    # Clear typing indicator when actual content starts streaming
                    if not assistant_content:  # First content chunk
                        typing_container.empty()
                    assistant_content += delta.content
                    accumulated_response += delta.content
                    # Stream the response to user
                    response_container.markdown(accumulated_response + "▌")
            
            # Remove cursor after streaming
            if assistant_content:
                response_container.markdown(accumulated_response)
            
            # Handle tool calls if any
            if current_tool_calls:
                # Keep the typing indicator visible during tool execution
                # (it's already shown at the start of the loop)
                
                # Collect tool names for minimal display and build cache-aware plan
                tool_names = []
                planned_calls = []  # (index, tool_call, cache_key, cached_result_or_None)
                for i, tool_call in enumerate(current_tool_calls):
                    tool_name = tool_call['function']['name']
                    args = json.loads(tool_call['function']['arguments'])
                    cache_key = f"{tool_name}_{json.dumps(args, sort_keys=True)}"
                    cached = _cache_get(cache_key)
                    planned_calls.append((i, tool_call, cache_key, cached))
                    tool_calls_made.append(tool_name)
                    tool_names.append(tool_name)
                    tool_call_count += 1
                
                # Execute only misses in parallel (background)
                start_time = time.time()
                
                # Prepare misses and batch them
                miss_indices = [i for i, pc in enumerate(planned_calls) if pc[3] is None]
                misses = [planned_calls[i][1] for i in miss_indices]
                if misses:
                    batched_calls, batch_meta = batch_tool_calls(misses)
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        batched_results = loop.run_until_complete(
                            execute_parallel_tools(batched_calls, tool_system)
                        )
                    finally:
                        loop.close()
                    # Split batched results back to each miss
                    miss_results_by_local_index = {}
                    batched_call_names = [bc['function']['name'] for bc in batched_calls]
                    for idx_b, (batched_res, meta_entry) in enumerate(zip(batched_results, batch_meta)):
                        name = batched_call_names[idx_b]
                        for orig in meta_entry['originals']:
                            orig_args = orig['args']
                            # Split by tool type
                            if name == 'query_historical_data':
                                piece = _subset_query_historical_data(batched_res, orig_args)
                            elif name == 'get_earnings_drivers':
                                tickers = _normalize_list(orig_args.get('tickers'))
                                piece = _subset_map_dict(batched_res, 'ticker', tickers, single_when_one=True, extra_fields=['period', 'timeframe', 'frequency'])
                            elif name == 'get_commentary':
                                tickers = _normalize_list(orig_args.get('tickers'))
                                piece = _subset_map_dict(batched_res, 'ticker', tickers, single_when_one=True)
                            elif name == 'get_valuation_analysis':
                                tickers = _normalize_list(orig_args.get('tickers'))
                                piece = _subset_map_dict(batched_res, 'ticker', tickers, single_when_one=True)
                            elif name == 'get_stock_performance':
                                # Rebuild a subset summary
                                tickers = set(_normalize_list(orig_args.get('tickers')))
                                if len(tickers) == 1:
                                    t = list(tickers)[0]
                                    piece = batched_res.get('detailed_results', {}).get(t, batched_res)
                                else:
                                    ranking = [r for r in batched_res.get('ranking', []) if r.get('ticker') in tickers]
                                    summary = None
                                    if ranking:
                                        perfs = [r['performance_pct'] for r in ranking]
                                        summary = {
                                            'best_performer': ranking[0]['ticker'],
                                            'worst_performer': ranking[-1]['ticker'],
                                            'average_performance': round(sum(perfs)/len(perfs), 2),
                                            'median_performance': round(sorted(perfs)[len(perfs)//2], 2)
                                        }
                                    piece = {
                                        'period': batched_res.get('period'),
                                        'detailed_results': {t: batched_res.get('detailed_results', {}).get(t) for t in tickers},
                                        'ranking': ranking,
                                        'summary': summary,
                                        'requested': len(tickers),
                                        'successful': len(ranking),
                                        'status': 'success' if ranking else 'failed'
                                    }
                            elif name == 'query_forecast_data':
                                # Filter actual and forecast data to requested tickers
                                req = _normalize_list(orig_args.get('tickers'))
                                if not req:
                                    piece = batched_res
                                else:
                                    req_set = set(req)
                                    piece = dict(batched_res)
                                    # Adjust requested_tickers field
                                    piece['requested_tickers'] = req
                                    # Filter actual_data
                                    if isinstance(piece.get('actual_data'), dict):
                                        ad = piece['actual_data']
                                        ad_data = ad.get('data', [])
                                        ad_f = [r for r in ad_data if r.get('TICKER') in req_set]
                                        piece['actual_data'] = {
                                            'year': ad.get('year'),
                                            'records': len(ad_f),
                                            'data': ad_f
                                        }
                                    # Filter forecast_data
                                    if isinstance(piece.get('forecast_data'), dict):
                                        fd = piece['forecast_data']
                                        fd_data = fd.get('data', [])
                                        fd_f = [r for r in fd_data if r.get('TICKER') in req_set]
                                        piece['forecast_data'] = {
                                            'years': fd.get('years'),
                                            'records': len(fd_f),
                                            'data': fd_f
                                        }
                            else:
                                piece = batched_res
                            miss_results_by_local_index[orig['index']] = piece
                else:
                    miss_results_by_local_index = {}

                # Reassemble results preserving order, using cache hits when available
                ordered_results = []
                for global_idx, (i, tool_call, cache_key, cached) in enumerate(planned_calls):
                    if cached is not None:
                        ordered_results.append(cached)
                    else:
                        # Map from global planned_calls index to its local miss index position
                        local_index = miss_indices.index(global_idx)
                        res = miss_results_by_local_index.get(local_index)
                        ordered_results.append(res)
                        _cache_set(cache_key, res)
                
                execution_time = time.time() - start_time
                
                # Update cache and execution log in main thread
                for tool_call, result in zip(current_tool_calls, ordered_results):
                    function_name = tool_call['function']['name']
                    function_args = json.loads(tool_call['function']['arguments'])
                    cache_key = f"{function_name}_{json.dumps(function_args, sort_keys=True)}"
                    
                    # Check if this is a chart rendering tool
                    if function_name == "render_chart" and result.get("status") == "success":
                        if "chart_spec" in result:
                            st.session_state.pending_charts.append(result["chart_spec"])
                    
                    # Update cache in session state (main thread)
                    _cache_set(cache_key, result)
                    
                    # Log execution
                    st.session_state.tool_executions.append({
                        "tool": function_name,
                        "arguments": function_args,
                        "timestamp": datetime.now().isoformat(),
                        "result": result
                    })
                
                # Don't clear typing here - let it stay until response starts
                # The typing indicator will be cleared when actual content starts streaming
                
                # Show minimal tool summary (small captions below)
                with tool_status_container:
                    # Show one line per tool with status icon
                    for tool_name, result in zip(tool_names, ordered_results):
                        if result.get("status") == "success":
                            st.caption(f"✓ {tool_name}")
                        else:
                            st.caption(f"✗ {tool_name}: {result.get('error', 'Failed')[:50]}")
                
                # Add tool results to messages
                messages.append({
                    "role": "assistant",
                    "content": assistant_content or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": tc["function"]
                        } for tc in current_tool_calls
                    ]
                })
                
                for tool_call, result in zip(current_tool_calls, ordered_results):
                    compacted = compact_tool_result_for_llm(result)
                    tool_response = json.dumps(compacted, default=str)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_response
                    })
                
                # Continue to next round for tool response
                continue
            else:
                # No tool calls, we have the final response
                if assistant_content:
                    # Update conversation history
                    st.session_state.conversation_history.append({"role": "user", "content": user_message})
                    compressed_response = compress_assistant_response(accumulated_response, tool_calls_made, user_message)
                    st.session_state.conversation_history.append({
                        "role": "assistant_compressed",
                        "data": compressed_response
                    })
                    
                    # Keep only last 6 messages
                    if len(st.session_state.conversation_history) > 6:
                        st.session_state.conversation_history = st.session_state.conversation_history[-6:]
                    
                    # Add minimal tool summary if tools were used
                    if tool_call_count > 0:
                        st.caption(f"_Used {tool_call_count} tool{'s' if tool_call_count > 1 else ''}_")
                    
                    # Display token usage and cost if available from OpenAI
                    if cumulative_usage:
                        # Use OpenAI's actual token counts (accumulated across all rounds)
                        total_input_tokens = cumulative_usage.prompt_tokens
                        total_output_tokens = cumulative_usage.completion_tokens
                        total_tokens = cumulative_usage.total_tokens
                        
                        estimated_cost = calculate_cost(total_input_tokens, total_output_tokens, st.session_state.selected_model)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption(f"📊 Token Usage: {total_input_tokens:,} input + {total_output_tokens:,} output = {total_tokens:,} total")
                        with col2:
                            st.caption(f"💰 Cost: ${estimated_cost:.4f}")
                    
                    # Render any pending charts
                    if st.session_state.pending_charts:
                        for chart_spec in st.session_state.pending_charts:
                            try:
                                fig = create_plotly_chart(chart_spec)
                                st.plotly_chart(fig, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error rendering chart: {str(e)}")
                        # Clear pending charts after rendering
                        st.session_state.pending_charts = []
                
                break
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            break
    
    if rounds >= max_rounds:
        st.warning(f"Analysis completed with {tool_call_count} tool calls. The query may be too complex.")


def main():
    st.title("Duc - AI Chatbot")
    st.markdown("This chatbot can draw charts, provide analysis and fetch banking data")
    
    # Add custom CSS for iPhone-style message bubbles
    st.markdown("""
    <style>
    /* User message styling - iPhone blue */
    div[data-testid="stChatMessageContent-user"] {
        background-color: #619BF7;
        color: white;
        border-radius: 18px;
        padding: 8px 14px;
        margin: 4px 0;
        max-width: 70%;
        margin-left: auto;
        margin-right: 0;
    }
    
    /* Assistant message styling - iPhone gray */
    div[data-testid="stChatMessageContent-assistant"] {
        background-color: #F1F1F2;
        color: black;
        border-radius: 18px;
        padding: 8px 14px;
        margin: 4px 0;
        max-width: 70%;
        margin-left: 0;
        margin-right: auto;
    }
    
    /* Adjust message container alignment */
    div[data-testid="stChatMessage-user"] {
        justify-content: flex-end;
    }
    
    div[data-testid="stChatMessage-assistant"] {
        justify-content: flex-start;
    }
    
    /* Hide default avatars for cleaner look */
    div[data-testid="stChatMessage-user"] img,
    div[data-testid="stChatMessage-assistant"] img {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Check API key
    if not st.session_state.openai_client:
        st.error("⚠️ OpenAI API key not configured!")
        st.info("Please create a `.env` file with your OpenAI API key:")
        st.code("OPENAI_API_KEY=your-api-key-here")
        return
    
    # Check tool system
    if 'tool_system' not in st.session_state or not st.session_state.tool_system:
        st.error("⚠️ Tool system not initialized!")
        if 'tool_system_error' in st.session_state and st.session_state.tool_system_error:
            st.error(f"Error details: {st.session_state.tool_system_error}")
        st.info("Please refresh the page or check that the Banking_MCP module is properly installed.")
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        # Developer mode toggle (controls MCP reload)
        dev = st.toggle("Developer Mode (reload tools)", value=st.session_state.developer_mode, help="Reload Banking_MCP on each run to pick up code changes")
        if dev != st.session_state.developer_mode:
            st.session_state.developer_mode = dev
            st.rerun()
        
        # Show available tools
        with st.expander("📋 Available Tools", expanded=False):
            if 'tool_system' in st.session_state and st.session_state.tool_system:
                tools = st.session_state.tool_system.get_tool_list()
                for tool in tools:
                    st.write(f"• {tool}")
            else:
                st.write("Tool system not initialized")
        
        # Clear tool executions
        if st.button("🗑️ Clear Tool History"):
            st.session_state.tool_executions = []
            st.rerun()
        
        # Export tool executions
        if st.button("📥 Export Tool History"):
            export_data = {
                "tool_executions": st.session_state.tool_executions,
                "timestamp": datetime.now().isoformat()
            }
            st.download_button(
                "Download JSON",
                json.dumps(export_data, indent=2, default=str),
                "tool_history.json",
                "application/json"
            )
    
    # Model selection
    col1, col2, col3 = st.columns([2, 3, 2])
    with col1:
        st.session_state.selected_model = st.selectbox(
            "Select AI Model:",
            options=["gpt-5", "gpt-5-mini"],
            index=1 if st.session_state.selected_model == "gpt-5-mini" else 0,
            help="GPT-5: More capable, better reasoning | GPT-5-mini: Faster, more cost-effective"
        )
    
    # Show conversation info
    st.info("**Rules for your questions**")
    col1, col2 = st.columns(2)
    with col1:
        st.write("1. Be specific (e.g., ask for PB not just 'valuation', or PBT, not just 'earnings')")
        st.write("2. Available: historical, forecast, analysis, stock data, charting")
    with col2:
        st.write("3. Sub-Sectors supported: SOCB, Private 1, Private 2, Private 3")
        st.write("4. Short conversation is supported")
    
    # Chat input
    user_input = st.chat_input("Ask Duc something ...")
    
    if user_input:
        # Add user message to display
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get AI response with streaming
        with st.chat_message("assistant"):
            chat_with_ai_streaming(user_input)
    
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