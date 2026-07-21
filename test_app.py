import importlib
import os
import unittest
import shutil
from unittest.mock import patch
from fastapi.testclient import TestClient

# Import the tools to test them directly
from agent.tools import (
    read_file_tool, patch_file_tool, view_dir_tool,
    execute_command_tool, clone_repository_tool,
    git_status_tool, git_rollback_tool, WORKSPACE_DIR,
    write_file_tool, list_directory_tool
)

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

if __name__ == "__main__":
    unittest.main()
