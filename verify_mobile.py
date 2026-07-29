import os
import time
from playwright.sync_api import sync_playwright

def run():
    os.makedirs("/home/jules/verification", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 375, "height": 667},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        # Listen for console logs
        page.on("console", lambda msg: print(f"[CONSOLE]: {msg.text}"))
        # Listen for page errors
        page.on("pageerror", lambda err: print(f"[PAGE ERROR]: {err}"))

        print("Navigating to MyAgent IDE...")
        page.goto("http://127.0.0.1:8000")

        print("Waiting for page and Monaco Editor initialization...")
        time.sleep(8)

        print("Taking mobile editor screenshot...")
        page.screenshot(path="/home/jules/verification/mobile_editor.png")

        try:
            print("Switching view to Explorer...")
            page.get_by_text("Explorer", exact=True).click(timeout=5000)
            time.sleep(2)
            page.screenshot(path="/home/jules/verification/mobile_explorer.png")

            print("Switching view to AI Chat...")
            page.get_by_text("AI Chat", exact=True).click(timeout=5000)
            time.sleep(2)
            page.screenshot(path="/home/jules/verification/mobile_chat.png")

            print("Toggling mobile top hamburger menu...")
            page.locator("button[title='Toggle Menu']").click(timeout=5000)
            time.sleep(1)
            page.screenshot(path="/home/jules/verification/mobile_menu.png")
        except Exception as e:
            print(f"Interactive actions failed: {e}")

        browser.close()
        print("Mobile verification complete!")

if __name__ == "__main__":
    run()
