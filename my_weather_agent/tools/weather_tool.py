import os
import requests
from langchain_core.tools import tool
 
 
@tool
def get_weather(city: str) -> str:
    """Get current weather forecast for a given city."""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
 
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return f"Could not fetch weather for '{city}'."
 
    data = response.json()
    temp = data["main"]["temp"]
    desc = data["weather"][0]["description"]
    humidity = data["main"]["humidity"]
    return f"{city}: {temp}°C, {desc}, humidity {humidity}%"
 