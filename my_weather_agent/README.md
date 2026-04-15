# 🌤️ Weather Agent

A conversational weather agent built with **LangGraph**, **LangChain**, and **OpenWeatherMap**, running entirely inside a **Docker container** with a **Streamlit** web interface.

---

## What It Does

You type a city name into the web page, click **Get Weather**, and the agent fetches real-time weather data and displays the temperature, conditions, and humidity.

Under the hood, a LangGraph agent loop controls the flow:
- The LLM receives your question
- It decides to call the `get_weather` tool
- The tool hits the OpenWeatherMap API
- The LLM forms a natural language answer
- The answer appears on the page

---

## Project Structure

```
my-weather-agent/
│
├── .devcontainer/
│   └── devcontainer.json       # VS Code Dev Container config
│
├── agents/
│   ├── __init__.py             # exports app
│   └── weather_agent.py        # LangGraph graph — nodes, edges, routing
│
├── llms/
│   ├── __init__.py             # exports llm
│   └── weather_llm.py          # ChatOpenAI setup with env-based config
│
├── states/
│   ├── __init__.py             # exports WeatherState
│   └── agent_state.py          # defines the state shape flowing through the graph
│
├── tools/
│   ├── __init__.py             # exports all_tools
│   └── weather_tool.py         # get_weather() — calls OpenWeatherMap API
│
├── .env                        # API keys (never commit this)
├── .gitignore
├── Dockerfile                  # container definition
├── main.py                     # Streamlit web app — entry point
└── requirements.txt            # Python dependencies
```

---

## Prerequisites

Install these on your host machine before starting:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Visual Studio Code](https://code.visualstudio.com/)
- VS Code extension: **Dev Containers** (`ms-vscode-remote.remote-containers`)

---

## Setup

### 1. Get your API keys

| Key | Where to get it |
|-----|----------------|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) (free tier) |

### 2. Fill in your `.env` file

Open the `.env` file and replace the placeholders with your real keys:

```
OPENAI_API_KEY=your_openai_key_here
OPENWEATHER_API_KEY=your_openweathermap_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMP=0
```

`OPENAI_MODEL` and `OPENAI_TEMP` are optional — the defaults above are used if you leave them out.

### 3. Open in VS Code

```
File → Open Folder → select the my-weather-agent/ folder
```

### 4. Reopen in Container

Press `Ctrl + Shift + P` and run:
```
Dev Containers: Reopen in Container
```

VS Code will build the Docker image and install all dependencies. This takes a minute the first time.

---

## Running the App

Once inside the container, open the integrated terminal (`Ctrl + `` ` ``) and run:

```bash
streamlit run main.py
```

Then open your browser and go to:
```
http://localhost:8501
```

Type a city name, click **Get Weather**, and see the result.

---

## How the Agent Works

```
User types city name
        │
        ▼
   [agent node]          LLM reads the question
        │
        ▼ calls tool
   [tools node]          get_weather(city) hits OpenWeatherMap API
        │
        ▼ returns result
   [agent node]          LLM reads the data, forms final answer
        │
        ▼
       END               Answer displayed on the page
```

Each folder has one clear responsibility:

| Folder | Responsibility |
|--------|---------------|
| `states/` | defines the data shape flowing through the graph |
| `llms/` | creates the base LLM with model and temperature config |
| `tools/` | defines `get_weather()` — the real-world data fetcher |
| `agents/` | binds tools, builds the graph, compiles it into `app` |
| `main.py` | Streamlit UI — the only file you run directly |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `langgraph` | agent loop and graph execution |
| `langchain` | core messages, tools, and abstractions |
| `langchain-openai` | OpenAI LLM connector |
| `python-dotenv` | loads API keys from `.env` |
| `requests` | HTTP calls to OpenWeatherMap |
| `streamlit` | web UI |

---

## Adding More Tools

To add a new tool (e.g. a 5-day forecast):

1. Create the function in `tools/forecast_tool.py` with `@tool`
2. Import and add it to `all_tools` in `tools/__init__.py`
3. Nothing else needs to change — the agent picks it up automatically

```python
# tools/__init__.py
from .weather_tool import get_weather
from .forecast_tool import get_forecast

all_tools = [get_weather, get_forecast]
```

---

## Notes

- Never commit your `.env` file — it is listed in `.gitignore`
- Always run `streamlit run main.py` from the project root folder
- Streamlit auto-reloads when you save changes to any file — no restart needed
- The project folder is bind-mounted into the container, so edits in VS Code are instantly reflected inside Docker