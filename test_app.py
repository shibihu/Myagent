import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(importlib.import_module("app").app)

    def test_home_page_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_chat_endpoint_returns_reply(self):
        response = self.client.post("/chat", json={"message": "hello"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("reply", response.json())

    def test_chat_endpoint_with_multipart_files(self):
        # Test sending form data along with multiple file attachments
        response = self.client.post(
            "/chat",
            data={"message": "What is in these files?", "search_web": "false"},
            files=[
                ("files", ("test.txt", b"Hello, this is a plain text file content.", "text/plain")),
                ("files", ("test.png", b"fake_png_bytes", "image/png"))
            ]
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertIn("reply", json_data)
        self.assertIn("chat_id", json_data)
        self.assertIn("title", json_data)

    def test_app_starts_without_groq_key(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
            import config
            import agent.groq as groq_module
            config.GROQ_API_KEY = ""
            groq_module.GROQ_API_KEY = ""
            app_module = importlib.reload(importlib.import_module("app"))
            client = TestClient(app_module.app)
            response = client.get("/")
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
