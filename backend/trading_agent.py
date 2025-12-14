"""
Autonomous Trading Agent for RennyTech

This module implements a separate LangGraph agent that trades autonomously
based on strategies generated during onboarding. It evaluates market conditions
on each tick and executes paper trades when conditions match the strategy.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os

from backend.db import (
    fetch_holdings,
    fetch_trading_profile,
    fetch_portfolio_analysis,
    insert_trade,
    upsert_sim_position,
    fetch_sim_positions,
    delete_sim_position,
)
from backend.simulation_engine import Candle


@dataclass
class TradeSignal:
    """Represents a trade signal from the agent."""
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    reason: str
    confidence: float  # 0-1


@dataclass
class TradingAgentState:
    """Tracks the state of the trading agent."""
    user_id: str
    running: bool = False
    strategies: Dict[str, str] = None  # symbol -> strategy_markdown
    profile: Dict[str, str] = None  # horizon, risk, style
    holdings: Dict[str, Dict] = None  # symbol -> {quantity, avg_buy_price}
    candle_history: Dict[str, List[Dict]] = None  # symbol -> last N candles
    last_trade_time: Dict[str, datetime] = None  # symbol -> last trade timestamp
    
    def __post_init__(self):
        if self.strategies is None:
            self.strategies = {}
        if self.profile is None:
            self.profile = {}
        if self.holdings is None:
            self.holdings = {}
        if self.candle_history is None:
            self.candle_history = {}
        if self.last_trade_time is None:
            self.last_trade_time = {}


class TradingAgent:
    """
    Autonomous trading agent that evaluates market conditions and executes trades.
    
    Features:
    - Loads strategy from onboarding analysis
    - Evaluates each tick against strategy rules
    - Executes paper trades with reasoning
    - Streams trade notifications via callback
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.state = TradingAgentState(user_id=user_id)
        self._trade_callbacks: List[Callable] = []
        
        # Get API key - try multiple env var names for compatibility
        api_key = os.environ.get("MISTRAL_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE") or os.environ.get("LLM_API_BASE") or "https://api.mistral.ai/v1"

        model_name = os.environ.get("OPENAI_MODEL_NAME", "devstral-medium-2512-preview")
        
        # Debug: Print config (without exposing full key)
        key_preview = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else "NOT SET"
        print(f"[TradingAgent] LLM Config: model={model_name}, base_url={api_base}, api_key={key_preview}")
        
        self._llm = ChatOpenAI(
            model=model_name,
            temperature=0.1,
            base_url=api_base,
            api_key=api_key,  # Explicitly pass the API key
            streaming=False,
        )
        self._cooldown_minutes = 5  # Minimum minutes between trades on same symbol

    def register_trade_callback(self, callback: Callable) -> None:
        """Register a callback to be called when a trade is executed."""
        self._trade_callbacks.append(callback)

    async def initialize(self) -> Dict[str, Any]:
        """
        Load user's trading profile, holdings, and strategies from database.
        """
        # Load trading profile
        profile = fetch_trading_profile(self.user_id)
        if profile:
            self.state.profile = {
                "horizon": profile.get("horizon", "swing"),
                "risk": profile.get("risk", "balanced"),
                "style": profile.get("style", "trend"),
            }
        
        # Load holdings
        holdings = fetch_holdings(self.user_id)
        for h in holdings:
            symbol = h.get("symbol", "").upper()
            if symbol:
                self.state.holdings[symbol] = {
                    "quantity": float(h.get("quantity", 0)),
                    "avg_buy_price": float(h.get("avg_buy_price", 0)),
                }
                self.state.candle_history[symbol] = []
        
        # Load strategies from most recent portfolio analysis
        # We need to find the latest completed analysis
        # For now, we'll use a simplified approach
        strategies_loaded = 0
        # Try to get the most recent analysis for each symbol
        # This is a simplified implementation - in production, we'd query properly
        from backend.db import get_conn, DEFAULT_DB_PATH
        with get_conn(DEFAULT_DB_PATH) as conn:
            rows = conn.execute(
                """
                SELECT ha.symbol, ha.strategy_markdown
                FROM holding_analysis ha
                JOIN portfolio_analysis pa ON ha.portfolio_analysis_id = pa.id
                WHERE pa.user_id = ? AND pa.status = 'completed'
                ORDER BY pa.id DESC
                """,
                (self.user_id,),
            ).fetchall()
            
            seen_symbols = set()
            for row in rows:
                symbol = row["symbol"]
                if symbol not in seen_symbols and row["strategy_markdown"]:
                    self.state.strategies[symbol] = row["strategy_markdown"]
                    seen_symbols.add(symbol)
                    strategies_loaded += 1
        
        # Initialize sim positions from actual holdings
        for symbol, holding in self.state.holdings.items():
            upsert_sim_position(
                user_id=self.user_id,
                symbol=symbol,
                quantity=holding["quantity"],
                avg_price=holding["avg_buy_price"],
            )
        
        self.state.running = True
        
        return {
            "status": "initialized",
            "profile": self.state.profile,
            "holdings_count": len(self.state.holdings),
            "strategies_loaded": strategies_loaded,
            "symbols": list(self.state.holdings.keys()),
        }

    async def evaluate_tick(self, candles: Dict[str, Candle]) -> List[TradeSignal]:
        """
        Evaluate new candles and generate trade signals.
        
        Args:
            candles: Dictionary of symbol -> Candle from simulation engine
            
        Returns:
            List of trade signals (may be empty)
        """
        if not self.state.running:
            return []
        
        signals = []
        
        for symbol, candle in candles.items():
            # Update candle history
            if symbol not in self.state.candle_history:
                self.state.candle_history[symbol] = []
            
            self.state.candle_history[symbol].append(candle.to_dict())
            
            # Keep last 50 candles
            if len(self.state.candle_history[symbol]) > 50:
                self.state.candle_history[symbol] = self.state.candle_history[symbol][-50:]
            
            # Check cooldown
            if symbol in self.state.last_trade_time:
                time_since = datetime.now() - self.state.last_trade_time[symbol]
                if time_since.total_seconds() < self._cooldown_minutes * 60:
                    continue
            
            # Only evaluate if we have a strategy for this symbol
            if symbol not in self.state.strategies:
                continue
            
            # Need at least 10 candles for meaningful analysis
            if len(self.state.candle_history[symbol]) < 10:
                continue
            
            # Evaluate strategy
            signal = await self._evaluate_strategy(symbol, candle)
            if signal:
                signals.append(signal)
        
        return signals

    async def _evaluate_strategy(self, symbol: str, current_candle: Candle) -> Optional[TradeSignal]:
        """
        Use LLM to evaluate if current market conditions match the strategy.
        """
        strategy = self.state.strategies.get(symbol, "")
        if not strategy:
            return None
        
        # Get recent price action
        history = self.state.candle_history.get(symbol, [])[-20:]
        if len(history) < 5:
            return None
        
        # Calculate simple indicators
        closes = [c["close"] for c in history]
        current_price = current_candle.close
        
        # Simple moving averages
        sma_5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else current_price
        sma_10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else current_price
        
        # Price momentum
        price_change_5 = (current_price - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
        
        # Get current position
        position = self.state.holdings.get(symbol, {})
        current_qty = position.get("quantity", 0)
        avg_price = position.get("avg_buy_price", 0)
        
        # Prepare context for LLM
        context = {
            "symbol": symbol,
            "current_price": current_price,
            "sma_5": round(sma_5, 2),
            "sma_10": round(sma_10, 2),
            "price_change_5_candles_pct": round(price_change_5, 2),
            "recent_high": max(c["high"] for c in history[-10:]),
            "recent_low": min(c["low"] for c in history[-10:]),
            "current_position_qty": current_qty,
            "avg_buy_price": avg_price,
            "unrealized_pnl_pct": round((current_price - avg_price) / avg_price * 100, 2) if avg_price > 0 else 0,
            "profile": self.state.profile,
        }
        
        # Create evaluation prompt
        prompt = [
            SystemMessage(content="""You are a trading bot evaluating market conditions.
Given the strategy and current market data, determine if a trade should be executed.

IMPORTANT RULES:
1. Only recommend a trade if conditions CLEARLY match the strategy
2. Be conservative - when in doubt, do nothing
3. Consider risk tolerance and position sizing
4. Output ONLY valid JSON, no other text

If recommending a trade, output:
{"action": "buy" or "sell", "quantity": number, "confidence": 0.0-1.0, "reason": "brief explanation"}

If no trade:
{"action": "hold", "reason": "why no trade"}"""),
            HumanMessage(content=f"""STRATEGY:
{strategy}

CURRENT MARKET DATA:
{json.dumps(context, indent=2)}

Evaluate and respond with JSON only:"""),
        ]
        
        try:
            response = self._llm.invoke(prompt)
            content = response.content.strip()
            
            # Extract JSON from response
            # Handle potential markdown code blocks
            if "```" in content:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                if match:
                    content = match.group(1)
            
            decision = json.loads(content)
            
            action = decision.get("action", "hold").lower()
            
            if action in ["buy", "sell"]:
                confidence = float(decision.get("confidence", 0.5))
                
                # Only execute if confidence is high enough
                if confidence < 0.6:
                    return None
                
                # Determine quantity
                qty = float(decision.get("quantity", 0))
                if qty <= 0:
                    # Default to 10% of holding on sell, or small buy
                    if action == "sell" and current_qty > 0:
                        qty = max(1, current_qty * 0.1)
                    else:
                        qty = 1  # Minimum buy
                
                return TradeSignal(
                    symbol=symbol,
                    side=action,
                    quantity=round(qty, 2),
                    price=current_price,
                    reason=decision.get("reason", "Strategy match"),
                    confidence=confidence,
                )
                
        except json.JSONDecodeError:
            # LLM didn't return valid JSON - no trade
            pass
        except Exception as e:
            print(f"Error evaluating strategy for {symbol}: {e}")
        
        return None

    async def execute_trade(self, signal: TradeSignal) -> Dict[str, Any]:
        """
        Execute a trade signal and record it in the database.
        """
        # Record the trade
        trade_id = insert_trade(
            user_id=self.user_id,
            symbol=signal.symbol,
            side=signal.side,
            quantity=signal.quantity,
            price=signal.price,
            reason=signal.reason,
        )
        
        # Update position
        current_position = self.state.holdings.get(signal.symbol, {"quantity": 0, "avg_buy_price": 0})
        current_qty = current_position.get("quantity", 0)
        current_avg = current_position.get("avg_buy_price", 0)
        
        if signal.side == "buy":
            new_qty = current_qty + signal.quantity
            # Weighted average price
            total_cost = (current_qty * current_avg) + (signal.quantity * signal.price)
            new_avg = total_cost / new_qty if new_qty > 0 else signal.price
            
            self.state.holdings[signal.symbol] = {
                "quantity": new_qty,
                "avg_buy_price": new_avg,
            }
            
            upsert_sim_position(
                user_id=self.user_id,
                symbol=signal.symbol,
                quantity=new_qty,
                avg_price=new_avg,
            )
            
        elif signal.side == "sell":
            new_qty = max(0, current_qty - signal.quantity)
            
            if new_qty > 0:
                self.state.holdings[signal.symbol] = {
                    "quantity": new_qty,
                    "avg_buy_price": current_avg,  # Keep avg price
                }
                upsert_sim_position(
                    user_id=self.user_id,
                    symbol=signal.symbol,
                    quantity=new_qty,
                    avg_price=current_avg,
                )
            else:
                # Position closed
                if signal.symbol in self.state.holdings:
                    del self.state.holdings[signal.symbol]
                delete_sim_position(self.user_id, signal.symbol)
        
        # Update last trade time
        self.state.last_trade_time[signal.symbol] = datetime.now()
        
        # Create trade record for notification
        trade_record = {
            "id": trade_id,
            "symbol": signal.symbol,
            "side": signal.side,
            "quantity": signal.quantity,
            "price": signal.price,
            "reason": signal.reason,
            "confidence": signal.confidence,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Notify callbacks
        for callback in self._trade_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trade_record)
                else:
                    callback(trade_record)
            except Exception as e:
                print(f"Error in trade callback: {e}")
        
        return trade_record

    async def process_tick(self, candles: Dict[str, Candle]) -> List[Dict[str, Any]]:
        """
        Main entry point: evaluate tick and execute any trade signals.
        
        Returns list of executed trades.
        """
        signals = await self.evaluate_tick(candles)
        
        executed_trades = []
        for signal in signals:
            trade = await self.execute_trade(signal)
            executed_trades.append(trade)
        
        return executed_trades

    def stop(self) -> None:
        """Stop the trading agent."""
        self.state.running = False

    def start(self) -> None:
        """Resume the trading agent."""
        self.state.running = True

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        positions = fetch_sim_positions(self.user_id)
        
        return {
            "running": self.state.running,
            "user_id": self.user_id,
            "profile": self.state.profile,
            "symbols_tracked": list(self.state.strategies.keys()),
            "positions": positions,
            "candle_counts": {s: len(h) for s, h in self.state.candle_history.items()},
        }


# Global agent instance
_trading_agent: Optional[TradingAgent] = None


def get_trading_agent() -> Optional[TradingAgent]:
    """Get the global trading agent instance."""
    return _trading_agent


def create_trading_agent(user_id: str = "default") -> TradingAgent:
    """Create a new global trading agent instance."""
    global _trading_agent
    _trading_agent = TradingAgent(user_id)
    return _trading_agent
