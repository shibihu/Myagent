import os
from agent.groq import get_groq_client


class ChatAgent:
    def __init__(self):
        self.client = get_groq_client()
        self.is_configured = self.client is not None

        # Load system instruction context dynamically
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        system_prompt_path = os.path.join(root_dir, "prompts", "system.txt")

        if os.path.exists(system_prompt_path):
            with open(system_prompt_path, "r", encoding="utf-8") as file:
                self.system_prompt = file.read()
        else:
            self.system_prompt = "You are a helpful and intelligent AI assistant."

    async def get_response(self, user_message: str) -> str:
        if not self.is_configured:
            return "⚠️ Groq API is not configured yet. Add your GROQ_API_KEY to the .env file or environment variables to enable AI replies."

        try:
            # Call Groq API via standard non-blocking completion parsing
            completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"⚠️ Core System Connection Error: {str(e)}"