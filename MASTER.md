# Banking Analysis Master Guide

This master document summarizes the full architecture, data flow, tools, workflows, and conventions of the Vietnamese Banking Analysis project.

## 1) Overview
- Purpose: Financial data visualization plus AI analysis powered by OpenAI.
- Flow: Source SQL Server → curated warehouse tables → Streamlit/MCP tools (Parquet files now legacy-only).
- Scope: Quarterly and yearly banking metrics, sector aggregates, valuation, price performance, and AI commentary.

## 2) Quick Start
```bash
# 1) Install dependencies
pip install -r requirements.txt

# 2) Environment
# .env file at project root (or Streamlit secrets)
# OPENAI_API_KEY=your_api_key_here
# SOURCE_DB_CONNECTION_STRING="SERVER=tcp:...;DATABASE=...;UID=...;PWD=...;Connection Timeout=30;"
# TARGET_DB_CONNECTION_STRING="SERVER=tcp:...;DATABASE=...;UID=...;PWD=...;Connection Timeout=30;"
# (Optional) OPENAI_MODEL=gpt-5

# 3) Prepare data (generates Parquet)
python scripts/prepare_data.py
python scripts/Prepare_earnings_driver.py
python scripts/prepare_valuation.py

# 4) Run Streamlit dashboard
streamlit run streamlit_app.py

# 5) Run generators (unified)
python scripts/run_generators.py
```

## 3) Project Structure (Key Paths)
```
.
├── streamlit_app.py                 # Main Streamlit app entry
├── requirements.txt                 # Python deps
├── .env                             # Environment variables (local)
│
├── Data/                            # Legacy reference files (parquet/Excel)
│   ├── Bank_Type.xlsx               # Legacy lookups (still used by ETL scripts)
│   ├── Key_items.xlsx               # Metric mapping
│   └── *.parquet                    # Historical exports (no longer primary source)
│
├── generators/
│   ├── bulk_comment_generator.py
│   └── bulk_quarterly_analysis_generator.py
│
├── pages/                           # Streamlit multi-page UI
│   ├── 1_Banking_Plot.py
│   ├── 2_Company_Table.py
│   ├── 3_OpenAI_Comment.py
│   ├── 4_Comment_Management.py
│   └── 5_Quarterly_Analysis.py
│
├── scripts/
│   ├── run_generators.py            # Unified generator runner
│   ├── prepare_data.py              # Data prep → Parquet
│   ├── Prepare_earnings_driver.py   # Earnings drivers → Parquet
│   └── prepare_valuation.py         # Valuation → Parquet
│
└── utilities/
    ├── __init__.py
    ├── quarter_utils.py             # Quarter parsing/sorting
    ├── path_utils.py                # OS-aware path helpers
    ├── banking_analysis.py          # Metric calculations
    ├── banking_table.py             # Table builders
    ├── plot_chart.py                # Chart helpers
    ├── openai_utils.py              # OpenAI client & prompts
    ├── openai_comments.py           # Comment generation logic
    └── Banking_MCP.py               # MCP tools
```

Notes:
- Parquet is the primary format for performance. Legacy CSV/XLSX may remain for reference.
- Cross-platform paths handled via `utilities/path_utils.py` (Windows path defaults vs current working directory on Mac/Linux).

## 4) Data Model & Conventions
- Quarter format: `XQyy` (e.g., `1Q24` for Q1 2024).
- Sector tickers: `Sector`, `SOCB`, `Private_1`, `Private_2`, `Private_3` (can mix with bank tickers in queries).
- Generated caches:
  - `banking_comments.parquet`: TICKER/SECTOR, QUARTER, COMMENT, GENERATED_DATE
  - `quarterly_analysis_results.parquet`: QUARTER, BANK_COUNT, KEY_CHANGES, INDIVIDUAL_HIGHLIGHTS, FORWARD_OUTLOOK, FULL_ANALYSIS, GENERATED_DATE

**Warehouse tables (primary data source)**

> Full schema, column descriptions, and table relationships live in `DATABASE_SCHEMA.md`. Always refer there when exploring or onboarding new data tables.

- `dbo.BankingMetrics` – quarterly & yearly fundamentals; key `(TICKER, YEARREPORT, LENGTHREPORT)`, `PERIOD_TYPE` distinguishes `Q`/`Y`.
- `dbo.BankingForecast` – forecast rows (typically next two years); key `(TICKER, YEARREPORT, LENGTHREPORT)`.
- `dbo.Valuation` / `dbo.ValuationBanking` – raw valuation pull and cleaned banking subset; key `(TICKER, TRADE_DATE)`.
- `dbo.FA_Quarterly`, `dbo.FA_Annual` – legacy financial statements stored in warehouse for completeness.
- `dbo.Banking_Comments`, `dbo.QuarterlyAnalysis` – AI commentary caches migrated from parquet files.
- `_load_earnings_quality_*` tables (quarterly/yearly) – earnings driver impacts used by MCP tools.

All connection handling is centralized in `utilities/db.py` using `pymssql`. Connection strings may still contain `DRIVER=...` segments (for backward compatibility) but only `SERVER`, `DATABASE`, `UID`, `PWD`, `Connection Timeout`, and optional `ssl`/`TDS_Version` values are consumed. For table-specific details, consult `DATABASE_SCHEMA.md`.

