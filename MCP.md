# MCP (Model Context Protocol) Banking Analysis System

## Overview

The MCP Banking Analysis System now blends OpenAI's GPT models with curated SQL datasets, technical market feeds, and scenario simulators to deliver context-aware Vietnamese banking analysis. The expanded tool suite supports broker consensus benchmarking, “what-if” forecasting, technical scoring, and chart rendering while keeping the modular design that lets OpenAI compose multiple tools per answer.

## Current Architecture

```
┌────────────────────────────────────────────────────┐
│ Streamlit UI (pages/10_Duc_Chatbot.py + dashboards) │
│  - Chat assistant, consensus, scenario, TA pages     │
│  - Tool execution logging & cache inspection         │
│  - Conversation memory with compression              │
│  - Chart previews rendered from MCP responses        │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│        OpenAI Integration Layer (streamlit_app.py)   │
│  - GPT model configurable via environment            │
│  - Orchestrates parallel tool invocations            │
│  - Enforces data-availability handshake              │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│    Tool System (utilities/Banking_MCP.py)            │
│  - 12 modular tools registered via decorators        │
│  - Lazy SQL + API loading with configurable caches   │
│  - Universal single/multi ticker responses           │
│  - Chart + scenario generation engines               │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│                   Data Layer                         │
│  - dbo.BankingMetrics (actual + forecast lenses)     │
│  - dbo.Forecast_Consensus (broker submissions)       │
│  - dbo.Banking_Drivers (earnings driver impacts)     │
│  - dbo.Banking_Comments & Quarterly Analysis         │
│  - dbo.Market_Data (PE/PB history)                   │
│  - Data/Key_items.xlsx (metric dictionary)           │
└─────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Data Availability Handshake

Every "latest" or "current" request must anchor on `get_data_availability()`. The Streamlit assistant enforces this so GPT knows the freshest completed quarter/year, supported forecast horizons, and when to fall back from YTD to quarterly views.

### 2. Universal Tool Pattern

Most tools accept single tickers, sector aggregates, or mixed lists and adapt the payload automatically:
```python
query_historical_data(
    frequency="quarterly",
    tickers=["VCB", "ACB"],
    periods=["2024-Q3", "2024-Q4"],
    metric="NIM"
)
```
Single entities return flat dicts for easy narration; arrays return batched dictionaries with record counts and optional warnings.

### 3. Aggregate Entity Support

- **Sector** – all Vietnamese banks (median aggregations)
- **SOCB** – state-owned commercial banks
- **Private_1/2/3** – private bank tiers

These aggregates can be mixed with 3-letter tickers across historical, forecast, valuation, and scenario tools.

### 4. Insight Modules

- **Consensus vs in-house**: `get_consensus_forecast_summary` reconciles broker medians, YoY deltas, and internal forecasts.
- **Scenario engine**: `forecast_scenario` models PBT sensitivity to NIM/NPL/loan/OPEX uplifts for banks and sectors.
- **Technical stack**: `technical_analysis` delivers STS/LTS/OBOS scores fed by cached candles.
- **Chart rendering**: `render_chart` returns Vega-lite-ready specs for Streamlit to visualize tool output without dumping raw tables.

### 5. Configurable Caching & Limits

- **Dataset caches**: `@lru_cache` wraps SQL fetchers so repeated queries stay in-memory.
- **Result TTLs**: `MCP_RESULT_TTL` governs tool-response caching (default 300s).
- **Market data TTLs**: `MCP_STOCK_TTL` controls TCBS price cache (default 30 minutes).
- **Tool budget**: GPT is still capped at ~20 tool calls per turn; the assistant prunes redundant invocations.

## Current Tools (12 Active)

### 1. get_data_availability()
**Purpose**: Discover live period coverage before any downstream call.  
**Parameters**: None.  
**Returns**:
- Current date stamped at runtime.
- Latest completed quarter and year from `dbo.BankingMetrics`.
- Recent history windows (8 quarters, 5 years).
- Forecast years present in the warehouse.  
**Usage**: Must precede any "latest", "recent", or "current" request so GPT anchors analysis to real data.

### 2. get_consensus_forecast_summary()
**Purpose**: Compare broker NPATMI medians vs in-house forecasts with YoY context.  
**Parameters**:
- `tickers` (required): Bank tickers to evaluate.  
**Returns**:
- Latest broker list with median NPATMI by year and broker coverage counts.
- In-house forecast alignment and YoY deltas vs actuals.  
**Data Source**: `dbo.Forecast_Consensus` (latest per broker) blended with `dbo.BankingMetrics` actuals/forecasts.

### 3. get_bank_sector_info()
**Purpose**: Surface sector classifications or expand aggregates into component banks.  
**Parameters**:
- `tickers` (optional): Bank tickers or sector handles (Sector, SOCB, Private_1/2/3).  
**Returns**:
- No params: full sector → bank mapping.
- Bank ticker: sector label.  
- Sector handle: component constituents with counts.  
**Data Source**: Type metadata embedded in `dbo.BankingMetrics`.

### 4. query_historical_data()
**Purpose**: Retrieve curated historical metrics with flexible filters.  
**Parameters**:
- `frequency` (required): `"quarterly"` or `"yearly"`.
- `tickers`, `period`, `periods`, `metric`, `metric_group` (optional).  
**Features**:
- YTD tokens auto-expand to completed quarters.
- Supports aggregate tickers alongside banks.
- Smart metric normalization (aliases, underscores, case).  
**Returns**: Record-level dicts plus included periods.  
**Data Source**: `dbo.BankingMetrics` (actual slices via lazy projections).

### 5. query_forecast_data()
**Purpose**: Blend upcoming forecasts with latest actuals for key ratios.  
**Parameters**:
- `tickers` (optional): Filter focus banks; omit for broad view.  
**Returns**:
- Latest actual year snapshot.
- Forecast series for all available years.
- Optional single-bank growth comparison vs latest actuals.  
**Data Source**: `dbo.BankingMetrics` (ACTUAL=0 vs ACTUAL=1).

### 6. get_commentary()
**Purpose**: Deliver analyst or AI commentary for banks and sector aggregates.  
**Parameters**:
- `tickers` (required): Bank codes or `"Sector"`.
- `quarter` (required): Period such as `"2024-Q3"`.  
**Returns**:
- Bank view: commentary text + generated timestamp.
- Sector view: quarterly narrative snapshot.  
**Data Source**: `dbo.Banking_Comments` and `dbo.Quarterly_Analysis` (lazy cached).

### 7. get_valuation_analysis()
**Purpose**: Compute valuation z-scores, percentiles, and relative ranking.  
**Parameters**:
- `tickers` (required): Bank or sector handles.
- `metric` (optional): `"PE"` or `"PB"` (default `"PB"`).  
**Returns**:
- Current vs historical mean/median/std.
- Z-score & percentile with undervalued/fair/overvalued interpretation.
- Batch comparison sorted by attractiveness.  
**Data Source**: `dbo.Market_Data` joined with sector tags from `dbo.BankingMetrics`.

### 8. get_stock_performance()
**Purpose**: Calculate price performance between two dates using TCBS candles.  
**Parameters**:
- `tickers` (required): List or single code.
- `start_date`, `end_date` (required): ISO dates.  
**Returns**:
- For each ticker: actual start/end dates, prices, % change.
- Aggregated ranking & summary statistics when batching.  
**Data Source**: TCBS `stock-insight` API with per-range caching (`MCP_STOCK_TTL`).

### 9. technical_analysis()
**Purpose**: Produce short-term, long-term, and overbought/oversold scores.  
**Parameters**:
- `tickers` (required): Array of tickers to score.  
**Returns**:
- STS/LTS/OBOS composite plus component labels ready for narration.  
**Data Source**: `utilities/tech_analysis.py` leveraging cached candles from `utilities/stock_candle.py`.

### 10. get_earnings_drivers()
**Purpose**: Quantify revenue/cost drivers behind PBT changes.  
**Parameters**:
- `tickers` (required).
- `period` (required): Quarter or year.
- `timeframe` (optional): `"QoQ"`, `"YoY"`, `"T12M"`.
- `frequency` (optional): `"quarterly"` or `"yearly"`.  
**Returns**:
- PBT growth %, topline/cost/non-recurring impacts, component drilldowns (NII, fees, OPEX, provisions).  
**Data Source**: `dbo.Banking_Drivers` with QoQ/YoY/T12M suffix logic.

### 11. render_chart()
**Purpose**: Package processed data into a chart spec for the Streamlit UI.  
**Parameters**:
- `chart_type`: `line`, `bar`, `scatter`, `area`.
- `data`: `{ "x": [...], "series": [{"name": ..., "y": [...]}] }`.
- Optional `title`, `x_label`, `y_label`, `y_format`.  
**Returns**:
- Chart id + Vega-lite style payload saved server-side for immediate rendering.  
**Usage**: Invoke only after data tools so the UI can show visuals without raw table dumps.

### 12. forecast_scenario()
**Purpose**: Run what-if analysis on PBT given metric adjustments.  
**Parameters**:
- `tickers`: Banks or sectors to adjust.
- `metric`: `"NIM"`, `"NPL"`, `"loan_growth"`, `"OPEX_growth"`, `"NPL_coverage"`, `"new_NPL"`.
- `adjustment`: Basis points (NIM/NPL/new_NPL) or percentage points (growth metrics).
- `year`: Forecast year under review.  
**Returns**:
- Original vs adjusted PBT, absolute/percentage deltas, carry-forward values (e.g., new NIM).  
**Data Source**: `dbo.BankingMetrics` actuals/forecasts with fallback heuristics for missing history.

## Removed/Deprecated Tools

### compare_banks (Removed)
**Reason**: Functionality absorbed by query_historical_data with multiple ticker support  
**Migration**: Use `query_historical_data(tickers=["VCB", "ACB", "BID"])`

### get_sector_performance (Removed)
**Reason**: Sector data now accessible via query_historical_data  
**Migration**: Use `query_historical_data(tickers=["Sector"])` or specific sector tickers

### list_all_banks (Removed)
**Reason**: Merged into get_bank_sector_info  
**Migration**: Use `get_bank_sector_info()` with no parameters

### calculate_growth_metrics (Removed)
**Reason**: OpenAI can calculate growth from raw data; pre-calculated growth available in get_earnings_drivers  
**Migration**: 
- Use `query_historical_data()` and let OpenAI calculate growth
- Or use `get_earnings_drivers()` for pre-calculated QoQ, YoY, T12M impacts

## Usage Examples

### Example 1: Simple Query
**User**: "What is VCB's NPL ratio for Q3 2024?"

**System Flow**:
1. `get_data_availability()` → Verify Q3 2024 is available
2. `query_historical_data(frequency="quarterly", tickers=["VCB"], period="2024-Q3", metric="NPL")`
3. Return: NPL ratio of 1.22%

### Example 2: Sector Comparison
**User**: "Compare profitability of state-owned banks vs private banks"

**System Flow**:
1. `query_historical_data(frequency="quarterly", tickers=["SOCB", "Private_1"], period="2024-Q3", metric_group="profitability")`
2. Returns aggregated metrics for both sectors
3. AI analyzes differences in ROA, ROE, NIM

### Example 3: YTD Performance
**User**: "Show me YTD 2025 performance for all banks"

**System Flow**:
1. `get_data_availability()` → Determine completed quarters
2. `query_historical_data(frequency="quarterly", period="2025-YTD", metric_group="all")`
3. Automatically aggregates Q1-Q3 2025 data (if in Q4)

### Example 4: Earnings Analysis
**User**: "What drove VPB's profit growth in Q2 2025?"

**System Flow**:
1. `get_earnings_drivers(tickers=["VPB"], period="2025-Q2", timeframe="QoQ")`
2. Returns structured breakdown:
   - Revenue impact: +15pp (NII: +10pp, Fees: +5pp)
   - Cost impact: -3pp (OPEX: -1pp, Provisions: -2pp)
   - Non-recurring: +2pp

### Example 5: Complex Multi-Tool Analysis
**User**: "Which banks have the best valuation and growth prospects?"

**System Flow**:
1. `get_bank_sector_info()` → Get all bank tickers
2. `get_valuation_analysis(tickers=[...all banks...], metric="PB")` → Parallel execution
3. `query_forecast_data(tickers=[...top 5 undervalued...])` → Growth prospects
4. `get_commentary(tickers=[...top picks...], quarter="2024-Q3")` → Qualitative insights
5. AI synthesizes comprehensive recommendation

### Example 6: Sector Component Query
**User**: "What are the individual banks in the SOCB sector?"

**System Flow**:
1. `get_bank_sector_info(tickers=["SOCB"])`
2. Returns: Component banks ["BID", "CTG", "VCB", "AGB"]

### Example 7: Broker Benchmarking
**User**: "How do broker forecasts for VCB compare with our in-house view?"

**System Flow**:
1. `get_data_availability()` → Confirm forecast years are available
2. `get_consensus_forecast_summary(tickers=["VCB"])`
3. Return: Broker median NPATMI alongside in-house forecast deltas and YoY context

### Example 8: Scenario Shock
**User**: "What happens to VPB's 2025 PBT if NIM improves by 15 bps?"

**System Flow**:
1. `get_data_availability()` → Identify the latest actual base year
2. `forecast_scenario(tickers=["VPB"], metric="NIM", adjustment=15, year=2025)`
3. Return: Original PBT, adjusted PBT, % change, and updated NIM assumption

## Adding New Tools

### Tool Definition Pattern
```python
@self.tool(
    name="your_tool_name",
    description="Clear description for OpenAI to understand usage",
    parameters={
        "param1": {
            "type": "string",
            "description": "Parameter description",
            "required": True
        },
        "param2": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional array parameter",
            "required": False
        }
    }
)
def your_tool_name(param1: str, param2: List[str] = None) -> Dict:
    """Implementation"""
    # Use lazy loading for data
    df = self._load_historical_quarter()
    
    # Process request
    result = process_data(df, param1, param2)
    
    # Return structured response
    return {
        "status": "success",
        "data": result,
        "records": len(result)
    }
