import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
print(f"API Key: {api_key[:10]}...{api_key[-5:] if api_key else ''}")

try:
    client = Groq(api_key=api_key)
    models = client.models.list()
    print("\n=== Available Models ===")
    for model in models.data:
        print(f"- {model.id} (Created by: {model.owned_by})")
except Exception as e:
    print(f"Error fetching models: {e}")
