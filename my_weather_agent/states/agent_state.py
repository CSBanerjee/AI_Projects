from typing import TypedDict, Annotated 
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class WeatherState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # add_messages is LangGraph's built-in reducer
    weather_state: str  