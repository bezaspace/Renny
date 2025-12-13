import os
import json
import re
from typing import Literal, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END, add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage
from typing_extensions import TypedDict, Annotated

from backend.tools import get_stock_chart_data, calculate_momentum_indicator, run_comprehensive_analysis, build_full_analysis_payload

# Define the tools
tools = [get_stock_chart_data, calculate_momentum_indicator, run_comprehensive_analysis]

# Initialize the model
analysis_model = ChatOpenAI(
    model=os.environ.get("OPENAI_MODEL_NAME", "qwen3-coder-plus"),
    temperature=0,
    base_url=os.environ.get("OPENAI_API_BASE")
)

model = ChatOpenAI(
    model=os.environ.get("OPENAI_MODEL_NAME", "qwen3-coder-plus"),
    temperature=0,
    base_url=os.environ.get("OPENAI_API_BASE")
).bind_tools(tools)


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    fa_active: bool
    fa_symbol: Optional[str]
    fa_horizon: Optional[str]
    fa_risk: Optional[str]
    fa_style: Optional[str]
    fa_pending: Optional[str]

# Define the nodes
def chatbot(state: MessagesState):
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}

def should_continue(state: MessagesState) -> Literal["tools", END]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


def _is_full_analysis_request(text: str) -> bool:
    t = (text or "").lower()
    return ("full analysis" in t) or ("comprehensive" in t and "analysis" in t)


