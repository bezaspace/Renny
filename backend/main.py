import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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
)
from backend.tools import build_full_analysis_payload

load_dotenv()

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
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL_NAME", "qwen3-coder-plus"),
        temperature=0,
        base_url=os.environ.get("OPENAI_API_BASE"),
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