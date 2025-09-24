This directory contains legacy data files kept for reference or one-off staging.

Primary data now lives in the SQL warehouse tables documented in DATABASE_SCHEMA.md.

Contents may include:
- Historical parquet exports (e.g., dfsectorquarter.parquet) generated during development
- Excel reference files (`Bank_Type.xlsx`, `Key_items.xlsx`) still used by ETL scripts for mapping
- Other archival assets retained for completeness

Treat everything here as optional/offline support files. The production apps and MCP tools read directly from the curated SQL tables.
