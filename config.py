import os
from dotenv import load_dotenv
load_dotenv()

def get_api_key():
    api_key = os.environ.get("LLM_API_KEY")
    if api_key is None:
        raise ValueError("LLM_API_KEY environment variable not set.")
    return api_key

LLM_API_KEY = get_api_key()
