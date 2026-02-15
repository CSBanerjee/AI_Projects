from langchain_openai import ChatOpenAI
from dotenv import load_dotenv 
from langchain_core.prompts import PromptTemplate,load_prompt
import streamlit as st
load_dotenv()
model = ChatOpenAI(model='gpt-4')

st.header('Recipe Tool') 
recipe_input = st.selectbox( "Select Recipe Name", ["Chicken Piccata with Bread Salad", "Yorkshire Lamb Patties", "Crispy Calamari Rings", "Roast Turkey with Cranberry Sauce"] )
style_input = st.selectbox( "Select Explanation Style", ["Beginner-Friendly", "Medium Home Friendly", "Professional Hotel Standard", "5 Star Competition Level"] )
length_input = st.selectbox( "Select Explanation Length", ["Short (1-2 paragraphs)", "Medium (3-5 paragraphs)", "Long (detailed explanation)"] )

#template
template = load_prompt('recipe_generator_template.json') 

if st.button("Summarize"):
    chain = template | model
    result = chain.invoke({
        'recipe_input': recipe_input,
        'style_input': style_input,
        'length_input': length_input
    })
    st.write(result.content)
    