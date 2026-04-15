# ==============================================================================
# agents/weather_agent.py
#
# This file is the BRAIN of the project.
# It builds the LangGraph "graph" — which is the decision-making loop
# that controls how the agent thinks, calls tools, and forms answers.
#
# Think of it like a flowchart:
#
#   User message comes in
#         │
#         ▼
#   [agent node]  → LLM thinks: "Do I need to call a tool?"
#         │
#    Yes  │  No
#         │   └──→ Return final answer to user
#         ▼
#   [tools node]  → get_weather() runs, fetches real data
#         │
#         └──→ back to [agent node] → LLM forms final answer
#
# ==============================================================================


# StateGraph is LangGraph's main class for building the decision loop (the graph)
# END is a special marker that tells the graph "stop here, we are done"
from langgraph.graph import StateGraph, END

# ToolNode is a pre-built LangGraph node that automatically runs
# whichever tool the LLM decided to call
from langgraph.prebuilt import ToolNode

# Our custom state — defines the shape of data flowing through the graph
# (messages list + weather_state string)
from states import WeatherState

# The base LLM (ChatOpenAI) — no tools attached yet
from llms import llm

# The list of all available tools — [get_weather]
from tools import all_tools


# ------------------------------------------------------------------------------
# STEP 1 — Attach tools to the LLM
# ------------------------------------------------------------------------------
# .bind_tools() tells the LLM which tools it is allowed to call.
# Without this, the LLM would just answer from its own training knowledge
# and never reach out to the real weather API.
#
# llm           = plain ChatOpenAI model
# llm_with_tools = same model but now aware that get_weather exists
#
# The LLM doesn't call the tool itself — it just signals "I want to call
# get_weather with city=Hyderabad" and LangGraph handles the actual execution.
llm_with_tools = llm.bind_tools(all_tools)


# ------------------------------------------------------------------------------
# STEP 2 — Define the AGENT node
# ------------------------------------------------------------------------------
# This function is called every time the graph reaches the "agent" node.
# Its job is to pass the current messages to the LLM and get a response.
#
# "state" is the current snapshot of the conversation —
# it contains all messages exchanged so far.
def call_model(state: WeatherState):

    # Send ALL messages so far to the LLM.
    # The LLM reads the full conversation history and decides:
    #   Option A → "I have enough info, I'll answer directly"
    #   Option B → "I need real data, I'll call get_weather()"
    response = llm_with_tools.invoke(state["messages"])

    # Return the LLM's response.
    # LangGraph automatically appends it to state["messages"]
    # because of the add_messages reducer we defined in WeatherState.
    #
    # We also update weather_state to track where we are in the flow.
    return {
        "messages": [response],
        "weather_state": "llm_responded"
    }


# ------------------------------------------------------------------------------
# STEP 3 — Define the ROUTER (conditional edge)
# ------------------------------------------------------------------------------
# After the agent node runs, LangGraph calls this function to decide
# what to do next — go to the tools node, or stop?
#
# This is the "fork in the road" of the flowchart.
def should_continue(state: WeatherState):

    # Get the last message in the conversation — the LLM's most recent response
    last_message = state["messages"][-1]

    # Did the LLM decide to call a tool?
    # If yes, it will have attached "tool_calls" to its response.
    # tool_calls looks like: [{"name": "get_weather", "args": {"city": "Hyderabad"}}]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Yes — send the flow to the "tools" node to actually run get_weather()
        return "tools"

    # No tool calls — the LLM has a final answer ready.
    # END tells LangGraph to stop the loop and return the response to the user.
    return END


# ------------------------------------------------------------------------------
# STEP 4 — Create the ToolNode
# ------------------------------------------------------------------------------
# ToolNode is a pre-built LangGraph helper that:
#   1. Reads which tool the LLM wants to call (e.g. get_weather)
#   2. Reads the arguments the LLM wants to pass (e.g. city="Hyderabad")
#   3. Actually calls that function
#   4. Returns the result as a ToolMessage back into the state
#
# We pass it all_tools so it knows which functions are available to run.
tool_node = ToolNode(all_tools)


# ------------------------------------------------------------------------------
# STEP 5 — Build the graph
# ------------------------------------------------------------------------------
# StateGraph is like a flowchart builder.
# We tell it what type of state flows through it (WeatherState).
graph = StateGraph(WeatherState)

# Add the two nodes to the graph:
#   "agent" → runs call_model() — the LLM thinking step
#   "tools" → runs tool_node   — the tool execution step
graph.add_node("agent", call_model)
graph.add_node("tools", tool_node)

# Set the entry point — when the graph starts, always go to "agent" first
graph.set_entry_point("agent")

# Add a conditional edge FROM the "agent" node.
# After "agent" runs, call should_continue() to decide where to go next:
#   → "tools"  if the LLM wants to call a tool
#   → END      if the LLM has a final answer
graph.add_conditional_edges("agent", should_continue)

# Add a fixed edge FROM "tools" back TO "agent".
# After a tool runs and returns its result, always go back to the LLM
# so it can read the tool result and form a final answer.
graph.add_edge("tools", "agent")


# ------------------------------------------------------------------------------
# STEP 6 — Compile the graph
# ------------------------------------------------------------------------------
# .compile() takes the graph definition (nodes + edges) and turns it into
# a runnable object called "app".
#
# Nothing runs yet — this just assembles and validates the structure.
# The actual execution happens in main.py when app.invoke() is called.
app = graph.compile()