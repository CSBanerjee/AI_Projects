import streamlit as st
from langchain_core.messages import HumanMessage
from agents import app
 
st.title("🌤️ Weather Agent")
 
city = st.text_input("Enter a city name")
 
if st.button("Get Weather"):
    if city.strip() == "":
        st.warning("Please enter a city name.")
    else:
        with st.spinner("Fetching weather..."):
            result = app.invoke({
                "messages": [HumanMessage(content=f"What is the weather in {city}?")],
                "weather_state": ""
            })
        st.success(result["messages"][-1].content)
 