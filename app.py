"""
=========================================
MyAgent
Main Entry Point
=========================================
"""

from chat import start_chat


def main():
    print("=" * 40)
    print("🤖 MyAgent")
    print("Powered by Groq")
    print("Type 'exit' to quit.")
    print("=" * 40)

    start_chat()


if __name__ == "__main__":
    main()