from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()
history = []

print("Chat started. Type 'quit' to exit.\n")

while True:
    user_input = input("You: ")
    
    if user_input.lower() == "quit":
        break
    
    history.append({"role": "user", "content": user_input})
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=history
    )
    
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    
    print(f"AI: {reply}\n")