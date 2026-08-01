import os
import traceback
import groq
from groq import Groq
from dotenv import load_dotenv

# Load .env (ถ้ามี)
load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")

print("=" * 60)
print("Python Test for Groq")
print("=" * 60)
print(f"Python Version : {os.sys.version}")
print(f"API Key Loaded : {API_KEY is not None}")

if API_KEY:
    print(f"API Key Prefix : {API_KEY[:10]}...")
else:
    print("ERROR: GROQ_API_KEY not found!")
    exit()

print("=" * 60)

try:
    client = Groq(api_key=API_KEY)

    print("Sending request to Groq...")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": "Say Hello!"
            }
        ],
    )

    print("\nSUCCESS!")
    print("=" * 60)
    print(response.choices[0].message.content)

except groq.AuthenticationError as e:
    print("\nAuthentication Error")
    print(repr(e))

except groq.PermissionDeniedError as e:
    print("\nPermission Denied")
    print(repr(e))

except groq.RateLimitError as e:
    print("\nRate Limit")
    print(repr(e))

except groq.NotFoundError as e:
    print("\nModel Not Found")
    print(repr(e))

except groq.APIConnectionError as e:
    print("\nAPI Connection Error")
    print("Exception:", repr(e))
    print("Cause:", repr(e.__cause__))

    print("\nFull Traceback:")
    traceback.print_exc()

except Exception as e:
    print("\nUnknown Error")
    print(type(e).__name__)
    print(repr(e))
    traceback.print_exc()