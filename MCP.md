# MCP (Model Context Protocol) Banking Analysis System

## Overview

The MCP Banking Analysis System integrates OpenAI's GPT models with your Vietnamese banking data to provide intelligent, context-aware analysis. The system allows OpenAI to access multiple specialized tools and chain them together to answer complex banking questions.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Streamlit UI (pages/9_MCP_Model.py)   │
│  - Chat interface                                │
│  - Tool execution visualization                  │
│  - Results display                               │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│         OpenAI Integration Layer                 │
│  - Manages conversation flow                     │
│  - Handles multiple tool calls                   │
│  - Chains tools until answer is complete         │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│      Tool System (utilities/Banking_MCP.py)      │
│  - Modular tool definitions                      │
│  - Data access layer                             │
│  - Analysis functions                            │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│              Data Layer                          │
│  - dfsectoryear.csv (Historical yearly)          │
│  - dfsectorquarter.csv (Historical quarterly)    │
│  - dfsectorforecast.csv (2025-2026 forecasts)   │
│  - banking_comments.xlsx (AI commentary)         │
│  - quarterly_analysis_results.xlsx               │
│  - Valuation_banking.csv                         │
└──────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Tool System

Tools are functions that OpenAI can call to access banking data. Each tool:
- Has a unique name and description
- Defines input parameters with JSON schema
- Returns structured data that OpenAI can interpret

### 2. Tool Chaining

OpenAI can call unlimited tools in sequence to answer complex questions:
1. First call `get_data_availability()` to understand what data is available
2. Then call `query_historical_data()` to get specific metrics
3. Finally call `calculate_growth_metrics()` to compute growth rates
4. Continue calling as many tools as needed until the analysis is complete

The system allows up to 50 tool calls per query (effectively unlimited for practical purposes) to ensure comprehensive analysis without artificial restrictions.

### 3. Parallel Tool Calls

OpenAI can request multiple tools simultaneously for efficiency:
- Get data for multiple banks at once
- Query different time periods in parallel
- Fetch both historical and forecast data together

## Available Tools

### Data Discovery Tools

#### `get_data_availability()`
Returns current date and available data periods.
- **No parameters required**
- **Returns**: Latest quarters, years, forecast periods

#### `get_bank_info(ticker)`
Get bank sector classification and basic information.
- **Parameters**: 
  - `ticker` (string): Bank ticker (e.g., "VCB", "ACB")
- **Returns**: Sector, bank type, basic info

#### `list_all_banks()`
List all available banks with their sectors.
- **No parameters required**
- **Returns**: List of all banks grouped by sector

### Data Query Tools

#### `query_historical_data(ticker, period, metric_group)`
Query historical banking metrics.
- **Parameters**:
  - `ticker` (string, optional): Bank ticker or sector
  - `period` (string, optional): Period like "2024-Q3" or "2024"
  - `metric_group` (string, optional): "all", "profitability", "asset_quality", "growth"
- **Returns**: DataFrame with requested metrics

#### `query_forecast_data(ticker, year)`
Query forecast data for 2025-2026.
- **Parameters**:
  - `ticker` (string, optional): Bank ticker or sector
  - `year` (string, optional): "2025" or "2026"
- **Returns**: Forecast metrics

### Analysis Tools

#### `calculate_growth_metrics(ticker, metric, periods)`
Calculate YoY, QoQ growth rates.
- **Parameters**:
  - `ticker` (string): Bank ticker
  - `metric` (string): Metric name (e.g., "Loan", "Deposit")
  - `periods` (integer): Number of periods
- **Returns**: Growth rates and trends

#### `get_valuation_analysis(ticker, metric)`
Get valuation statistics with Z-scores.
- **Parameters**:
  - `ticker` (string): Bank ticker
  - `metric` (string): "PE", "PB", or "PS"
- **Returns**: Current value, historical stats, Z-score, percentile

#### `compare_banks(tickers, metrics, period)`
Compare multiple banks on specific metrics.
- **Parameters**:
  - `tickers` (array): List of bank tickers
  - `metrics` (array): List of metrics to compare
  - `period` (string): Period for comparison
- **Returns**: Comparison table

#### `get_ai_commentary(ticker, quarter)`
Get AI-generated qualitative analysis.
- **Parameters**:
  - `ticker` (string): Bank ticker or "Sector"
  - `quarter` (string): Quarter like "2024-Q3"
- **Returns**: Qualitative analysis text

#### `get_stock_performance(ticker, start_date, end_date)`
Get stock price performance between two dates.
- **Parameters**:
  - `ticker` (string): Stock ticker symbol (e.g., "VPB", "VCB")
  - `start_date` (string): Start date in YYYY-MM-DD format
  - `end_date` (string): End date in YYYY-MM-DD format
- **Returns**: Starting price, ending price, and performance percentage

## Adding New Tools

To add a new tool, follow these steps:

### 1. Define the Tool in Banking_MCP.py

