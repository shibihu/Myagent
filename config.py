"""
=========================================
MyAgent
Configuration
=========================================
"""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================
# API Keys
# ==========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ==========================
# Model Settings
# ==========================

GROQ_MODEL = "llama-3.3-70b-versatile"

# ==========================
# Application Settings
# ==========================

APP_NAME = "MyAgent"
VERSION = "1.0.0"