def _extract_symbol(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"\b(?:on|for)\s+([A-Za-z0-9\.]{2,30})\b", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip().upper()
    tokens = re.findall(r"\b[A-Za-z]{2,15}\b", text)
    if not tokens:
        return None
    ignore = {
        "FULL",
        "ANALYSIS",
        "COMPREHENSIVE",
        "STOCK",
        "SHARE",
        "PLEASE",
        # Full-analysis questionnaire choices
        "INTRADAY",
        "SWING",
        "INVEST",
        "INVESTING",
        "CONSERVATIVE",
        "BALANCED",
        "AGGRESSIVE",
        "TREND",
        "BREAKOUT",
        "MEAN",
        "REVERSION",
        "RANGE",
    }
    for tok in reversed(tokens):
        up = tok.upper()
        if up not in ignore:
            return up
    return None


def _normalize_choice(text: str, options: dict[str, str]) -> Optional[str]:
    if not text:
        return None
    t = text.strip().lower()
    for k, v in options.items():
        if k in t:
            return v
    return None


def full_analysis_step(state: AgentState):
    messages = state.get("messages", [])
    last_human = None
    for m in reversed(messages):
        if m.type == "human":
            last_human = m
            break

    user_text = last_human.content if last_human else ""
    fa_active = bool(state.get("fa_active"))
    fa_pending = state.get("fa_pending")
    symbol = state.get("fa_symbol")

    # Guard against previously-stored questionnaire answers being incorrectly persisted as the symbol.
    if symbol is not None:
        bad_symbols = {
            "INTRADAY",
            "SWING",
            "INVEST",
            "INVESTING",
            "CONSERVATIVE",
            "BALANCED",
            "AGGRESSIVE",
            "TREND",
            "BREAKOUT",
            "MEAN",
            "REVERSION",
            "RANGE",
        }
        if str(symbol).strip().upper() in bad_symbols:
            symbol = None

    # Only extract a symbol from the user's message when we're actually expecting a symbol.
    # Otherwise answers like "swing" (horizon) can get incorrectly stored as the symbol.
    if symbol is None and (not fa_active or fa_pending in (None, "symbol")):
        symbol = _extract_symbol(user_text)

    horizon_options = {
        "intraday": "intraday",
        "intra day": "intraday",
        "day trade": "intraday",
        "swing": "swing",
        "short term": "swing",
        "invest": "investing",
        "investing": "investing",
        "long term": "investing",
    }
    risk_options = {
        "conservative": "conservative",
        "low": "conservative",
        "balanced": "balanced",
        "medium": "balanced",
        "aggressive": "aggressive",
        "high": "aggressive",
    }
    style_options = {
        "trend": "trend",
        "trend following": "trend",
        "breakout": "breakout",
        "mean": "mean_reversion",
        "reversion": "mean_reversion",
        "range": "mean_reversion",
    }

    fa_horizon = state.get("fa_horizon")
    fa_risk = state.get("fa_risk")
    fa_style = state.get("fa_style")

    if fa_pending == "horizon" and fa_horizon is None:
        fa_horizon = _normalize_choice(user_text, horizon_options)
    if fa_pending == "risk" and fa_risk is None:
        fa_risk = _normalize_choice(user_text, risk_options)
    if fa_pending == "style" and fa_style is None:
        fa_style = _normalize_choice(user_text, style_options)

    if fa_horizon is None:
        q = "Choose your time horizon for full analysis: Intraday, Swing, or Investing."
        return {
            "messages": [AIMessage(content=q)],
            "fa_active": True,
            "fa_symbol": symbol,
            "fa_horizon": fa_horizon,
            "fa_risk": fa_risk,
            "fa_style": fa_style,
            "fa_pending": "horizon",
        }

    if fa_risk is None:
        q = "What is your risk tolerance: Conservative, Balanced, or Aggressive?"
        return {
            "messages": [AIMessage(content=q)],
            "fa_active": True,
            "fa_symbol": symbol,
            "fa_horizon": fa_horizon,
            "fa_risk": fa_risk,
            "fa_style": fa_style,
            "fa_pending": "risk",
        }

    if fa_style is None:
        q = "Preferred style: Trend following, Breakout, or Mean reversion?"
        return {
            "messages": [AIMessage(content=q)],
            "fa_active": True,
            "fa_symbol": symbol,
            "fa_horizon": fa_horizon,
            "fa_risk": fa_risk,
            "fa_style": fa_style,
            "fa_pending": "style",
        }

    if not symbol:
        return {
            "messages": [AIMessage(content="Which stock symbol should I analyze?")],
            "fa_active": True,
            "fa_symbol": None,
            "fa_horizon": fa_horizon,
            "fa_risk": fa_risk,
            "fa_style": fa_style,
            "fa_pending": "symbol",
        }

    if fa_horizon == "intraday":
        interval = "30minute"
        lookback_days = 30
    elif fa_horizon == "investing":
        interval = "week"
        lookback_days = 365 * 3
    else:
        interval = "day"
        lookback_days = 365

    visuals = build_full_analysis_payload(
        symbol=symbol,
        interval=interval,
        lookback_days=lookback_days,
    )
    tool_msg = ToolMessage(content=json.dumps(visuals, default=str), tool_call_id="full_analysis_visuals")

    summary_prompt = [
        SystemMessage(
            content=(
                "You are a trading analyst. Use the provided technical snapshot and candlestick patterns to produce a concise, actionable full analysis. "
                "Output must include: Market bias, Key levels, Setup, Entry trigger, Stop/invalidation, Targets, Risk notes, and what would change your view."
            )
        ),
        HumanMessage(
            content=json.dumps(
                {
                    "symbol": symbol,
                    "horizon": fa_horizon,
                    "risk": fa_risk,
                    "style": fa_style,
                    "patterns": visuals.get("patterns", []),
                    "interval": interval,
                    "series": visuals.get("series", {}),
                },
                default=str,
            )
        ),
    ]
    summary = analysis_model.invoke(summary_prompt)

    return {
        "messages": [tool_msg, summary],
        "fa_active": False,
        "fa_symbol": symbol,
        "fa_horizon": fa_horizon,
        "fa_risk": fa_risk,
        "fa_style": fa_style,
        "fa_pending": None,
    }

from langgraph.checkpoint.memory import MemorySaver

# Define the graph
workflow = StateGraph(AgentState)

def route_from_start(state: AgentState) -> Literal["full_analysis", "chatbot"]:
    messages = state.get("messages", [])
    last_human = None
    for m in reversed(messages):
        if m.type == "human":
            last_human = m
            break
    if state.get("fa_active"):
        return "full_analysis"
    if last_human and _is_full_analysis_request(last_human.content):
        return "full_analysis"
    return "chatbot"

workflow.add_node("chatbot", chatbot)
workflow.add_node("tools", ToolNode(tools))
workflow.add_node("full_analysis", full_analysis_step)

workflow.add_conditional_edges(START, route_from_start, ["full_analysis", "chatbot"])
workflow.add_edge("full_analysis", END)
workflow.add_conditional_edges("chatbot", should_continue, ["tools", END])
workflow.add_edge("tools", "chatbot")

# Compile the graph
checkpointer = MemorySaver()
agent = workflow.compile(checkpointer=checkpointer)
