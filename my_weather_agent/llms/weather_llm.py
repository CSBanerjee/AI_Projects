from langchain_openai import ChatOpenAI
import os 
from dotenv import load_dotenv 

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
  raise ValueError("OPENAI_API_KEY is not set")

llm  = ChatOpenAI(model=os.getenv("OPENAI_MODEL","gpt-4o-mini"),
                  temperature=float(os.getenv("OPENAI_TEMP","0"))
                  )