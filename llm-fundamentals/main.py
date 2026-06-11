import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")
tokens = enc.encode("Hello, world!")

print(f"Tokens: {tokens}")
print(f"Token count: {len(tokens)}")