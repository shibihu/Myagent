import os
from groq import Groq
from config import GROQ_API_KEY

def get_groq_client():
    if not GROQ_API_KEY:
        raise ValueError("CRITICAL: GROQ_API_KEY is missing from environment/env configurations.")
    return Groq(api_key=GROQ_API_KEY)