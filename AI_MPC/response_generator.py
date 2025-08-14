#%% Import libraries
from typing import Dict, Any

def generate_quantitative_response(user_question: str, data_result: Dict[str, Any], valuation_data_text: str, 
                                  client, model: str, temperature: float) -> str:
    """
    Generate quantitative response using OpenAI
    
    Args:
        user_question: The user's question
        data_result: Dictionary containing the data table
        valuation_data_text: Formatted valuation data (if applicable)
        client: OpenAI client instance
        model: Model name to use
        temperature: Temperature setting for response
    
    Returns:
        Generated response string
    """
    
    # Create prompt with question and data
    enhanced_prompt = f"""
Question: {user_question}

Data Table:
{data_result['data_table']}{valuation_data_text}

Instructions:
- Give a concise and punchy answer. If asked for data only provide the most relevant data.
- Convert decimals to percentages (0.02 = 2%, 0.134 = 13.4%)
- Round numbers appropriately (billions, millions, percentages to 1 decimal)
- Be direct and specific with bank names and numbers
"""
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise banking analyst. Give short, punchy answers with properly formatted numbers. Convert decimals to percentages, use billions/millions for large numbers. Maximum 2-3 sentences."},
            {"role": "user", "content": enhanced_prompt}
        ],
        temperature=temperature
    )
    
    return response.choices[0].message.content


def generate_qualitative_response(user_question: str, qualitative_data: str, valuation_data_text: str,
                                 client, model: str, temperature: float) -> str:
    """
    Generate qualitative response using OpenAI
    
    Args:
        user_question: The user's question
        qualitative_data: Combined qualitative data for all tickers
        valuation_data_text: Formatted valuation data (if applicable)
        client: OpenAI client instance
        model: Model name to use
        temperature: Temperature setting for response
    
    Returns:
        Generated response string
    """
    
    # Create qualitative prompt
    qual_prompt = f"""
Question: {user_question}

Available Analysis and Commentary:
{qualitative_data}{valuation_data_text}

Instructions:
- Open with a concise conclusion of key findings, afterward followed with detailed analysis
- Give a concise and punchy answer. If asked for data only provide the most relevant data.
- Use specific examples and data points from the analysis
- Convert decimals to percentages (0.02 = 2%, 0.134 = 13.4%)
- Be punchy and assertive, max 2 paragraphs. Don't divert from the question
- Reference specific quarters and banks when relevant
"""
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a senior banking analyst writing comprehensive sector analysis. Draw insights from the provided commentary and analysis to answer questions with depth and nuance."},
            {"role": "user", "content": qual_prompt}
        ],
        temperature=temperature
    )
    
    return response.choices[0].message.content