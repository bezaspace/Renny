import os
import json
import re
import pandas as pd
import numpy as np
import talib
import talib.abstract as ta
import upstox_client
from upstox_client.rest import ApiException
from langchain_core.tools import tool
from datetime import datetime, timedelta

def load_symbol_map_from_file():
    """Parses stocks.md to build a symbol map."""
    symbol_map = {}
    current_exchange = None
    try:
        # Assuming stocks.md is in the parent directory of backend/
        # Use explicit path relative to current working directory if possible, or relative to file
        base_dir = os.getcwd()
        file_path = os.path.join(base_dir, "stocks.md")
        
        if not os.path.exists(file_path):
             # Fallback: try relative to this file
             file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stocks.md")

        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("# NSE Stocks"):
                        current_exchange = "NSE_EQ"
                        continue
                    elif line.startswith("# BSE Stocks"):
                        current_exchange = "BSE_EQ"
                        continue
                    
                    if not current_exchange:
                        continue

                    # Format: | Trading Symbol | ISIN | Company Name |
                    # Regex to capture Symbol and ISIN (allowing INE, INF, INY etc)
                    match = re.search(r'\|\s*([A-Z0-9]+)\s*\|\s*(IN[A-Z0-9]+)\s*\|', line)
                    if match:
                        symbol = match.group(1).strip()
                        isin = match.group(2).strip()
                        instrument_key = f"{current_exchange}|{isin}"
                        
                        # Store specific exchange mapping (e.g., RELIANCE.NSE, RELIANCE.BSE)
                        exch_suffix = current_exchange.split('_')[0]
                        symbol_map[f"{symbol}.{exch_suffix}"] = instrument_key
                        
                        # For the bare symbol (e.g. RELIANCE):
                        # Prioritize NSE. If current is NSE, set it.
                        # If current is BSE, only set if not already present (don't overwrite NSE)
                        if current_exchange == "NSE_EQ":
                            symbol_map[symbol] = instrument_key
                        elif current_exchange == "BSE_EQ":
                            if symbol not in symbol_map:
                                symbol_map[symbol] = instrument_key

    except Exception as e:
        print(f"Error loading symbol map: {e}")
    
    return symbol_map

# Mock Instrument Key Mapper for Prototype
SYMBOL_MAP = {
    "RELIANCE": "NSE_EQ|INE002A01018",
    "TCS": "NSE_EQ|INE467B01029",
    "INFY": "NSE_EQ|INE009A01021",
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "SBIN": "NSE_EQ|INE062A01020",
    "TATAMOTORS": "NSE_EQ|INE155A01022",
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "HDFC": "NSE_EQ|INE040A01034" # Alias for HDFC to HDFCBANK
}

# Update with loaded symbols
SYMBOL_MAP.update(load_symbol_map_from_file())

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

def fetch_candles(instrument_key: str, interval: str = "day", lookback_days: int = 365):
    """Fetches historical candle data from Upstox."""
    api_instance = upstox_client.HistoryApi(get_upstox_client())
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d") # Last 1 year
    
    # Using v2/v3 historical API - falling back to v2 based on available docs in context if v3 fails or straightforward usage
    # The docs showed HistoryApi having get_historical_candle_data
    try:
        # get_historical_candle_data1(instrument_key, interval, to_date, from_date, api_version)
        # Intervals: 1minute, 30minute, day, week, month
        api_response = api_instance.get_historical_candle_data1(instrument_key, interval, to_date, from_date, "2.0")
        
        if api_response.status == "success" and api_response.data and api_response.data.candles:
            # Upstox returns list of lists: [timestamp, open, high, low, close, volume, open_interest]
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
            df = pd.DataFrame(api_response.data.candles, columns=columns)
            
            # Convert timestamp to datetime if necessary, usually string in ISO format
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Sort by timestamp ascending (Oldest -> Newest) to ensure correct TA calc
            df = df.sort_values(by='timestamp', ascending=True).reset_index(drop=True)
            
            return df
        else:
            return None
    except ApiException as e:
        print(f"Exception when calling HistoryApi->get_historical_candle_data: {e}")
        return None


