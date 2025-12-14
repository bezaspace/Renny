"""
Market Simulation Engine for RennyTech Trading

This module provides a realistic market simulation for day trading practice.
It fetches real historical data from Upstox, calculates volatility parameters,
and generates simulated 1-minute candlesticks using Geometric Brownian Motion.
"""

import asyncio
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import numpy as np

from backend.tools import fetch_candles, get_instrument_key
from backend.db import (
    upsert_historical_candles,
    fetch_historical_candles,
    get_last_candle,
)


@dataclass
class SymbolState:
    """Tracks simulation state for a single symbol."""
    symbol: str
    last_price: float
    volatility: float  # Annualized volatility (sigma)
    trend_bias: float = 0.0  # Drift coefficient (mu)
    volume_avg: float = 100000.0
    last_timestamp: Optional[datetime] = None


@dataclass
class Candle:
    """Represents a single candlestick."""
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class MarketSimulator:
    """
    Market simulation engine that generates realistic 1-minute candlesticks.
    
    Features:
    - Fetches real historical data from Upstox and stores in DB
    - Calculates volatility from actual price movements
    - Uses Geometric Brownian Motion for price simulation
    - Configurable tick rate (1x, 10x, 50x speed)
    """

    def __init__(self, symbols: List[str], speed_multiplier: float = 1.0):
        self.symbols = [s.upper().strip() for s in symbols]
        self.speed_multiplier = speed_multiplier
        self.symbol_states: Dict[str, SymbolState] = {}
        self.running = False
        self.paused = False
        self.current_sim_time: Optional[datetime] = None
        self._tick_callbacks: List[Callable] = []
        self._task: Optional[asyncio.Task] = None

    async def initialize(self, lookback_days: int = 30) -> Dict[str, Any]:
        """
        Fetch historical data from Upstox for all symbols and initialize simulation.
        
        Args:
            lookback_days: Number of days of historical data to fetch
            
        Returns:
            Dictionary with initialization results per symbol
        """
        results = {}
        
        for symbol in self.symbols:
            try:
                # Fetch historical data from Upstox
                instrument_key = get_instrument_key(symbol)
                df = fetch_candles(instrument_key, interval="1minute", lookback_days=lookback_days)
                
                if df is None or df.empty:
                    # Try daily data as fallback
                    df = fetch_candles(instrument_key, interval="day", lookback_days=lookback_days)
                
                if df is not None and not df.empty:
                    # Store in database
                    candles_to_store = []
                    for _, row in df.iterrows():
                        candles_to_store.append({
                            "symbol": symbol,
                            "timestamp": str(row["timestamp"]),
                            "open": float(row["open"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "close": float(row["close"]),
                            "volume": float(row["volume"]),
                        })
                    
                    stored_count = upsert_historical_candles(candles_to_store)
                    
                    # Calculate volatility from log returns
                    closes = df["close"].values.astype(float)
                    log_returns = np.diff(np.log(closes))
                    daily_volatility = np.std(log_returns) if len(log_returns) > 1 else 0.02
                    
                    # Annualize volatility (assuming 252 trading days, 375 minutes per day)
                    # For 1-min data: annualized_vol = per_min_vol * sqrt(375 * 252)
                    periods_per_year = 375 * 252
                    annualized_volatility = daily_volatility * math.sqrt(periods_per_year)
                    
                    # Get last known price
                    last_price = float(df.iloc[-1]["close"])
                    avg_volume = float(df["volume"].mean())
                    
                    # Initialize symbol state
                    self.symbol_states[symbol] = SymbolState(
                        symbol=symbol,
                        last_price=last_price,
                        volatility=max(0.1, min(annualized_volatility, 2.0)),  # Clamp between 10% and 200%
                        volume_avg=avg_volume,
                        last_timestamp=datetime.now(),
                    )
                    
                    results[symbol] = {
                        "status": "success",
                        "candles_stored": stored_count,
                        "last_price": last_price,
                        "volatility": self.symbol_states[symbol].volatility,
                    }
                else:
                    # Use fallback values
                    self.symbol_states[symbol] = SymbolState(
                        symbol=symbol,
                        last_price=1000.0,  # Default price
                        volatility=0.3,  # 30% annual volatility
                        volume_avg=100000,
                    )
                    results[symbol] = {
                        "status": "fallback",
                        "message": "Using default values - no data from Upstox",
                        "last_price": 1000.0,
                    }
                    
            except Exception as e:
                # Fallback on error
                self.symbol_states[symbol] = SymbolState(
                    symbol=symbol,
                    last_price=1000.0,
                    volatility=0.3,
                    volume_avg=100000,
                )
                results[symbol] = {
                    "status": "error",
                    "message": str(e),
                    "last_price": 1000.0,
                }
        
        self.current_sim_time = datetime.now()
        return results

    def _generate_candle(self, symbol: str) -> Candle:
        """
        Generate a single 1-minute candle using Geometric Brownian Motion.
        
        GBM formula: S(t+dt) = S(t) * exp((mu - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
        where Z ~ N(0,1)
        """
        state = self.symbol_states[symbol]
        
        # Time step for 1 minute (in years, assuming 375 trading minutes * 252 days)
        dt = 1.0 / (375 * 252)
        
        # GBM parameters
        mu = state.trend_bias
        sigma = state.volatility
        
        # Generate intrabar price path (simulate tick-by-tick within the minute)
        num_ticks = 10
        prices = [state.last_price]
        
        for _ in range(num_ticks):
            z = random.gauss(0, 1)
            drift = (mu - 0.5 * sigma ** 2) * (dt / num_ticks)
            diffusion = sigma * math.sqrt(dt / num_ticks) * z
            new_price = prices[-1] * math.exp(drift + diffusion)
            prices.append(max(0.01, new_price))  # Ensure positive price
        
        open_price = prices[0]
        close_price = prices[-1]
        high_price = max(prices)
        low_price = min(prices)
        
        # Generate volume with some randomness
        volume = state.volume_avg * (0.5 + random.random())
        
        # Update state
        state.last_price = close_price
        state.last_timestamp = self.current_sim_time
        
        return Candle(
            symbol=symbol,
            timestamp=self.current_sim_time.isoformat() if self.current_sim_time else datetime.now().isoformat(),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 0),
        )

    def generate_tick(self) -> Dict[str, Candle]:
        """Generate candles for all symbols and advance simulation time."""
        candles = {}
        
        for symbol in self.symbols:
            if symbol in self.symbol_states:
                candles[symbol] = self._generate_candle(symbol)
        
        # Advance simulation time by 1 minute
        if self.current_sim_time:
            self.current_sim_time += timedelta(minutes=1)
        else:
            self.current_sim_time = datetime.now()
            
        return candles

    def register_tick_callback(self, callback: Callable) -> None:
        """Register a callback to be called on each tick."""
        self._tick_callbacks.append(callback)

    async def _tick_loop(self) -> None:
        """Main simulation loop."""
        # Base interval is 60 seconds for 1x speed
        # At 10x speed, we tick every 6 seconds
        # At 50x speed, we tick every 1.2 seconds
        
        while self.running:
            if not self.paused:
                candles = self.generate_tick()
                
                # Notify all callbacks
                for callback in self._tick_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(candles)
                        else:
                            callback(candles)
                    except Exception as e:
                        print(f"Error in tick callback: {e}")
            
            # Wait based on speed multiplier
            wait_time = 60.0 / self.speed_multiplier
            await asyncio.sleep(max(0.1, wait_time))

    async def start(self) -> None:
        """Start the simulation loop."""
        if self.running:
            return
        
        self.running = True
        self.paused = False
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        """Stop the simulation loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def pause(self) -> None:
        """Pause the simulation."""
        self.paused = True

    def resume(self) -> None:
        """Resume the simulation."""
        self.paused = False

    def set_speed(self, multiplier: float) -> None:
        """Set the simulation speed multiplier."""
        self.speed_multiplier = max(0.1, min(multiplier, 100.0))

    def get_status(self) -> Dict[str, Any]:
        """Get current simulation status."""
        return {
            "running": self.running,
            "paused": self.paused,
            "speed_multiplier": self.speed_multiplier,
            "current_time": self.current_sim_time.isoformat() if self.current_sim_time else None,
            "symbols": list(self.symbol_states.keys()),
            "prices": {s: state.last_price for s, state in self.symbol_states.items()},
        }

    def get_current_prices(self) -> Dict[str, float]:
        """Get current prices for all symbols."""
        return {s: state.last_price for s, state in self.symbol_states.items()}


# Global simulator instance (will be initialized on first use)
_simulator: Optional[MarketSimulator] = None


def get_simulator() -> Optional[MarketSimulator]:
    """Get the global simulator instance."""
    return _simulator


def create_simulator(symbols: List[str], speed_multiplier: float = 10.0) -> MarketSimulator:
    """Create a new global simulator instance."""
    global _simulator
    _simulator = MarketSimulator(symbols, speed_multiplier)
    return _simulator
