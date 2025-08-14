#%% Import libraries
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple
import time

def fetch_quantitative_data_parallel(query_analysis: Dict[str, Any], 
                                    discovery_agent,
                                    valuation_formatter=None) -> Dict[str, Any]:
    """
    Fetch quantitative data and valuation data in parallel
    
    Args:
        query_analysis: Parsed query analysis
        discovery_agent: DataDiscoveryAgent instance
        valuation_formatter: Optional function to format valuation data
    
    Returns:
        Dictionary with both data results and valuation data
    """
    results = {
        'data_result': None,
        'valuation_data': ""
    }
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        
        # Submit data discovery task
        future_data = executor.submit(
            discovery_agent.find_relevant_data,
            query_analysis
        )
        futures.append(('data', future_data))
        
        # Submit valuation task if needed
        if query_analysis.get('valuation', False) and valuation_formatter:
            tickers = query_analysis.get('tickers', [])
            if tickers:
                future_val = executor.submit(
                    valuation_formatter,
                    tickers
                )
                futures.append(('valuation', future_val))
        
        # Collect results as they complete
        for task_type, future in futures:
            try:
                if task_type == 'data':
                    results['data_result'] = future.result(timeout=30)
                elif task_type == 'valuation':
                    results['valuation_data'] = future.result(timeout=30)
            except Exception as e:
                print(f"Error in parallel fetch ({task_type}): {str(e)}")
                if task_type == 'data':
                    results['data_result'] = {'data_found': False, 'error': str(e)}
    
    return results


def fetch_qualitative_data_parallel(tickers: List[str], 
                                   timeframe: List[str],
                                   qualitative_handler,
                                   valuation_formatter=None,
                                   need_valuation: bool = False) -> Dict[str, Any]:
    """
    Fetch qualitative data and valuation data in parallel
    
    Args:
        tickers: List of ticker symbols
        timeframe: List of quarters
        qualitative_handler: QualitativeDataHandler instance
        valuation_formatter: Optional function to format valuation data
        need_valuation: Whether to fetch valuation data
    
    Returns:
        Dictionary with qualitative and valuation data
    """
    results = {
        'qualitative_data': "",
        'valuation_data': ""
    }
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        
        # Submit qualitative data collection task
        future_qual = executor.submit(
            collect_qualitative_batch,
            tickers,
            timeframe,
            qualitative_handler
        )
        futures.append(('qualitative', future_qual))
        
        # Submit valuation task if needed
        if need_valuation and valuation_formatter and tickers:
            future_val = executor.submit(
                valuation_formatter,
                tickers
            )
            futures.append(('valuation', future_val))
        
        # Collect results
        for task_type, future in futures:
            try:
                if task_type == 'qualitative':
                    results['qualitative_data'] = future.result(timeout=30)
                elif task_type == 'valuation':
                    results['valuation_data'] = future.result(timeout=30)
            except Exception as e:
                print(f"Error in parallel fetch ({task_type}): {str(e)}")
                if task_type == 'qualitative':
                    results['qualitative_data'] = f"Error fetching qualitative data: {str(e)}"
    
    return results


def collect_qualitative_batch(tickers: List[str], 
                             timeframe: List[str], 
                             qualitative_handler) -> str:
    """
    Helper function to collect qualitative data for batch processing
    Can be optimized further with batch queries
    """
    all_qualitative_data = []
    
    for ticker in tickers:
        is_sector = ticker in ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']
        
        ticker_data = qualitative_handler.format_qualitative_data(
            ticker=ticker,
            timeframe=timeframe,
            is_sector=is_sector
        )
        all_qualitative_data.append(ticker_data)
    
    return "\n\n".join(all_qualitative_data)


async def fetch_all_data_async(query_type: str,
                              query_analysis: Dict[str, Any],
                              handlers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async wrapper for fetching all data types concurrently
    
    Args:
        query_type: 'quantitative' or 'qualitative'
        query_analysis: Parsed query analysis
        handlers: Dictionary of handler instances and functions
    
    Returns:
        Combined results dictionary
    """
    loop = asyncio.get_event_loop()
    
    if query_type == 'quantitative':
        # Run quantitative parallel fetch in executor
        result = await loop.run_in_executor(
            None,
            fetch_quantitative_data_parallel,
            query_analysis,
            handlers.get('discovery_agent'),
            handlers.get('valuation_formatter')
        )
    else:  # qualitative
        # Extract needed data
        tickers = query_analysis.get('tickers', [])
        timeframe = query_analysis.get('timeframe', [])
        need_valuation = query_analysis.get('valuation', False)
        
        # Run qualitative parallel fetch in executor
        result = await loop.run_in_executor(
            None,
            fetch_qualitative_data_parallel,
            tickers,
            timeframe,
            handlers.get('qualitative_handler'),
            handlers.get('valuation_formatter'),
            need_valuation
        )
    
    return result


def benchmark_parallel_vs_sequential(func_parallel, func_sequential, *args):
    """
    Utility function to benchmark parallel vs sequential execution
    
    Args:
        func_parallel: Parallel version of function
        func_sequential: Sequential version of function
        *args: Arguments to pass to both functions
    
    Returns:
        Tuple of (parallel_time, sequential_time, speedup_percentage)
    """
    # Benchmark sequential
    start = time.time()
    result_seq = func_sequential(*args)
    seq_time = time.time() - start
    
    # Benchmark parallel
    start = time.time()
    result_par = func_parallel(*args)
    par_time = time.time() - start
    
    speedup = ((seq_time - par_time) / seq_time) * 100 if seq_time > 0 else 0
    
    return par_time, seq_time, speedup