def _scan_candlestick_patterns(
    df: pd.DataFrame,
    lookback_bars: int = 20,
    max_patterns: int = 3,
    strength_threshold: int = 80,
):
    patterns = talib.get_function_groups().get("Pattern Recognition", [])
    if df is None or df.empty:
        return {
            "patterns": [],
            "pattern_markers": [],
        }

    required_cols = {"open", "high", "low", "close", "timestamp"}
    if not required_cols.issubset(set(df.columns)):
        return {
            "patterns": [],
            "pattern_markers": [],
            "error": "Missing required OHLCV columns for pattern scan.",
        }

    o = df["open"].astype(float).values
    h = df["high"].astype(float).values
    l = df["low"].astype(float).values
    c = df["close"].astype(float).values
    timestamps = df["timestamp"].astype(str).tolist()

    candidates = []
    start_idx = max(0, len(df) - lookback_bars)
    for p in patterns:
        try:
            func = getattr(talib, p, None)
            if func is None:
                continue
            out = func(o, h, l, c)
            if out is None or len(out) == 0:
                continue

            window = out[start_idx:]
            nz = np.where(window != 0)[0]
            if len(nz) == 0:
                continue

            last_offset = int(nz[-1])
            idx = start_idx + last_offset
            val = int(out[idx])
            strength = abs(val)
            if strength < strength_threshold:
                continue

            direction = "bullish" if val > 0 else "bearish"
            recency = (len(df) - 1) - idx
            score = (strength * 2) - (recency * 3)
            candidates.append(
                {
                    "pattern": p,
                    "timestamp": timestamps[idx] if idx < len(timestamps) else None,
                    "index": idx,
                    "direction": direction,
                    "strength": strength,
                    "score": score,
                }
            )
        except Exception:
            continue

    candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
    top = candidates[:max_patterns]

    patterns_out = []
    markers = []
    for item in top:
        patterns_out.append(
            {
                "name": item["pattern"],
                "direction": item["direction"],
                "strength": item["strength"],
                "timestamp": item["timestamp"],
            }
        )
        markers.append(
            {
                "timestamp": item["timestamp"],
                "pattern": item["pattern"],
                "direction": item["direction"],
                "strength": item["strength"],
            }
        )

    return {
        "patterns": patterns_out,
        "pattern_markers": markers,
    }


def build_full_analysis_payload(
    symbol: str,
    interval: str,
    lookback_days: int,
    chart_limit: int = 100,
    series_limit: int = 50,
    pattern_lookback_bars: int = 20,
):
    instrument_key = get_instrument_key(symbol)
    df = fetch_candles(instrument_key, interval=interval, lookback_days=lookback_days)
    if df is None or df.empty:
        return {"error": f"Could not fetch data for {symbol}."}

    df_chart = df.tail(chart_limit).copy()
    chart_data = df_chart[["timestamp", "open", "high", "low", "close", "volume"]].to_dict(orient="records")

    inputs = {
        "open": df["open"].values,
        "high": df["high"].values,
        "low": df["low"].values,
        "close": df["close"].values,
        "volume": df["volume"].values.astype(float),
    }

    def _to_series(arr, limit):
        sliced = arr[-limit:]
        return [float(x) if not np.isnan(x) else None for x in sliced]

    overlays = {}
    try:
        overlays["SMA20"] = _to_series(ta.SMA(inputs, timeperiod=20), chart_limit)
    except Exception:
        pass
    try:
        overlays["SMA50"] = _to_series(ta.SMA(inputs, timeperiod=50), chart_limit)
    except Exception:
        pass
    try:
        upper, middle, lower = ta.BBANDS(inputs, timeperiod=20, nbdevup=2, nbdevdn=2)
        overlays["BBANDS"] = {
            "upper": _to_series(upper, chart_limit),
            "middle": _to_series(middle, chart_limit),
            "lower": _to_series(lower, chart_limit),
        }
    except Exception:
        pass

    timestamps = df["timestamp"].astype(str).tolist()[-series_limit:]

    series = {}
    try:
        rsi = ta.RSI(inputs, timeperiod=14)
        series["RSI"] = {"RSI": _to_series(rsi, series_limit)}
    except Exception:
        pass
    try:
        macd, macdsignal, macdhist = ta.MACD(inputs, fastperiod=12, slowperiod=26, signalperiod=9)
        series["MACD"] = {
            "MACD": _to_series(macd, series_limit),
            "Signal": _to_series(macdsignal, series_limit),
            "Hist": _to_series(macdhist, series_limit),
        }
    except Exception:
        pass
    try:
        adx = ta.ADX(inputs, timeperiod=14)
        series["ADX"] = {"ADX": _to_series(adx, series_limit)}
    except Exception:
        pass
    try:
        atr = ta.ATR(inputs, timeperiod=14)
        series["ATR"] = {"ATR": _to_series(atr, series_limit)}
    except Exception:
        pass

    pattern_result = _scan_candlestick_patterns(
        df_chart,
        lookback_bars=pattern_lookback_bars,
        max_patterns=3,
        strength_threshold=80,
    )

    return {
        "symbol": symbol,
        "interval": interval,
        "data": chart_data,
        "message": f"Full analysis visuals for {symbol} ({interval}).",
        "overlays": overlays,
        "series": series,
        "timestamps": timestamps,
        "patterns": pattern_result.get("patterns", []),
        "pattern_markers": pattern_result.get("pattern_markers", []),
    }


