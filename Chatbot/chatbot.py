from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

load_dotenv()
model = ChatOpenAI(model="gpt-4", temperature=0.7)
chat_history = [ ]

while True:
  user_input = input("You: ")
  if user_input.lower() == "exit":
    print("Exiting chatbot. Goodbye!")
    break
  else:
    chat_history.append(HumanMessage(content=user_input))
    result = model.invoke(chat_history)
    chat_history.append(AIMessage(content=result.content))
    print("AI: ", result.content)

print("Chat history: ", chat_history)