```

### Best Practices
1. **Lazy Loading**: Load data only when needed
2. **Universal Pattern**: Support single and multiple entities
3. **Structured Returns**: Always return dicts with status
4. **Error Handling**: Return {"error": "message", "status": "failed"}
5. **Efficient Defaults**: Make parameters optional when sensible

## Configuration

### Environment Variables (.env)
```
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-5  # or gpt-4-turbo-preview
TARGET_DB_CONNECTION_STRING="Driver=...;Server=...;Database=...;Uid=...;Pwd=..."
SOURCE_DB_CONNECTION_STRING="Driver=...;Server=...;Database=...;Uid=...;Pwd=..."  # optional legacy reads
MCP_RESULT_TTL=300     # seconds, optional override
MCP_STOCK_TTL=1800     # seconds, optional override
```

### Key Settings
- **Model**: GPT-5 (default) or GPT-4 Turbo
- **Temperature**: 1.0 (GPT-5 only supports default)
- **Max Tool Calls**: 20 per conversation turn
- **Result Cache TTL**: `MCP_RESULT_TTL` (default 300s)
- **Price Cache TTL**: `MCP_STOCK_TTL` (default 1800s)
- **Conversation Memory**: Last 3 exchanges (compressed)

## Performance Optimizations

### Data Loading
- **Lazy SQL fetches**: `@lru_cache` wraps each warehouse query, with column-projection caches to avoid full scans when asking for single metrics.
- **Key dictionary reuse**: `Key_items.xlsx` is memoized to normalize metric labels across historical + consensus datasets.
- **Sector rollups**: BankingMetrics already stores sector rows (Sector/SOCB/Private tiers) so no runtime aggregation cost.

### Tool Execution
- **Parallel API calls**: Stock performance requests run via `ThreadPoolExecutor` with per-range caching.
- **Result caching**: Per-tool TTL caches honor `MCP_RESULT_TTL` to short-circuit identical prompts.
- **Compressed memory**: Conversation history stays trimmed to 3 exchanges for token efficiency.

### Pre-calculated Metrics
`dbo.Banking_Drivers` provides QoQ, YoY, and T12M impacts. Prefer these fields instead of recomputing growth inside the tools.

## Tool Portfolio Highlights

### Recent Enhancements
1. **Broker consensus coverage** ✓ `get_consensus_forecast_summary` reconciles latest broker vs in-house data.
2. **Technical signal engine** ✓ `technical_analysis` mirrors the Streamlit TA scores inside MCP.
3. **Scenario + chart outputs** ✓ `forecast_scenario` and `render_chart` unblock the new dashboards.

### Streamlining To Date
- `list_all_banks` merged into `get_bank_sector_info`.
- `calculate_growth_metrics` removed in favor of pre-calculated drivers.
- Sector performance consolidated into `query_historical_data` (no separate tool).

### Upcoming Opportunities
- Evaluate whether commentary + earnings drivers can share a single narrative payload.
- Consider pre-warming consensus summaries for heavily-used tickers to reduce recompute cost.

## Error Handling

### Common Issues and Solutions

1. **"No data found"**
   - Verify ticker exists in `dbo.BankingMetrics` (`get_bank_sector_info()` is the quickest check)
   - Check period format (YYYY-Q# or YYYY)
   - Ensure SQL credentials (`TARGET_DB_CONNECTION_STRING`) point to the refreshed warehouse

2. **Sector ticker issues**
   - Use exact case: "Sector", not "SECTOR"
   - Private sectors: "Private_1", not "PRIVATE_1"

3. **YTD queries**
   - Format: "2025-YTD"
   - Automatically switches to quarterly frequency
   - Returns all completed quarters in the year

4. **Tool timeout**
   - Large queries may timeout
   - Break into smaller batches
   - Use specific metrics instead of "all"

## Troubleshooting

### Debug Mode
Enable logging by uncommenting debug statements in Banking_MCP.py:
```python
# print(f"DEBUG: Initial data loaded - {len(df)} rows")
```

### Tool Execution Monitoring
The Streamlit UI shows:
- Tool execution order
- Parameters passed
- Success/failure status
- Result summaries
- Execution time

### Cache Inspection
Check session state in Streamlit:
- `st.session_state.tool_cache` - Cached results
- `st.session_state.tool_executions` - Execution history
- `st.session_state.conversation_history` - Compressed chat history

## Future Enhancements

### Immediate Priorities
1. ✓ Consensus, technical, and scenario tooling delivered across MCP + dashboards
2. Implement streaming responses
3. Add batch processing for large queries

### Medium Term
1. Vietnamese language support
2. Advanced visualizations
3. Export functionality (PDF/Excel)
4. Real-time data integration

### Long Term
1. Machine learning predictions
2. Alert system for significant changes
3. Mobile application
4. Voice interface support
