"""
Banking MCP Tool System
Provides modular tools for OpenAI to access and analyze banking data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import json
from functools import wraps
from scipy import stats
import requests
from datetime import datetime, timedelta


class BankingToolSystem:
    """
    Modular tool system for banking analysis
    Easy to extend with new tools using decorator pattern
    """
    
    def __init__(self, data_dir: Path = None):
        """Initialize the tool system with data"""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "Data"
        
        self.data_dir = data_dir
        self.tools = {}
        self.tool_schemas = []
        self.data = {}
        
        # Load all data files
        self._load_data()
        
        # Register all tools
        self._register_tools()
    
    def _load_data(self):
        """Load all necessary data files"""
        try:
            # Load main data files with descriptive column names
            self.data['historical_year'] = pd.read_csv(self.data_dir / 'dfsectoryear.csv')
            self.data['historical_quarter'] = pd.read_csv(self.data_dir / 'dfsectorquarter.csv')
            self.data['forecast'] = pd.read_csv(self.data_dir / 'dfsectorforecast.csv')
            
            # Load reference data
            self.data['bank_types'] = pd.read_excel(self.data_dir / 'Bank_Type.xlsx')
            self.data['key_items'] = pd.read_excel(self.data_dir / 'Key_items.xlsx')
            
            # Load AI-generated content
            if (self.data_dir / 'banking_comments.xlsx').exists():
                self.data['comments'] = pd.read_excel(self.data_dir / 'banking_comments.xlsx')
            
            if (self.data_dir / 'quarterly_analysis_results.xlsx').exists():
                self.data['quarterly_analysis'] = pd.read_excel(self.data_dir / 'quarterly_analysis_results.xlsx')
            
            # Load valuation data if available
            if (self.data_dir / 'Valuation_banking.csv').exists():
                self.data['valuation'] = pd.read_csv(self.data_dir / 'Valuation_banking.csv')
            
            print(f"Loaded data: {list(self.data.keys())}")
            
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            raise
    
    def tool(self, name: str, description: str, parameters: Dict = None):
        """
        Decorator to register a tool with OpenAI schema
        Makes it easy to add new tools
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    return {
                        "error": f"Error in {name}: {str(e)}",
                        "status": "failed"
                    }
            
            # Register the tool
            self.tools[name] = wrapper
            
            # Create OpenAI function schema
            # Clean parameters by removing 'required' field from individual params
            clean_params = {}
            required_params = []
            
            if parameters:
                for param_name, param_def in parameters.items():
                    # Check if this parameter is required (default True if not specified)
                    is_required = param_def.get("required", True)
                    if is_required:
                        required_params.append(param_name)
                    
                    # Create clean parameter definition without 'required' field
                    clean_param = {k: v for k, v in param_def.items() if k != "required"}
                    clean_params[param_name] = clean_param
            
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": clean_params,
                        "required": required_params
                    }
                }
            }
            self.tool_schemas.append(schema)
            
            return wrapper
        return decorator
    
    def _register_tools(self):
        """Register all available tools"""
        
        # Tool 1: Get Data Availability
        @self.tool(
            name="get_data_availability",
            description="Get current date and latest available data periods - ALWAYS call this first for 'latest' or 'current' queries",
            parameters={}
        )
        def get_data_availability() -> Dict:
            """Get available data periods"""
            quarterly = self.data['historical_quarter']
            yearly = self.data['historical_year']
            forecast = self.data['forecast']
            
            # Get unique periods
            q_periods = sorted(quarterly['Date_Quarter'].unique())[-8:]
            y_periods = sorted(yearly['Year'].unique())[-5:]
            f_periods = sorted(forecast['Year'].unique())
            
            return {
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "latest_quarterly": q_periods[-1] if q_periods else None,
                "latest_yearly": str(y_periods[-1]) if y_periods else None,
                "recent_quarters": q_periods,
                "recent_years": [str(y) for y in y_periods],
                "forecast_years": [str(y) for y in f_periods],
                "status": "success"
            }
        
        # Tool 2: Get Bank Information
        @self.tool(
            name="get_bank_info",
            description="Get bank sector classification and basic information",
            parameters={
                "ticker": {"type": "string", "description": "Bank ticker symbol (e.g., VCB, ACB)"}
            }
        )
        def get_bank_info(ticker: str) -> Dict:
            """Get bank sector and info"""
            ticker = ticker.upper()
            bank_types = self.data['bank_types']
            
            bank_info = bank_types[bank_types['TICKER'] == ticker]
            if bank_info.empty:
                return {"error": f"Bank {ticker} not found", "status": "failed"}
            
            sector = bank_info.iloc[0]['Type']
            
            # Get latest metrics
            yearly = self.data['historical_year']
            latest = yearly[yearly['TICKER'] == ticker].iloc[-1] if not yearly[yearly['TICKER'] == ticker].empty else None
            
            result = {
                "ticker": ticker,
                "sector": sector,
                "status": "success"
            }
            
            if latest is not None:
                result.update({
                    "latest_year": str(latest['Year']),
                    "total_assets": latest.get('Total Assets', None),
                    "total_equity": latest.get('Total Equity', None),
                    "loan": latest.get('Loan', None),
                    "deposit": latest.get('Deposit', None)
                })
            
            return result
        
        # Tool 3: List All Banks
        @self.tool(
            name="list_all_banks",
            description="List all available banks grouped by sector",
            parameters={}
        )
        def list_all_banks() -> Dict:
            """List all banks by sector"""
            bank_types = self.data['bank_types']
            
            sectors = {}
            for sector in bank_types['Type'].unique():
                banks = bank_types[bank_types['Type'] == sector]['TICKER'].tolist()
                sectors[sector] = banks
            
            return {
                "sectors": sectors,
                "total_banks": len(bank_types),
                "status": "success"
            }
        
        # Tool 4: Query Historical Data
        @self.tool(
            name="query_historical_data",
            description="Query historical banking metrics",
            parameters={
                "ticker": {"type": "string", "description": "Bank ticker or sector name", "required": False},
                "period": {"type": "string", "description": "Period like 2024-Q3 or 2024", "required": False},
                "metric_group": {
                    "type": "string", 
                    "description": "Metric group: all, profitability, asset_quality, growth",
                    "enum": ["all", "profitability", "asset_quality", "growth"],
                    "required": False
                }
            }
        )
        def query_historical_data(ticker: str = None, period: str = None, metric_group: str = "all") -> Dict:
            """Query historical data"""
            # Determine if quarterly or yearly
            is_quarterly = period and 'Q' in period
            df = self.data['historical_quarter'] if is_quarterly else self.data['historical_year']
            
            # Apply filters
            if ticker:
                ticker = ticker.upper()
                df = df[df['TICKER'] == ticker]
            
            if period:
                if is_quarterly:
                    df = df[df['Date_Quarter'] == period]
                else:
                    df = df[df['Year'] == int(period)]
            
            if df.empty:
                return {"error": "No data found", "status": "failed"}
            
            # Select metrics based on group
            metric_groups = {
                "profitability": ["ROA", "ROE", "NIM", "CIR"],
                "asset_quality": ["NPL", "NPL Coverage ratio", "Provision/ Total Loan", "GROUP 2"],
                "growth": ["Loan", "Deposit", "Total Assets", "NPATMI"]
            }
            
            if metric_group != "all":
                metrics = metric_groups.get(metric_group, [])
                available_metrics = [m for m in metrics if m in df.columns]
                if available_metrics:
                    id_cols = ['TICKER', 'Year' if 'Year' in df.columns else 'Date_Quarter']
                    df = df[id_cols + available_metrics]
            
            # Return summary
            return {
                "records": len(df),
                "data": df.head(10).to_dict('records'),
                "columns": df.columns.tolist(),
                "status": "success"
            }
        
        # Tool 5: Query Forecast Data
        @self.tool(
            name="query_forecast_data",
            description="Query forecast data for 2025-2026",
            parameters={
                "ticker": {"type": "string", "description": "Bank ticker or sector", "required": False},
                "year": {"type": "string", "description": "2025 or 2026", "required": False}
            }
        )
        def query_forecast_data(ticker: str = None, year: str = None) -> Dict:
            """Query forecast data"""
            df = self.data['forecast'].copy()
            
            if ticker:
                ticker = ticker.upper()
                df = df[df['TICKER'] == ticker]
            
            if year:
                df = df[df['Year'] == int(year)]
            
            if df.empty:
                return {"error": "No forecast data found", "status": "failed"}
            
            # Key forecast metrics
            key_metrics = ["Loan", "Deposit", "NPL", "ROA", "ROE", "NIM", "NPATMI"]
            available = [m for m in key_metrics if m in df.columns]
            
            return {
                "records": len(df),
                "data": df[['TICKER', 'Year'] + available].to_dict('records'),
                "status": "success"
            }
        
        # Tool 6: Calculate Growth Metrics
        @self.tool(
            name="calculate_growth_metrics",
            description="Calculate growth rates for metrics",
            parameters={
                "ticker": {"type": "string", "description": "Bank ticker"},
                "metric": {"type": "string", "description": "Metric name (e.g., Loan, Deposit)"},
                "periods": {"type": "integer", "description": "Number of periods to analyze", "required": False}
            }
        )
        def calculate_growth_metrics(ticker: str, metric: str, periods: int = 5) -> Dict:
            """Calculate growth metrics"""
            ticker = ticker.upper()
            
            # Get historical data
            df = self.data['historical_year']
            bank_data = df[df['TICKER'] == ticker].sort_values('Year').tail(periods + 1)
            
            if bank_data.empty or metric not in bank_data.columns:
                return {"error": f"No data for {ticker} or metric {metric}", "status": "failed"}
            
            # Calculate growth rates
            values = bank_data[metric].values
            years = bank_data['Year'].values
            
            growth_rates = []
            for i in range(1, len(values)):
                if values[i-1] != 0:
                    growth = ((values[i] - values[i-1]) / values[i-1]) * 100
                    growth_rates.append({
                        "year": int(years[i]),
                        "value": float(values[i]),
                        "growth_rate": float(growth)
                    })
            
            # Calculate CAGR if possible
            if len(values) >= 2 and values[0] > 0:
                n_years = len(values) - 1
                cagr = (pow(values[-1] / values[0], 1/n_years) - 1) * 100
            else:
                cagr = None
            
            return {
                "ticker": ticker,
                "metric": metric,
                "growth_data": growth_rates,
                "cagr": cagr,
                "average_growth": np.mean([g["growth_rate"] for g in growth_rates]) if growth_rates else None,
                "status": "success"
            }
        
        # Tool 7: Get Valuation Analysis
        @self.tool(
            name="get_valuation_analysis",
            description="Get valuation statistics with Z-score and percentiles",
            parameters={
                "ticker": {"type": "string", "description": "Bank ticker"},
                "metric": {
                    "type": "string", 
                    "description": "Valuation metric",
                    "enum": ["PE", "PB", "PS"],
                    "required": False
                }
            }
        )
        def get_valuation_analysis(ticker: str, metric: str = "PB") -> Dict:
            """Get valuation analysis"""
            if 'valuation' not in self.data:
                return {"error": "Valuation data not available", "status": "failed"}
            
            ticker = ticker.upper()
            df = self.data['valuation']
            
            # Map metric names
            metric_map = {
                "PE": "PE_RATIO",
                "PB": "PX_TO_BOOK_RATIO", 
                "PS": "PX_TO_SALES_RATIO"
            }
            
            col_name = metric_map.get(metric, "PX_TO_BOOK_RATIO")
            
            if col_name not in df.columns:
                return {"error": f"Metric {metric} not found", "status": "failed"}
            
            bank_data = df[df['TICKER'] == ticker][col_name].dropna()
            
            if bank_data.empty:
                return {"error": f"No valuation data for {ticker}", "status": "failed"}
            
            current = bank_data.iloc[-1]
            mean = bank_data.mean()
            std = bank_data.std()
            
            z_score = (current - mean) / std if std != 0 else 0
            percentile = stats.percentileofscore(bank_data, current)
            
            return {
                "ticker": ticker,
                "metric": metric,
                "current_value": float(current),
                "mean": float(mean),
                "median": float(bank_data.median()),
                "std": float(std),
                "z_score": float(z_score),
                "percentile_rank": float(percentile),
                "min": float(bank_data.min()),
                "max": float(bank_data.max()),
                "interpretation": "Undervalued" if z_score < -1 else "Overvalued" if z_score > 1 else "Fair valued",
                "status": "success"
            }
        
        # Tool 8: Compare Banks
        @self.tool(
            name="compare_banks",
            description="Compare multiple banks on specific metrics",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers to compare"
                },
                "metrics": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "List of metrics to compare",
                    "required": False
                },
                "period": {"type": "string", "description": "Period for comparison", "required": False}
            }
        )
        def compare_banks(tickers: List[str], metrics: List[str] = None, period: str = None) -> Dict:
            """Compare multiple banks"""
            if not metrics:
                metrics = ["ROA", "ROE", "NPL", "NIM", "Loan", "Deposit"]
            
            tickers = [t.upper() for t in tickers]
            
            # Get data
            df = self.data['historical_year']
            
            if period:
                df = df[df['Year'] == int(period)]
            else:
                # Get latest year for each bank
                df = df.sort_values('Year').groupby('TICKER').last()
                df = df.reset_index()
            
            # Filter for requested banks
            df = df[df['TICKER'].isin(tickers)]
            
            if df.empty:
                return {"error": "No data found for comparison", "status": "failed"}
            
            # Select available metrics
            available_metrics = [m for m in metrics if m in df.columns]
            comparison_df = df[['TICKER'] + available_metrics]
            
            # Calculate rankings
            rankings = {}
            for metric in available_metrics:
                if metric in ["NPL", "CIR"]:  # Lower is better
                    rankings[metric] = comparison_df[metric].rank(ascending=True)
                else:  # Higher is better
                    rankings[metric] = comparison_df[metric].rank(ascending=False)
            
            rankings_df = pd.DataFrame(rankings)
            rankings_df['TICKER'] = comparison_df['TICKER'].values
            
            return {
                "comparison": comparison_df.to_dict('records'),
                "rankings": rankings_df.to_dict('records'),
                "metrics_compared": available_metrics,
                "status": "success"
            }
        
        # Tool 9: Get AI Commentary
        @self.tool(
            name="get_ai_commentary",
            description="Get AI-generated qualitative analysis and commentary",
            parameters={
                "ticker": {"type": "string", "description": "Bank ticker or 'Sector' for sector analysis"},
                "quarter": {"type": "string", "description": "Quarter like 2024-Q3"}
            }
        )
        def get_ai_commentary(ticker: str, quarter: str) -> Dict:
            """Get AI commentary"""
            ticker = ticker.upper()
            
            if ticker == "SECTOR" and 'quarterly_analysis' in self.data:
                # Get sector analysis
                df = self.data['quarterly_analysis']
                analysis = df[df['QUARTER'] == quarter] if 'QUARTER' in df.columns else pd.DataFrame()
                
                if not analysis.empty:
                    return {
                        "type": "sector",
                        "quarter": quarter,
                        "analysis": analysis.iloc[0].to_dict(),
                        "status": "success"
                    }
            elif 'comments' in self.data:
                # Get bank-specific commentary
                df = self.data['comments']
                comment = df[(df['TICKER'] == ticker) & (df['QUARTER'] == quarter)]
                
                if not comment.empty:
                    return {
                        "type": "bank",
                        "ticker": ticker,
                        "quarter": quarter,
                        "comment": comment.iloc[0]['COMMENT'],
                        "generated_at": str(comment.iloc[0].get('GENERATED_AT', '')),
                        "status": "success"
                    }
            
            return {"error": "No commentary found", "status": "failed"}
        
        # Tool 10: Get Sector Performance
        @self.tool(
            name="get_sector_performance",
            description="Get aggregated performance metrics for a sector",
            parameters={
                "sector": {"type": "string", "description": "Sector name (SOCB, Private_1, Private_2, Private_3, Sector)"},
                "period": {"type": "string", "description": "Period for analysis", "required": False}
            }
        )
        def get_sector_performance(sector: str, period: str = None) -> Dict:
            """Get sector performance"""
            df = self.data['historical_year']
            
            # Filter by sector
            if sector != "Sector":
                # Get banks in this sector
                bank_types = self.data['bank_types']
                sector_banks = bank_types[bank_types['Type'] == sector]['TICKER'].tolist()
                df = df[df['TICKER'].isin(sector_banks)]
            else:
                # Use the pre-aggregated Sector row
                df = df[df['TICKER'] == 'Sector']
            
            if period:
                df = df[df['Year'] == int(period)]
            else:
                df = df[df['Year'] == df['Year'].max()]
            
            if df.empty:
                return {"error": f"No data for sector {sector}", "status": "failed"}
            
            # Key sector metrics
            metrics = ["Total Assets", "Loan", "Deposit", "NPL", "ROA", "ROE", "NIM"]
            available = [m for m in metrics if m in df.columns]
            
            if sector != "Sector" and len(df) > 1:
                # Calculate averages for the sector
                result = {
                    "sector": sector,
                    "banks_count": len(df),
                    "period": period or str(df['Year'].iloc[0]),
                    "metrics": {}
                }
                
                for metric in available:
                    result["metrics"][metric] = {
                        "mean": float(df[metric].mean()),
                        "median": float(df[metric].median()),
                        "min": float(df[metric].min()),
                        "max": float(df[metric].max())
                    }
            else:
                # Return the aggregated data
                result = {
                    "sector": sector,
                    "period": period or str(df['Year'].iloc[0]),
                    "data": df[available].iloc[0].to_dict()
                }
            
            result["status"] = "success"
            return result
        
        # Tool 11: Get Stock Performance
        @self.tool(
            name="get_stock_performance",
            description="Get stock price performance between two dates",
            parameters={
                "ticker": {"type": "string", "description": "Stock ticker symbol (e.g., VPB, VCB)"},
                "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"}
            }
        )
        def get_stock_performance(ticker: str, start_date: str, end_date: str) -> Dict:
            """Get stock price performance between two dates"""
            ticker = ticker.upper()
            
            try:
                # Parse dates
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                
                # Calculate days between dates (add some buffer days)
                days_diff = (end_dt - start_dt).days + 30
                
                # TCBS API endpoint
                url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
                
                # Calculate timestamps
                from_timestamp = int((end_dt - timedelta(days=days_diff)).timestamp())
                to_timestamp = int((end_dt + timedelta(days=5)).timestamp())  # Add buffer for end date
                
                # API parameters
                params = {
                    "ticker": ticker,
                    "type": "stock",
                    "resolution": "D",
                    "from": str(from_timestamp),
                    "to": str(to_timestamp)
                }
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                }
                
                # Fetch data
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if 'data' in data and data['data']:
                    # Convert to DataFrame
                    df = pd.DataFrame(data['data'])
                    
                    # Convert timestamp to datetime
                    if 'tradingDate' in df.columns:
                        if df['tradingDate'].dtype == 'object' and isinstance(df['tradingDate'].iloc[0], str) and 'T' in df['tradingDate'].iloc[0]:
                            df['tradingDate'] = pd.to_datetime(df['tradingDate'])
                        else:
                            df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms')
                    
                    # Convert to date only for comparison
                    df['date'] = df['tradingDate'].dt.date
                    
                    # Sort by date
                    df = df.sort_values('date')
                    
                    # Find closest dates to requested dates
                    start_date_obj = start_dt.date()
                    end_date_obj = end_dt.date()
                    
                    # Get data for start date (or closest available)
                    start_data = df[df['date'] <= start_date_obj].tail(1)
                    if start_data.empty:
                        start_data = df.head(1)  # Use first available if no earlier data
                    
                    # Get data for end date (or closest available)
                    end_data = df[df['date'] <= end_date_obj].tail(1)
                    if end_data.empty:
                        end_data = df.tail(1)  # Use last available if no data up to end date
                    
                    if not start_data.empty and not end_data.empty:
                        start_price = float(start_data.iloc[0]['close'])
                        end_price = float(end_data.iloc[0]['close'])
                        start_actual_date = str(start_data.iloc[0]['date'])
                        end_actual_date = str(end_data.iloc[0]['date'])
                        
                        # Calculate performance
                        if start_price > 0:
                            performance_pct = ((end_price - start_price) / start_price) * 100
                        else:
                            performance_pct = 0
                        
                        return {
                            "ticker": ticker,
                            "start_date": start_actual_date,
                            "start_price": start_price,
                            "end_date": end_actual_date,
                            "end_price": end_price,
                            "performance_pct": round(performance_pct, 2),
                            "status": "success"
                        }
                    else:
                        return {"error": "Insufficient data for the requested date range", "status": "failed"}
                else:
                    return {"error": f"No price data available for {ticker}", "status": "failed"}
                    
            except ValueError as e:
                return {"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}", "status": "failed"}
            except requests.exceptions.RequestException as e:
                return {"error": f"Error fetching stock data: {str(e)}", "status": "failed"}
            except Exception as e:
                return {"error": f"Unexpected error: {str(e)}", "status": "failed"}
    
    def execute_tool(self, tool_name: str, arguments: Dict = None) -> Dict:
        """Execute a tool by name with arguments"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}", "status": "failed"}
        
        tool_func = self.tools[tool_name]
        
        # Get the actual function (unwrapped) to inspect parameters
        import inspect
        sig = inspect.signature(tool_func)
        
        # Filter arguments to only include those the function accepts
        filtered_args = {}
        for param_name in sig.parameters:
            if param_name != 'self' and arguments and param_name in arguments:
                filtered_args[param_name] = arguments[param_name]
        
        try:
            result = tool_func(**filtered_args)
            return result
        except Exception as e:
            return {"error": f"Error executing {tool_name}: {str(e)}", "status": "failed"}
    
    def get_openai_tools(self) -> List[Dict]:
        """Get tool schemas for OpenAI"""
        return self.tool_schemas
    
    def get_tool_list(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())


# Helper function to create a singleton instance
_tool_system_instance = None

def get_tool_system() -> BankingToolSystem:
    """Get or create the banking tool system instance"""
    global _tool_system_instance
    if _tool_system_instance is None:
        _tool_system_instance = BankingToolSystem()
    return _tool_system_instance