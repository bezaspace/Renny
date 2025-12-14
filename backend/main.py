import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from backend.agent import agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from backend.db import (
    init_db,
    fetch_holdings,
    fetch_trading_profile,
    replace_holdings,
    upsert_trading_profile,
    create_portfolio_analysis,
    add_holding_analysis,
    finalize_portfolio_analysis,
    fetch_portfolio_analysis,
    fetch_trades,
    fetch_sim_positions,
    fetch_users_with_sim_positions,
    insert_trade,
    upsert_sim_position,
    delete_sim_position,
)
from backend.tools import build_full_analysis_payload
from backend.simulation_engine import create_simulator, get_simulator, MarketSimulator
from backend.trading_agent import create_trading_agent, get_trading_agent, TradingAgent

app = FastAPI()


@app.on_event("startup")
def _startup_init_db():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_thread"


class HoldingInput(BaseModel):
    symbol: str
    quantity: float
    avg_buy_price: float


class TradingProfileInput(BaseModel):
    horizon: str
    risk: str
    style: str


class OnboardingSaveRequest(BaseModel):
    holdings: List[HoldingInput]
    profile: TradingProfileInput


class AnalyzePortfolioRequest(BaseModel):
    user_id: str = "default"


def _serialize_messages(messages):
    serialized_messages = []
    for msg in messages:
        msg_type = msg.type
        content = msg.content
        tool_calls = getattr(msg, "tool_calls", [])

        if msg_type == 'tool':
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "indicators" in data and "symbol" in data:
                    content = json.dumps({
                        "symbol": data.get("symbol"),
                        "indicator": "Technical Analysis Scan",
                        "analysis": "Comprehensive set of indicators calculated successfully. See the summary below for insights.",
                        "data": data.get("data"),
                        "overlays": data.get("overlays"),
                        "series": data.get("series")
                    })
            except Exception:
                pass

        serialized_messages.append({
            "type": msg_type,
            "content": content,
            "tool_calls": tool_calls,
            "id": getattr(msg, "id", None)
        })
    return serialized_messages

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # Invoke the agent with the new user message
        # The agent will pick up previous state from the checkpointer using thread_id
        final_state = agent.invoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config
        )
        
        # Extract messages
        messages = final_state.get("messages", [])

        return {"messages": _serialize_messages(messages)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
def chat_stream_endpoint(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}

    def gen():
        try:
            for chunk, _metadata in agent.stream(
                {"messages": [HumanMessage(content=request.message)]},
                config=config,
                stream_mode="messages",
            ):
                delta = getattr(chunk, "content", None)
                if not delta:
                    continue
                yield (json.dumps({"type": "ai_delta", "delta": delta}) + "\n").encode("utf-8")

            snapshot = agent.get_state(config)
            messages = snapshot.values.get("messages", []) if snapshot and snapshot.values else []
            yield (json.dumps({"type": "final", "messages": _serialize_messages(messages)}) + "\n").encode("utf-8")

        except Exception as e:
            yield (json.dumps({"type": "error", "message": str(e)}) + "\n").encode("utf-8")

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/onboarding/{user_id}")
def get_onboarding(user_id: str = "default"):
    holdings = fetch_holdings(user_id)
    profile = fetch_trading_profile(user_id)
    return {"user_id": user_id, "holdings": holdings, "profile": profile}

@app.post("/onboarding/{user_id}")
def save_onboarding(user_id: str, request: OnboardingSaveRequest):
    holdings_dicts = [h.model_dump() for h in request.holdings]
    replace_holdings(user_id, holdings_dicts)
    upsert_trading_profile(user_id, request.profile.model_dump())
    return {"ok": True}

def _portfolio_interval_and_lookback(horizon: str):
    h = (horizon or "").strip().lower()
    if h == "intraday":
        return "30minute", 30
    if h == "investing":
        return "week", 365 * 3
    return "day", 365

def _analysis_model():
    api_key = os.environ.get("MISTRAL_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    api_base = os.environ.get("OPENAI_API_BASE") or os.environ.get("LLM_API_BASE") or "https://api.mistral.ai/v1"
    model_name = os.environ.get("OPENAI_MODEL_NAME", "devstral-medium-2512-preview")
    return ChatOpenAI(
        model=model_name,
        temperature=0,
        base_url=api_base,
        api_key=api_key,
        streaming=False,
    )

@app.post("/portfolio/analyze")
def analyze_portfolio(request: AnalyzePortfolioRequest):
    user_id = request.user_id or "default"
    holdings = fetch_holdings(user_id)
    profile = fetch_trading_profile(user_id)

    if not holdings:
        raise HTTPException(status_code=400, detail="No holdings found. Save onboarding data first.")
    if not profile:
        raise HTTPException(status_code=400, detail="No trading profile found. Save onboarding data first.")

    pa_id = create_portfolio_analysis(user_id, status="running")

    try:
        horizon = str(profile.get("horizon"))
        risk = str(profile.get("risk"))
        style = str(profile.get("style"))
        interval, lookback_days = _portfolio_interval_and_lookback(horizon)
        llm = _analysis_model()

        per_stock_summaries = []

        for h in holdings:
            symbol = str(h.get("symbol", "")).strip().upper()
            qty = float(h.get("quantity", 0))
            avg_buy = float(h.get("avg_buy_price", 0))

            visuals = build_full_analysis_payload(
                symbol=symbol,
                interval=interval,
                lookback_days=lookback_days,
            )

            summary_prompt = [
                SystemMessage(
                    content=(
                        "You are a trading analyst. Given the technical snapshot and candlestick patterns, produce a practical trade plan. "
                        "Output must include: Market bias, Key levels, Setup, Entry trigger, Stop/invalidation, Targets, Risk/position sizing notes, and what would change your view. "
                        "Incorporate the user's holding (quantity and average buy price) into the plan (e.g., manage risk, decide hold/add/trim)."
                    )
                ),
                HumanMessage(
                    content=json.dumps(
                        {
                            "symbol": symbol,
                            "holding": {"quantity": qty, "avg_buy_price": avg_buy},
                            "horizon": horizon,
                            "risk": risk,
                            "style": style,
                            "interval": interval,
                            "patterns": (visuals or {}).get("patterns", []),
                            "series": (visuals or {}).get("series", {}),
                            "overlays": (visuals or {}).get("overlays", {}),
                        },
                        default=str,
                    )
                ),
            ]

            summary_msg = llm.invoke(summary_prompt)
            strategy_md = getattr(summary_msg, "content", "")
            tool_payload_json = json.dumps(visuals, default=str)

            add_holding_analysis(
                portfolio_analysis_id=pa_id,
                symbol=symbol,
                horizon=horizon,
                risk=risk,
                style=style,
                tool_payload_json=tool_payload_json,
                strategy_markdown=strategy_md,
            )

            per_stock_summaries.append(
                {
                    "symbol": symbol,
                    "quantity": qty,
                    "avg_buy_price": avg_buy,
                    "strategy_markdown": strategy_md,
                }
            )

        portfolio_prompt = [
            SystemMessage(
                content=(
                    "You are a portfolio trading strategist. Based on the user's trading profile and per-stock trade plans, produce a portfolio-level plan for the next session. "
                    "Include: prioritization, risk budgeting, when to do nothing, and conflicts/correlation notes. Output in markdown."
                )
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        "trading_profile": {"horizon": horizon, "risk": risk, "style": style},
                        "holdings": holdings,
                        "per_stock": per_stock_summaries,
                    },
                    default=str,
                )
            ),
        ]
        portfolio_summary_msg = llm.invoke(portfolio_prompt)
        portfolio_summary_md = getattr(portfolio_summary_msg, "content", "")

        finalize_portfolio_analysis(pa_id, status="completed", summary_markdown=portfolio_summary_md)
        return {"portfolio_analysis_id": pa_id, "status": "completed"}

    except Exception as e:
        finalize_portfolio_analysis(pa_id, status="error", error_message=str(e))
        raise

