import os
import json
import pandas as pd
import talib.abstract as ta
import upstox_client
from upstox_client.rest import ApiException
from langchain_core.tools import tool
from datetime import datetime, timedelta

# Mock Instrument Key Mapper for Prototype
SYMBOL_MAP = {
    "RELIANCE": "NSE_EQ|INE002A01018",
    "TCS": "NSE_EQ|INE467B01029",
    "INFY": "NSE_EQ|INE009A01021",
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "SBIN": "NSE_EQ|INE062A01020",
    "TATAMOTORS": "NSE_EQ|INE155A01022",
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank"
}

def get_instrument_key(symbol: str) -> str:
    """Helper to resolve symbol to instrument key."""
    clean_symbol = symbol.upper().strip()
    return SYMBOL_MAP.get(clean_symbol, clean_symbol) # Fallback to returning the input if not found

def get_upstox_client():
    """Initializes the Upstox API client."""
    access_token = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        raise ValueError("UPSTOX_ACCESS_TOKEN environment variable not set")
    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    return upstox_client.ApiClient(configuration)

def fetch_candles(instrument_key: str, interval: str = "day"):
    """Fetches historical candle data from Upstox."""
    api_instance = upstox_client.HistoryApi(get_upstox_client())
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d") # Last 1 year
    
    # Using v2/v3 historical API - falling back to v2 based on available docs in context if v3 fails or straightforward usage
    # The docs showed HistoryApi having get_historical_candle_data
    try:
        # get_historical_candle_data(instrument_key, interval, to_date, from_date)
        # Intervals: 1minute, 30minute, day, week, month
        api_response = api_instance.get_historical_candle_data(instrument_key, interval, to_date, from_date)
        
        if api_response.status == "success" and api_response.data and api_response.data.candles:
            # Upstox returns list of lists: [timestamp, open, high, low, close, volume, open_interest]
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
            df = pd.DataFrame(api_response.data.candles, columns=columns)
            
            # Convert timestamp to datetime if necessary, usually string in ISO format
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        else:
            return None
    except ApiException as e:
        print(f"Exception when calling HistoryApi->get_historical_candle_data: {e}")
        return None

@tool
def get_stock_chart_data(symbol: str):
    """
    Fetches historical stock data for a given symbol (e.g., RELIANCE, TCS, NIFTY).
    Returns JSON structured data suitable for charting (timestamp, open, high, low, close).
    """
    instrument_key = get_instrument_key(symbol)
    df = fetch_candles(instrument_key)
    
    if df is not None:
        # Format for frontend chart
        # We'll return the last 100 candles to keep payload light
        df_subset = df.head(100).sort_values(by='timestamp')
        result = df_subset[['timestamp', 'open', 'high', 'low', 'close', 'volume']].to_dict(orient='records')
        return json.dumps({
            "symbol": symbol,
            "data": result,
            "message": f"Here is the daily chart for {symbol} over the last 100 trading days."
        }, default=str)
    return json.dumps({"error": f"Could not fetch data for {symbol}. Please check the symbol or API credentials."})

@tool
def calculate_momentum_indicator(symbol: str, indicator_name: str):
    """
    Calculates a momentum indicator for a given stock symbol.
    Supported indicators: RSI, MOM, STOCH, MACD, ADX.
    Returns the analysis and the calculated values.
    """
    instrument_key = get_instrument_key(symbol)
    df = fetch_candles(instrument_key)
    
    if df is None:
        return {"error": f"Could not fetch data for {symbol}."}
    
    # Prepare inputs for TA-Lib
    # TA-Lib Abstract API expects dict of numpy arrays with lowercase keys
    inputs = {
        'open': df['open'].values,
        'high': df['high'].values,
        'low': df['low'].values,
        'close': df['close'].values,
        'volume': df['volume'].values
    }
    
    indicator_name = indicator_name.upper()
    result_data = {}
    analysis = ""
    
    try:
        if indicator_name == 'RSI':
            rsi = ta.RSI(inputs, timeperiod=14)
            last_rsi = rsi[-1]
            result_data['RSI'] = rsi.tolist()[-20:] # Return last 20 points
            analysis = f"The current RSI (14) for {symbol} is {last_rsi:.2f}. "
            if last_rsi > 70:
                analysis += "It is in overbought territory."
            elif last_rsi < 30:
                analysis += "It is in oversold territory."
            else:
                analysis += "It is in a neutral zone."
                
        elif indicator_name == 'MOM':
            mom = ta.MOM(inputs, timeperiod=10)
            last_mom = mom[-1]
            result_data['MOM'] = mom.tolist()[-20:]
            analysis = f"The current Momentum (10) is {last_mom:.2f}."
            
        elif indicator_name == 'MACD':
            macd, macdsignal, macdhist = ta.MACD(inputs, fastperiod=12, slowperiod=26, signalperiod=9)
            result_data['MACD'] = macd.tolist()[-20:]
            result_data['Signal'] = macdsignal.tolist()[-20:]
            result_data['Hist'] = macdhist.tolist()[-20:]
            
            last_hist = macdhist[-1]
            analysis = f"MACD Histogram is {last_hist:.2f}. "
            if last_hist > 0:
                analysis += "Momentum is bullish."
            else:
                analysis += "Momentum is bearish."
        
        else:
            # Generic fallback for other indicators supported by abstract API
            func = ta.Function(indicator_name)
            output = func(inputs)
            # Output can be a single array or list of arrays (tuple)
            if isinstance(output, list) or isinstance(output, tuple):
                 # For simplicity in this generic block, just taking string rep
                 analysis = f"Calculated {indicator_name}."
            else:
                 last_val = output[-1]
                 analysis = f"Current {indicator_name} value: {last_val:.2f}"

        return json.dumps({
            "symbol": symbol,
            "indicator": indicator_name,
            "analysis": analysis,
            "values": result_data # Frontend could plot this if needed
        }, default=str)

    except Exception as e:
        return json.dumps({"error": f"Failed to calculate {indicator_name}: {str(e)}"})