## 5) Core Utilities (How Things Work)
- `quarter_utils.py`: Convert/sort quarters; numeric encodings for ordering and ranges.
- `path_utils.py`: Resolve project root and standardized `Data/` paths.
- `banking_analysis.py`: Simple, transparent banking formulas; vectorized pandas operations.
- `banking_table.py` / `plot_chart.py`: Display helpers for tables and charts.
- `openai_utils.py`: OpenAI client, prompt templates, caching wrappers.
- `openai_comments.py`: Constructs comment and sector analysis prompts.
- `Banking_MCP.py`: Registers MCP tools with lazy loading + TTL result cache.

## 6) MCP Tool Catalog (8 Active)
All tools follow the same pattern: lazy data load, universal single/multi-entity support, structured dict returns, 5-minute result TTL.

1. get_data_availability
   - Purpose: Discover available periods and coverage.
   - Notes: Helps the model validate queries before expensive calls.

2. get_bank_sector_info
   - Purpose: Bank tickers and sector membership; expands sector → component banks.

3. query_historical_data
   - Purpose: Historical metrics (quarterly/yearly).
   - Supports: `tickers`, `period` (e.g., `2024-Q3` or `2025-YTD`), `metric` or `metric_group`.
   - Special: Sector tickers; YTD expansion to completed quarters.

4. query_forecast_data
   - Purpose: 2025–2026 forecasts plus latest actuals; returns all forecast years.

5. get_commentary
   - Purpose: AI-generated commentary per bank or sector.
   - Source: `banking_comments.parquet`, `quarterly_analysis_results.parquet`.

6. get_valuation_analysis
   - Purpose: PB/PE valuation vs historical stats with Z-score & percentile.
   - Source: `Valuation_banking.parquet`.

7. get_stock_performance
   - Purpose: Price performance between dates (TCBS API).

8. get_earnings_drivers
   - Purpose: Driver decomposition for PBT growth (QoQ/YoY/T12M).
   - Source: `earnings_quality_quarterly.parquet`, `earnings_quality_yearly.parquet`.

## 7) Typical Workflows
- Prepare data (first-time or when source updates)
  - Run `scripts/prepare_data.py`, `scripts/Prepare_earnings_driver.py`, `scripts/prepare_valuation.py`.

- Generate AI outputs
  - Use `scripts/run_generators.py` for unified runs, or run individual generator scripts in `generators/`.

- Explore in UI
  - Launch `streamlit_app.py` for plots, company tables, comment tools, management, and sector analysis.

## 8) Performance & Caching
- Parquet migration: 5–10x load speed, 50–75% space reduction.
- Lazy loading for data files; LRU caches for loaders; 5-minute TTL for tool results.
- Recommended next improvements:
  - Streaming responses, asyncio parallel tool execution.
  - Redis-based persistent cache across sessions.
  - Prompt compression for lower latency and cost.
  - Pre-computed aggregations for hot queries.

## 9) Environment & Configuration
- `.env` variables
  - `OPENAI_API_KEY` (required)
  - `OPENAI_MODEL` (optional; default GPT-5 if configured)
- Cross-platform paths
  - Windows baseline path: `C:\\Users\\ducle\\OneDrive\\Work-related\\VS - Code project`
  - Mac/Linux: current working directory (resolved via `path_utils`)

## 10) Coding Standards (Important)
These are enforced by convention across utilities, pages, and generators:

1) No brittle fallbacks
   - Do not hardcode fixed time windows or magic numbers.
   - Accept flexible date/quarter inputs; infer ranges programmatically.

2) Prefer vectorization over loops
   - Use pandas vectorized ops and groupby/agg pipelines.
   - Avoid per-row for-loops; use `.assign`, `.pipe`, `.eval`, `.where`.

3) Jupyter cell markers
   - Place `#%%` at the start of Python modules and before logical sections to support interactive execution in VS Code.

4) Simple, transparent formulas
   - Keep metric calculations readable and business-logic aligned.
   - Use descriptive names consistent with financial terminology.

5) Structured returns and error handling
   - Return dicts with `status`, `data`, `records` (as applicable).
   - For errors: `{ "status": "failed", "error": "message" }`.

## 11) Troubleshooting
- File not found / missing Parquet
  - Run the three data prep scripts to regenerate all Parquet files.
  - Ensure `pyarrow` is installed for Parquet IO.

- Sector ticker casing
  - Use exact labels (`Sector`, `SOCB`, `Private_1`, etc.).

- YTD queries
  - Use `YYYY-YTD`; expands to available completed quarters.

- Timeouts / large queries
  - Prefer specific `metric`/`metric_group` and smaller ticker sets.

## 12) Maintenance
- Weekly: Review cache hit rates; analyze slow tool calls; adjust prompts.
- Monthly: Refresh Parquet files; prune logs; validate aggregations.
- Quarterly: Load test; revisit architecture and hot paths.

## 13) Future Roadmap (High Value)
- Streaming responses in UI; progress indicators.
- Parallel tool execution via asyncio.
- Redis caching across sessions.
- Advanced visualizations; export (PDF/Excel); Vietnamese language support.
- ML-based predictions; alerting; real-time data; mobile/voice.

---
Authoritative references: README.md, CLAUDE.md, MCP.md, PERFORMANCE_OPTIMIZATION.md, PARQUET_MIGRATION_SUMMARY.md
