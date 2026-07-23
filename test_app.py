import importlib
import os
import unittest
import shutil
import json
import asyncio
from unittest.mock import patch
from fastapi.testclient import TestClient

# Import the tools to test them directly
from agent.tools import (
    read_file_tool, patch_file_tool, view_dir_tool,
    execute_command_tool, clone_repository_tool,
    git_status_tool, git_rollback_tool, WORKSPACE_DIR,
    write_file_tool, list_directory_tool
)
from agent.agent import ChatAgent

class AppTests(unittest.TestCase):
    def setUp(self):
        # Setup workspace folder for testing
        if os.path.exists(WORKSPACE_DIR):
            shutil.rmtree(WORKSPACE_DIR)
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
        self.client = TestClient(importlib.import_module("app").app)

    def tearDown(self):
        # Clean up testing workspace
        if os.path.exists(WORKSPACE_DIR):
            shutil.rmtree(WORKSPACE_DIR)

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

    # === IDE AGENT & SECURITY TESTS ===

    def test_security_endpoints_require_token(self):
        """Verify that security tools/agent endpoints require the correct X-API-Token header."""
        endpoints_to_test = [
            ("/api/agent/run", {"instruction": "test instruction"}),
            ("/api/tools/read_file", {"filepath": "test.py"}),
            ("/api/tools/patch_file", {"filepath": "test.py", "replace_block": "print(1)"}),
            ("/api/tools/view_dir", {}),
            ("/api/tools/execute_command", {"command": "echo 1"}),
            ("/api/tools/clone_repository", {"repo_url": "https://github.com/test/test.git"}),
            ("/api/tools/git_status", None),
            ("/api/tools/git_rollback", None),
        ]

        for path, payload in endpoints_to_test:
            # 1. No token should return 403
            if payload is None:
                resp = self.client.post(path)
            else:
                resp = self.client.post(path, json=payload)
            self.assertEqual(resp.status_code, 403, f"Expected 403 for {path} with no token")

            # 2. Wrong token should return 403
            if payload is None:
                resp = self.client.post(path, headers={"X-API-Token": "wrong-token"})
            else:
                resp = self.client.post(path, json=payload, headers={"X-API-Token": "wrong-token"})
            self.assertEqual(resp.status_code, 403, f"Expected 403 for {path} with wrong token")

            # 3. Correct token should pass authentication (may return 200 or other mock success, not 403)
            # We'll use the default token defined: "super-secret-ide-agent-token-123"
            headers = {"X-API-Token": "super-secret-ide-agent-token-123"}
            if payload is None:
                resp = self.client.post(path, headers=headers)
            else:
                resp = self.client.post(path, json=payload, headers=headers)
            self.assertNotEqual(resp.status_code, 403, f"Expected authenticated pass for {path}")

    def test_direct_file_system_tools(self):
        """Test file creation, patching, reading, and view dir tools."""
        # 1. Patch to create new file
        res = patch_file_tool("test_code.py", search_block="", replace_block="print('hello world')")
        self.assertEqual(res["status"], "success")

        # 2. Read back
        res_read = read_file_tool("test_code.py")
        self.assertEqual(res_read["status"], "success")
        self.assertEqual(res_read["content"], "print('hello world')")

        # 3. Patch existing file
        res_patch = patch_file_tool("test_code.py", search_block="print('hello world')", replace_block="print('hello universe')")
        self.assertEqual(res_patch["status"], "success")

        # 4. Read back updated
        res_read2 = read_file_tool("test_code.py")
        self.assertEqual(res_read2["status"], "success")
        self.assertEqual(res_read2["content"], "print('hello universe')")

        # 5. View directory structure
        res_dir = view_dir_tool()
        self.assertEqual(res_dir["status"], "success")
        self.assertIn("test_code.py", res_dir["files"])

        # 6. Test direct write file tool
        res_write = write_file_tool("direct_write.py", "print('direct')")
        self.assertEqual(res_write["status"], "success")

        # 7. Test direct list directory tool
        res_list = list_directory_tool()
        self.assertEqual(res_list["status"], "success")
        self.assertIn("direct_write.py", res_list["files"])

    def test_direct_execute_command_tool(self):
        """Test terminal execution tool."""
        res = execute_command_tool("echo 'Jules is here'")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["returncode"], 0)
        self.assertIn("Jules is here", res["stdout"])

    def test_chat_agent_tool_calling(self):
        """Test that ChatAgent tool calling processes tool calls and executes them correctly."""
        agent_instance = ChatAgent()

        # We mock the post requests in sequence:
        # First call: returns a tool call requesting write_file
        # Second call: returns the final text response
        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code
            def json(self):
                return self._json

        mock_responses = [
            MockResponse({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_mock123",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps({"filepath": "hello_test.txt", "content": "Hello from mock!"})
                            }
                        }]
                    }
                }],
                "usage": {"total_tokens": 50}
            }),
            MockResponse({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "I have successfully written the file for you.",
                        "tool_calls": None
                    }
                }],
                "usage": {"total_tokens": 100}
            })
        ]

        response_iterator = iter(mock_responses)

        async def mock_post(*args, **kwargs):
            return next(response_iterator)

        with patch.dict(os.environ, {"GROQ_API_KEY": "mock_key"}):
            agent_instance = ChatAgent() # reload keys
            with patch("httpx.AsyncClient.post", side_effect=mock_post):
                # Run get_response
                result = asyncio.run(agent_instance.get_response("Write a file named hello_test.txt with 'Hello from mock!'"))

                # Assertions
                self.assertEqual(result["model"], "Groq (Llama-3.3-70b)")
                self.assertEqual(result["reply"], "I have successfully written the file for you.")

            # Verify file was actually written in the workspace!
            file_path = os.path.join(WORKSPACE_DIR, "hello_test.txt")
            self.assertTrue(os.path.exists(file_path))
            with open(file_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "Hello from mock!")

    def test_mcp_config_endpoints(self):
        """Test active MCP config retrieval, formatting validation, and save endpoints."""
        # 1. Test GET config returns 200
        get_resp = self.client.get("/api/mcp/config")
        self.assertEqual(get_resp.status_code, 200)
        self.assertIn("mcpServers", get_resp.json())

        # 2. Test POST invalid syntax JSON returns 400
        post_bad_syntax = self.client.post("/api/mcp/config", json={"config_raw": "invalid: syntax { ]"})
        self.assertEqual(post_bad_syntax.status_code, 400)
        self.assertIn("Invalid JSON Syntax", post_bad_syntax.json()["detail"])

        # 3. Test POST invalid structure JSON returns 400
        post_bad_struct = self.client.post("/api/mcp/config", json={"config_raw": '{"badKey": []}'})
        self.assertEqual(post_bad_struct.status_code, 400)
        self.assertIn("mcpServers", post_bad_struct.json()["detail"])

        # 4. Test POST valid config returns 200
        valid_raw = '{\n  "mcpServers": {\n    "roblox-studio": {\n      "url": "http://localhost:3000"\n    }\n  }\n}'
        post_ok = self.client.post("/api/mcp/config", json={"config_raw": valid_raw})
        self.assertEqual(post_ok.status_code, 200)
        self.assertEqual(post_ok.json()["status"], "success")

        # 5. Verify saved changes are returned in next GET
        verify_resp = self.client.get("/api/mcp/config")
        self.assertEqual(verify_resp.status_code, 200)
        self.assertIn("roblox-studio", verify_resp.json()["mcpServers"])

    def test_pwa_manifest_and_favicon_endpoints(self):
        """Test that PWA manifest and favicon endpoints are served correctly."""
        # 1. Test GET /manifest.json
        resp = self.client.get("/manifest.json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("content-type"), "application/json")
        manifest_data = resp.json()
        self.assertEqual(manifest_data.get("short_name"), "MyAgent")
        self.assertEqual(manifest_data.get("display"), "standalone")

        # 2. Test GET /favicon.ico
        resp_favicon = self.client.get("/favicon.ico")
        self.assertEqual(resp_favicon.status_code, 200)
        self.assertEqual(resp_favicon.headers.get("content-type"), "image/x-icon")

if __name__ == "__main__":
    unittest.main()
