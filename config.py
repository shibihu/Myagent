import os
from dotenv import load_dotenv

# Ensure the environment config finds the .env file regardless of runtime location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")