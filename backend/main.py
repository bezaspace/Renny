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

load_dotenv()

app = FastAPI()

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