```python
@tool(
    name="your_tool_name",
    description="Clear description of what the tool does",
    parameters={
        "param1": {"type": "string", "description": "Parameter description"},
        "param2": {"type": "number", "description": "Another parameter", "required": False}
    }
)
def your_tool_name(self, param1: str, param2: float = None) -> Dict:
    """
    Implementation of your tool
    """
    # Access data
    df = self.data['historical']
    
    # Process data
    result = df[df['TICKER'] == param1]
    
    # Return structured result
    return {
        "status": "success",
        "data": result.to_dict(),
        "message": "Tool executed successfully"
    }
```

### 2. The Tool Decorator Automatically:
- Registers the tool with OpenAI
- Validates parameters
- Handles errors
- Formats responses

### 3. Tool Design Best Practices:
- Keep tools focused on a single task
- Return structured data (dicts, lists)
- Include helpful error messages
- Document parameters clearly
- Make parameters optional when sensible

## Usage Examples

### Example 1: Simple Query
**User**: "What is VCB's NPL ratio for 2024-Q3?"

**System Flow**:
1. OpenAI calls `get_data_availability()` → Gets latest periods
2. OpenAI calls `query_historical_data("VCB", "2024-Q3", "asset_quality")` → Gets NPL data
3. OpenAI formulates answer with specific NPL ratio

### Example 2: Comparison Query
**User**: "Compare the profitability of all Private_1 banks in 2024"

**System Flow**:
1. OpenAI calls `get_bank_info()` for sector components
2. OpenAI calls `compare_banks(["VCB", "CTG", "BID"], ["ROA", "ROE", "NIM"], "2024")`
3. OpenAI analyzes results and provides comparison

### Example 3: Complex Analysis
**User**: "Which bank has the best valuation and growth prospects?"

**System Flow**:
1. OpenAI calls `list_all_banks()` → Gets all banks
2. OpenAI calls `get_valuation_analysis()` for each bank (parallel)
3. OpenAI calls `query_forecast_data()` for growth prospects
4. OpenAI calls `get_ai_commentary()` for qualitative insights
5. OpenAI synthesizes all data into recommendation

### Example 4: Stock Performance Query
**User**: "What's the YTD price performance for VPB?"

**System Flow**:
1. OpenAI calls `get_data_availability()` → Gets current date (2024-08-25)
2. OpenAI determines YTD start date → 2023-12-31 (last day of previous year)
3. OpenAI calls `get_stock_performance("VPB", "2023-12-31", "2024-08-25")`
4. OpenAI presents result: "VPB has increased 13.51% YTD, from 18,500 VND to 21,000 VND"

## Streamlit Integration

The system is fully integrated with Streamlit:

### Features:
1. **Chat Interface**: Natural conversation with context retention
2. **Tool Execution Display**: See which tools are being called
3. **Progress Indicators**: Visual feedback during processing
4. **Results Formatting**: Tables, charts, and formatted text
5. **History Management**: Save and review past conversations
6. **Export Options**: Download analysis results

### UI Components:
- Chat input box
- Message history display
- Tool execution log
- Results panel with tabs for different data types
- Settings sidebar for model configuration

## Configuration

### Environment Variables (.env file):
```
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4-turbo-preview
ENABLE_TOOL_LOGGING=true
```

### Settings:
- **Model Selection**: Choose between GPT-4, GPT-4-Turbo, GPT-3.5
- **Temperature**: Control response creativity (0.0 - 1.0)
- **Max Tokens**: Limit response length
- **Tool Timeout**: Maximum execution time per tool

## Error Handling

The system includes robust error handling:

1. **Data Availability Checks**: Verify data exists before querying
2. **Parameter Validation**: Ensure valid inputs for each tool
3. **Graceful Failures**: Return helpful error messages
4. **Retry Logic**: Automatic retries for transient failures
5. **Fallback Responses**: Provide partial answers when possible

## Performance Optimization

### Caching Strategy:
- Cache frequently accessed data in memory
- Store tool results for repeated queries
- Implement TTL (Time To Live) for cache entries

### Efficient Tool Calls:
- Batch similar queries together
- Use parallel tool calls when possible
- Minimize data transfer between tools

## Security Considerations

1. **API Key Management**: Never expose OpenAI API keys in code
2. **Input Sanitization**: Validate all user inputs
3. **Rate Limiting**: Implement request throttling
4. **Data Access Control**: Restrict access to sensitive data
5. **Audit Logging**: Track all tool executions

## Troubleshooting

### Common Issues:

1. **"No data found"**: Check data file paths and formats
2. **"Tool timeout"**: Increase timeout or optimize query
3. **"Invalid parameters"**: Verify parameter types and values
4. **"API rate limit"**: Implement backoff strategy

### Debug Mode:
Enable verbose logging to see:
- Raw OpenAI requests/responses
- Tool execution details
- Data query results
- Error stack traces

## Future Enhancements

Potential improvements to consider:

1. **Advanced Analytics**: Statistical models, ML predictions
2. **Custom Visualizations**: Interactive charts and graphs
3. **Report Generation**: Automated PDF/Excel reports
4. **Alerting System**: Notifications for significant changes
5. **Multi-language Support**: Vietnamese language interface
6. **Voice Interface**: Speech-to-text input
7. **Mobile App**: Responsive design for mobile devices