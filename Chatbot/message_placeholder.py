from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder 
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
#chat_template 
chat_template = ChatPromptTemplate([
('system','You are a helpful customer support assistant.'),
MessagesPlaceholder(variable_name='chat_history'),
('human','{query}')
]
)
#load_chat_history
chat_history = []
with open('chat_history.txt','r') as f:
  chat_history.extend(f.readlines())
print(chat_history)
#create prompt 
prompt = chat_template.invoke({'chat_history':chat_history,'query':'Where is my refund'}) 

print(prompt)