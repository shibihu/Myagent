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
