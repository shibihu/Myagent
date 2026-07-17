from pathlib import Path

from agent.groq import ask_groq


PROMPT_PATH = Path("prompts/system.txt")


def chat(message: str) -> str:

    system_prompt = PROMPT_PATH.read_text(
        encoding="utf-8"
    )

    return ask_groq(system_prompt, message)