@app.get("/portfolio/analysis/{portfolio_analysis_id}")
def get_portfolio_analysis(portfolio_analysis_id: int):
    result = fetch_portfolio_analysis(portfolio_analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Portfolio analysis not found")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Trading Simulation Endpoints
# ─────────────────────────────────────────────────────────────────────────────

# WebSocket connection manager for live feed
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()


class TradingInitRequest(BaseModel):
    user_id: str = "default"
    lookback_days: int = 30
    speed_multiplier: float = 10.0


class TradingControlRequest(BaseModel):
    user_id: str = "default"


class SpeedChangeRequest(BaseModel):
    speed_multiplier: float = 10.0


class ManualTradeRequest(BaseModel):
    user_id: str = "default"
    symbol: str
    side: str
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: Optional[str] = None


class PositionRiskUpdateRequest(BaseModel):
    user_id: str = "default"
    symbol: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _get_sim_price(symbol: str) -> float:
    simulator = get_simulator()
    if not simulator:
        raise HTTPException(status_code=400, detail="Simulator not initialized. Call /trading/init first.")
    prices = simulator.get_current_prices()
    sym = _normalize_symbol(symbol)
    if sym not in prices:
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {sym}")
    return float(prices[sym])


def _execute_paper_trade(
    *,
    user_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    reason: Optional[str] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> Dict[str, Any]:
    sym = _normalize_symbol(symbol)
    s = str(side or "").strip().lower()
    qty = float(quantity)
    if s not in {"buy", "sell"}:
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    if qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be > 0")

    current_positions = {p["symbol"]: p for p in fetch_sim_positions(user_id)}
    position = current_positions.get(sym)
    current_qty = float((position or {}).get("quantity") or 0)
    current_avg = float((position or {}).get("avg_price") or 0)
    current_stop = (position or {}).get("stop_loss")
    current_tp = (position or {}).get("take_profit")

    if s == "sell" and qty > current_qty:
        raise HTTPException(status_code=400, detail="Insufficient position quantity to sell")

    trade_id = insert_trade(
        user_id=user_id,
        symbol=sym,
        side=s,
        quantity=qty,
        price=float(price),
        reason=reason,
    )

    if s == "buy":
        new_qty = current_qty + qty
        total_cost = (current_qty * current_avg) + (qty * float(price))
        new_avg = total_cost / new_qty if new_qty > 0 else float(price)
        upsert_sim_position(
            user_id=user_id,
            symbol=sym,
            quantity=new_qty,
            avg_price=new_avg,
            stop_loss=stop_loss if stop_loss is not None else current_stop,
            take_profit=take_profit if take_profit is not None else current_tp,
        )
    else:
        new_qty = max(0.0, current_qty - qty)
        if new_qty > 0:
            upsert_sim_position(
                user_id=user_id,
                symbol=sym,
                quantity=new_qty,
                avg_price=current_avg,
                stop_loss=current_stop,
                take_profit=current_tp,
            )
        else:
            delete_sim_position(user_id, sym)

    return {
        "id": trade_id,
        "symbol": sym,
        "side": s,
        "quantity": qty,
        "price": float(price),
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _validate_risk_for_long(*, current_price: float, stop_loss: Optional[float], take_profit: Optional[float]) -> None:
    if stop_loss is not None and float(stop_loss) >= float(current_price):
        raise HTTPException(status_code=400, detail="stop_loss must be below current price for long positions")
    if take_profit is not None and float(take_profit) <= float(current_price):
        raise HTTPException(status_code=400, detail="take_profit must be above current price for long positions")


@app.post("/trading/init")
async def init_trading(request: TradingInitRequest):
    """
    Initialize trading simulation by fetching historical data from Upstox.
    This must be called before starting the simulation.
    """
    user_id = request.user_id or "default"
    
    # Get user's holdings
    holdings = fetch_holdings(user_id)
    if not holdings:
        raise HTTPException(status_code=400, detail="No holdings found. Complete onboarding first.")
    
    symbols = [h["symbol"] for h in holdings if h.get("symbol")]
    if not symbols:
        raise HTTPException(status_code=400, detail="No valid symbols in holdings.")
    
    # Create simulator
    simulator = create_simulator(symbols, request.speed_multiplier)
    
    # Initialize with historical data
    init_result = await simulator.initialize(request.lookback_days)
    
    # Create trading agent
    agent = create_trading_agent(user_id)
    agent_result = await agent.initialize()
    
    return {
        "status": "initialized",
        "simulator": init_result,
        "agent": agent_result,
    }


@app.post("/trading/start")
async def start_trading(request: TradingControlRequest):
    """Start the trading simulation."""
    simulator = get_simulator()
    agent = get_trading_agent()
    
    if not simulator:
        raise HTTPException(status_code=400, detail="Simulator not initialized. Call /trading/init first.")
    
    # Register callbacks for broadcasting
    async def on_tick(candles):
        # Broadcast candle updates
        await ws_manager.broadcast({
            "type": "candle",
            "data": {symbol: c.to_dict() for symbol, c in candles.items()},
            "timestamp": candles[list(candles.keys())[0]].timestamp if candles else None,
        })
        
        # Have agent process the tick
        if agent and agent.state.running:
            trades = await agent.process_tick(candles)
            for trade in trades:
                await ws_manager.broadcast({
                    "type": "trade",
                    "data": trade,
                })

        # Evaluate SL/TP triggers for all users with open positions
        try:
            for user_id in fetch_users_with_sim_positions():
                positions = fetch_sim_positions(user_id)
                pos_by_sym = {p["symbol"]: p for p in positions}
                for symbol, candle in candles.items():
                    pos = pos_by_sym.get(symbol)
                    if not pos:
                        continue
                    qty = float(pos.get("quantity") or 0)
                    if qty <= 0:
                        continue
                    sl = pos.get("stop_loss")
                    tp = pos.get("take_profit")
                    if sl is None and tp is None:
                        continue

                    trigger_reason = None
                    trigger_price = None
                    if sl is not None and float(candle.low) <= float(sl):
                        trigger_reason = f"Stop loss hit ({float(sl):.2f})"
                        trigger_price = float(sl)
                    elif tp is not None and float(candle.high) >= float(tp):
                        trigger_reason = f"Take profit hit ({float(tp):.2f})"
                        trigger_price = float(tp)

                    if trigger_reason and trigger_price is not None:
                        trade = _execute_paper_trade(
                            user_id=user_id,
                            symbol=symbol,
                            side="sell",
                            quantity=qty,
                            price=trigger_price,
                            reason=trigger_reason,
                        )
                        await ws_manager.broadcast({
                            "type": "trade",
                            "data": trade,
                        })
        except Exception as e:
            print(f"[Trading] SL/TP evaluation error: {e}")
    
    simulator.register_tick_callback(on_tick)
    
    # Start simulation
    await simulator.start()
    if agent:
        agent.start()
    
    return {"status": "started", "simulator": simulator.get_status()}


@app.post("/trading/trade")
async def place_manual_trade(request: ManualTradeRequest):
    user_id = request.user_id or "default"
    symbol = _normalize_symbol(request.symbol)
    side = str(request.side or "").strip().lower()
    qty = float(request.quantity)
    price = _get_sim_price(symbol)

    if side == "buy":
        _validate_risk_for_long(current_price=price, stop_loss=request.stop_loss, take_profit=request.take_profit)

    trade = _execute_paper_trade(
        user_id=user_id,
        symbol=symbol,
        side=side,
        quantity=qty,
        price=price,
        reason=request.reason or "Manual trade",
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
    )
    await ws_manager.broadcast({"type": "trade", "data": trade})
    return {"trade": trade}


@app.post("/trading/positions/risk")
async def update_position_risk(request: PositionRiskUpdateRequest):
    user_id = request.user_id or "default"
    symbol = _normalize_symbol(request.symbol)
    positions = fetch_sim_positions(user_id)
    pos = next((p for p in positions if p.get("symbol") == symbol), None)
    if not pos or float(pos.get("quantity") or 0) <= 0:
        raise HTTPException(status_code=400, detail="No open position for symbol")

    current_price = _get_sim_price(symbol)
    _validate_risk_for_long(current_price=current_price, stop_loss=request.stop_loss, take_profit=request.take_profit)

    upsert_sim_position(
        user_id=user_id,
        symbol=symbol,
        quantity=float(pos.get("quantity") or 0),
        avg_price=float(pos.get("avg_price") or 0),
        unrealized_pnl=pos.get("unrealized_pnl"),
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
    )
    return {"ok": True}


@app.post("/trading/stop")
async def stop_trading(request: TradingControlRequest):
    """Stop the trading simulation."""
    simulator = get_simulator()
    agent = get_trading_agent()
    
    if simulator:
        await simulator.stop()
    if agent:
        agent.stop()
    
    return {"status": "stopped"}


@app.post("/trading/pause")
async def pause_trading():
    """Pause the trading simulation."""
    simulator = get_simulator()
    if simulator:
        simulator.pause()
        return {"status": "paused"}
    raise HTTPException(status_code=400, detail="Simulator not running.")


@app.post("/trading/resume")
async def resume_trading():
    """Resume the trading simulation."""
    simulator = get_simulator()
    if simulator:
        simulator.resume()
        return {"status": "resumed"}
    raise HTTPException(status_code=400, detail="Simulator not running.")


@app.post("/trading/speed")
async def set_speed(request: SpeedChangeRequest):
    """Change simulation speed."""
    simulator = get_simulator()
    if simulator:
        simulator.set_speed(request.speed_multiplier)
        return {"status": "speed_changed", "speed_multiplier": request.speed_multiplier}
    raise HTTPException(status_code=400, detail="Simulator not initialized.")


@app.get("/trading/status")
def get_trading_status(user_id: str = "default"):
    """Get current trading simulation status."""
    simulator = get_simulator()
    agent = get_trading_agent()
    
    return {
        "simulator": simulator.get_status() if simulator else None,
        "agent": agent.get_status() if agent else None,
    }


@app.get("/trading/positions")
def get_positions(user_id: str = "default"):
    """Get current simulated positions."""
    positions = fetch_sim_positions(user_id)
    return {"positions": positions}


@app.get("/trading/trades")
def get_trades(user_id: str = "default", limit: int = 100):
    """Get trade history."""
    trades = fetch_trades(user_id, limit)
    return {"trades": trades}


@app.get("/trading/prices")
def get_current_prices():
    """Get current simulated prices for all symbols."""
    simulator = get_simulator()
    if simulator:
        return {"prices": simulator.get_current_prices()}
    return {"prices": {}}


@app.websocket("/ws/live-feed")
async def websocket_live_feed(websocket: WebSocket):
    """
    WebSocket endpoint for real-time market data and trade notifications.
    
    Messages sent to client:
    - {"type": "candle", "data": {...}, "timestamp": "..."}
    - {"type": "trade", "data": {...}}
    - {"type": "status", "data": {...}}
    """
    await ws_manager.connect(websocket)
    
    try:
        # Send initial status
        simulator = get_simulator()
        agent = get_trading_agent()
        
        await websocket.send_json({
            "type": "status",
            "data": {
                "connected": True,
                "simulator": simulator.get_status() if simulator else None,
                "agent": agent.get_status() if agent else None,
            }
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                # Handle ping/pong or control messages from client
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)