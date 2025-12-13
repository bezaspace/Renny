import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
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
        
        # Serialize messages for the frontend
        serialized_messages = []
        for msg in messages:
            msg_type = msg.type
            content = msg.content
            tool_calls = getattr(msg, "tool_calls", [])
            
            # Pre-process tool messages to avoid sending massive JSON dumps to frontend
            if msg_type == 'tool':
                try:
                    data = json.loads(content)
                    # Check if this is the comprehensive analysis result
                    if isinstance(data, dict) and "indicators" in data and "symbol" in data:
                        # Replace content with a summary card format that the frontend supports
                        # Frontend looks for 'indicator' and 'analysis' keys to render a nice card
                        # WE MUST PRESERVE 'data' (chart) and 'overlays' for the frontend to render the chart!
                        content = json.dumps({
                            "symbol": data.get("symbol"),
                            "indicator": "Technical Analysis Scan",
                            "analysis": "Comprehensive set of indicators calculated successfully. See the summary below for insights.",
                            "data": data.get("data"),
                            "overlays": data.get("overlays"),
                            "series": data.get("series")
                        })
                except Exception:
                    # If it's not JSON or parsing fails, leave it as is
                    pass
            
            serialized_messages.append({
                "type": msg_type,
                "content": content,
                "tool_calls": tool_calls,
                "id": getattr(msg, "id", None)
            })
            
        return {"messages": serialized_messages}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "ok"}