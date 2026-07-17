from groq import Groq

from config import GROQ_API_KEY, MODEL

client = Groq(api_key=GROQ_API_KEY)


def ask_groq(system_prompt: str, user_message: str) -> str:

    response = client.chat.completions.create(

        model=MODEL,

        messages=[

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_message
            }

        ]

    )

    return response.choices[0].message.content