@tool
def get_full_analysis_visuals(symbol: str, interval: str = "day", lookback_days: int = 365):
    """Build a full analysis visualization payload (chart + overlays + key indicator series + candlestick patterns).

    This returns JSON content intended to be rendered in the UI right-side panel.
    """
    payload = build_full_analysis_payload(
        symbol=symbol,
        interval=interval,
        lookback_days=lookback_days,
    )
    return json.dumps(payload, default=str)

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
        df_subset = df.tail(100).sort_values(by='timestamp')
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
        'volume': df['volume'].values.astype(float)
    }
    
    indicator_name = indicator_name.upper()
    result_data = {}
    analysis = ""
    
    try:
        if indicator_name == 'RSI':
            rsi = ta.RSI(inputs, timeperiod=14)
            last_rsi = rsi[-1]
            # Return last 50 points for charting
            result_data['RSI'] = rsi.tolist()[-50:] 
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
            result_data['MOM'] = mom.tolist()[-50:]
            analysis = f"The current Momentum (10) is {last_mom:.2f}."
            
        elif indicator_name == 'MACD':
            macd, macdsignal, macdhist = ta.MACD(inputs, fastperiod=12, slowperiod=26, signalperiod=9)
            result_data['MACD'] = macd.tolist()[-50:]
            result_data['Signal'] = macdsignal.tolist()[-50:]
            result_data['Hist'] = macdhist.tolist()[-50:]
            
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
                 for idx, out_arr in enumerate(output):
                     out_name = func.output_names[idx] if idx < len(func.output_names) else f"out_{idx}"
                     result_data[out_name] = out_arr.tolist()[-50:]
                 analysis = f"Calculated {indicator_name}."
            else:
                 last_val = output[-1]
                 result_data[indicator_name] = output.tolist()[-50:]
                 analysis = f"Current {indicator_name} value: {last_val:.2f}"

        # Add timestamps for the x-axis
        timestamps = df['timestamp'].astype(str).tolist()[-50:]
        
        return json.dumps({
            "symbol": symbol,
            "indicator": indicator_name,
            "analysis": analysis,
            "values": result_data,
            "timestamps": timestamps
        }, default=str)

    except Exception as e:
        return json.dumps({"error": f"Failed to calculate {indicator_name}: {str(e)}"})

