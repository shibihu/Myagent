import os
from groq import Groq
from config import GROQ_API_KEY


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY") or GROQ_API_KEY
    if not api_key:
        return None
    return Groq(api_key=api_key)