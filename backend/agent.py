import os
from typing import Literal
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage

from backend.tools import get_stock_chart_data, calculate_momentum_indicator

# Define the tools
tools = [get_stock_chart_data, calculate_momentum_indicator]

# Initialize the model
model = ChatOpenAI(
    model=os.environ.get("OPENAI_MODEL_NAME", "qwen3-coder-plus"),
    temperature=0,
    base_url=os.environ.get("OPENAI_API_BASE")
).bind_tools(tools)

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

from langgraph.checkpoint.memory import MemorySaver

# Define the graph
workflow = StateGraph(MessagesState)

workflow.add_node("chatbot", chatbot)
workflow.add_node("tools", ToolNode(tools))

workflow.add_edge(START, "chatbot")
workflow.add_conditional_edges("chatbot", should_continue, ["tools", END])
workflow.add_edge("tools", "chatbot")

# Compile the graph
checkpointer = MemorySaver()
agent = workflow.compile(checkpointer=checkpointer)