@tool
def run_comprehensive_analysis(symbol: str):
    """
    Runs a comprehensive technical analysis on a given stock symbol.
    Executes ALL available TA-Lib indicators (excluding Pattern Recognition) 
    to provide a complete technical overview.
    Returns chart data and overlay indicators for visualization.
    """
    instrument_key = get_instrument_key(symbol)
    df = fetch_candles(instrument_key)
    
    if df is None:
        return json.dumps({"error": f"Could not fetch data for {symbol}."})
    
    # Prepare inputs for TA-Lib
    inputs = {
        'open': df['open'].values,
        'high': df['high'].values,
        'low': df['low'].values,
        'close': df['close'].values,
        'volume': df['volume'].values.astype(float)
    }
    
    # We'll focus on the last 100 points for the chart and overlays
    limit = 100
    df_subset = df.tail(limit).copy()
    chart_data = df_subset[['timestamp', 'open', 'high', 'low', 'close', 'volume']].to_dict(orient='records')
    
    analysis_results = {
        "symbol": symbol,
        "timestamp": str(datetime.now()),
        "data": chart_data, # Main chart data
        "overlays": {},      # Series data for overlapping indicators
        "indicators": {}     # Snapshot values for summary
    }
    
    # Get all function groups
    groups = talib.get_function_groups()
    
    # Key indicators to capture series data for (for visualization)
    KEY_INDICATORS = ['RSI', 'MOM', 'MACD', 'STOCH', 'ADX', 'CCI', 'APO', 'DX', 'WILLR']
    analysis_results["series"] = {}

    for group_name, indicators in groups.items():
        # User requested to exclude pattern recognition
        if group_name == 'Pattern Recognition':
            continue
            
        analysis_results["indicators"][group_name] = {}
        
        for ind_name in indicators:
            try:
                func = ta.Function(ind_name)
                output = func(inputs)
                
                # Handle Snapshot (Last Value)
                value_snapshot = {}
                if isinstance(output, tuple) or isinstance(output, list):
                    for idx, out_arr in enumerate(output):
                        out_name = func.output_names[idx] if idx < len(func.output_names) else f"out_{idx}"
                        last_val = out_arr[-1]
                        if pd.isna(last_val):
                             valid_vals = out_arr[~np.isnan(out_arr)]
                             last_val = valid_vals[-1] if len(valid_vals) > 0 else None
                        value_snapshot[out_name] = float(last_val) if last_val is not None else None
                else:
                    last_val = output[-1]
                    if pd.isna(last_val):
                         valid_vals = output[~np.isnan(output)]
                         last_val = valid_vals[-1] if len(valid_vals) > 0 else None
                    key_name = func.output_names[0] if func.output_names else ind_name
                    value_snapshot[key_name] = float(last_val) if last_val is not None else None
                
                analysis_results["indicators"][group_name][ind_name] = value_snapshot

                # Handle Series Data for Key Indicators
                if ind_name in KEY_INDICATORS:
                    series_data = {}
                    
                    def process_array(arr):
                        sliced = arr[-50:] # Last 50 points for sparklines/mini-charts
                        return [float(x) if not np.isnan(x) else None for x in sliced]

                    if isinstance(output, tuple) or isinstance(output, list):
                        for idx, out_arr in enumerate(output):
                            out_name = func.output_names[idx] if idx < len(func.output_names) else f"line_{idx}"
                            series_data[out_name] = process_array(out_arr)
                    else:
                        key_name = func.output_names[0] if func.output_names else ind_name
                        series_data[key_name] = process_array(output)
                    
                    analysis_results["series"][ind_name] = series_data

                # Handle Overlays (Series Data) - Only for Overlap Studies
                if group_name == 'Overlap Studies':
                    # valid_points ensures we match the chart_data length (last 'limit' points)
                    # We need to handle NaN at start if lookback is long, replace with null for JSON
                    
                    def process_overlay_array(arr):
                        # Slice to last 'limit'
                        sliced = arr[-limit:]
                        # Convert to list, replace NaN with None
                        return [float(x) if not np.isnan(x) else None for x in sliced]

                    if isinstance(output, tuple) or isinstance(output, list):
                        # Store complex overlay (e.g. BBANDS) as a dict
                        complex_overlay = {}
                        for idx, out_arr in enumerate(output):
                            out_name = func.output_names[idx] if idx < len(func.output_names) else f"line_{idx}"
                            complex_overlay[out_name] = process_overlay_array(out_arr)
                        analysis_results["overlays"][ind_name] = complex_overlay
                    else:
                        # Store simple overlay (e.g. SMA) as a list
                        analysis_results["overlays"][ind_name] = process_overlay_array(output)

            except Exception as e:
                analysis_results["indicators"][group_name][ind_name] = {"error": str(e)}

    return json.dumps(analysis_results, default=str)
