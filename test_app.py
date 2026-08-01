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
        self.assertEqual(manifest_data.get("description"), "An intelligent AI agent assistant")
        self.assertEqual(len(manifest_data.get("icons")), 2)
        self.assertEqual(manifest_data["icons"][0]["sizes"], "192x192")
        self.assertEqual(manifest_data["icons"][1]["sizes"], "512x512")

        # 2. Test GET /favicon.ico
        resp_favicon = self.client.get("/favicon.ico")
        self.assertEqual(resp_favicon.status_code, 200)
        self.assertEqual(resp_favicon.headers.get("content-type"), "image/x-icon")

    def test_github_auth_and_user_management(self):
        """Test GitHub OAuth login redirect, mock callback, user registration, JWT generation, and flexible auth policies."""
        from unittest.mock import patch
        import jwt
        from agent.auth import JWT_SECRET, JWT_ALGORITHM

        # 1. Test Login Redirect
        with patch("agent.auth.GITHUB_CLIENT_ID", "mock_id"):
            resp = self.client.get("/auth/github/login", follow_redirects=False)
            self.assertEqual(resp.status_code, 307)
            self.assertTrue(resp.headers.get("location").startswith("https://github.com/login/oauth/authorize"))
            self.assertIn("client_id=mock_id", resp.headers.get("location"))

        # 2. Test Login Redirect Configuration Error
        with patch("agent.auth.GITHUB_CLIENT_ID", ""):
            resp = self.client.get("/auth/github/login")
            self.assertEqual(resp.status_code, 500)

        # 3. Test OAuth Callback with mock exchanges
        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code
            def json(self):
                return self._json

            @property
            def text(self):
                return json.dumps(self._json)

        async def mock_httpx_post_and_get(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "oauth/access_token" in url:
                return MockResponse({"access_token": "mock_github_access_token"})
            elif "api.github.com/user/emails" in url:
                return MockResponse([{"email": "verified_user@bot.local", "primary": True, "verified": True}])
            elif "api.github.com/user" in url:
                return MockResponse({
                    "id": 12345,
                    "login": "test_github_user",
                    "avatar_url": "https://github.com/avatar.png",
                    "email": None  # Trigger fetching from user/emails
                })
            return MockResponse({}, 404)

        with patch("httpx.AsyncClient.post", side_effect=mock_httpx_post_and_get), \
             patch("httpx.AsyncClient.get", side_effect=mock_httpx_post_and_get), \
             patch("agent.auth.GITHUB_CLIENT_ID", "mock_id"), \
             patch("agent.auth.GITHUB_CLIENT_SECRET", "mock_secret"):

            # Invoke the callback
            resp = self.client.get("/auth/github/callback?code=mock_code", follow_redirects=False)
            self.assertEqual(resp.status_code, 307)
            self.assertEqual(resp.headers.get("location"), "/")
            self.assertIn("access_token", resp.headers.get("set-cookie"))

            # Extract the cookie token to test protected routes
            cookie_str = resp.headers.get("set-cookie")
            token_val = None
            for part in cookie_str.split(";"):
                if part.strip().startswith("access_token="):
                    token_val = part.strip().split("=")[1]
                    break
            self.assertIsNotNone(token_val)

            # 4. Test GET /auth/me with both cookie and Bearer Header
            headers = {"Authorization": f"Bearer {token_val}"}
            me_resp = self.client.get("/auth/me", headers=headers)
            self.assertEqual(me_resp.status_code, 200)
            user_data = me_resp.json()
            self.assertEqual(user_data["username"], "test_github_user")
            self.assertEqual(user_data["email"], "verified_user@bot.local")

            # Using Cookie
            self.client.cookies.set("access_token", token_val)
            me_resp_cookie = self.client.get("/auth/me")
            self.assertEqual(me_resp_cookie.status_code, 200)
            self.assertEqual(me_resp_cookie.json()["username"], "test_github_user")
            self.client.cookies.delete("access_token")

        # 5. Test Flexible policy with X-API-Token
        from fastapi import Request
        from agent.auth import get_current_user_or_api_client
        import unittest.mock as mock

        mock_req = mock.Mock()
        mock_req.headers = {"X-API-Token": "super-secret-ide-agent-token-123"}
        res = asyncio.run(get_current_user_or_api_client(mock_req))
        self.assertTrue(res["is_api_client"])
        self.assertEqual(res["username"], "Roblox_Studio_Client")

    def test_supabase_postgres_integration(self):
        """Test database connection health check, ORM mapping to users table, and persistence."""
        from database import check_db_connection, Users
        from unittest.mock import patch, MagicMock

        # 1. Test database ping check success
        with patch("os.getenv", return_value="postgresql://mock_host:5432/mock_db"), \
             patch("sqlalchemy.engine.base.Engine.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value.__enter__.return_value = mock_conn
            res = check_db_connection()
            self.assertTrue(res)

        # 2. Test database ping check failure
        with patch("os.getenv", return_value="postgresql://mock_host:5432/mock_db"), \
             patch("sqlalchemy.engine.base.Engine.connect", side_effect=Exception("Connection refused")):
            res = check_db_connection()
            self.assertFalse(res)

        # 3. Test Users ORM schema mapping fields
        user_record = Users(
            github_id="999888",
            username="supabase_dev",
            prompt_content="test metadata"
        )
        self.assertEqual(user_record.github_id, "999888")
        self.assertEqual(user_record.username, "supabase_dev")
        self.assertEqual(user_record.prompt_content, "test metadata")

    def test_environment_operational_rules_detection(self):
        """Test that ChatAgent dynamically and correctly detects the environment state and applies the appropriate system prompt/operational rules."""
        import os
        import shutil
        from unittest.mock import patch
        import json
        from agent.tools import WORKSPACE_DIR

        # Mock response to capture payload
        captured_payloads = []

        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code
            def json(self):
                return self._json

        async def mock_post_capture(*args, **kwargs):
            # Capture the JSON payload sent to Groq/LLM
            captured_payloads.append(kwargs.get("json"))
            return MockResponse({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "Mocked response",
                        "tool_calls": None
                    }
                }],
                "usage": {"total_tokens": 10}
            })

        with patch.dict(os.environ, {"GROQ_API_KEY": "mock_key"}), \
             patch("httpx.AsyncClient.post", side_effect=mock_post_capture):

            agent_instance = ChatAgent()

            # Scenario A: NO REPOSITORY (Empty Workspace / Standalone Chat)
            # Ensure workspace is totally empty or does not exist
            if os.path.exists(WORKSPACE_DIR):
                shutil.rmtree(WORKSPACE_DIR)

            captured_payloads.clear()
            res = asyncio.run(agent_instance.get_response("Hello, write some code please"))
            self.assertEqual(res["reply"], "Mocked response")
            self.assertTrue(len(captured_payloads) > 0)
            system_msg = captured_payloads[0]["messages"][0]["content"]
            self.assertIn("NO REPOSITORY (Empty Workspace / Standalone Chat)", system_msg)
            self.assertIn("Do NOT attempt to invoke disk writing tools", system_msg)

            # Scenario B: WORKSPACE WITH CLONED REPOSITORY (Repository Present)
            # Create workspace and add a file/folder to simulate cloned repo or project files
            os.makedirs(WORKSPACE_DIR, exist_ok=True)
            with open(os.path.join(WORKSPACE_DIR, "project_file.py"), "w") as f:
                f.write("# some python code")

            captured_payloads.clear()
            res = asyncio.run(agent_instance.get_response("Hello, please create a file"))
            self.assertTrue(len(captured_payloads) > 0)
            system_msg = captured_payloads[0]["messages"][0]["content"]
            self.assertIn("WORKSPACE WITH CLONED REPOSITORY (Repository Present)", system_msg)
            self.assertIn("automatically default the file path to the Root Directory", system_msg)

            # Scenario C: ROBLOX STUDIO CONNECTION (Active Studio Session)
            # Pass is_roblox=True or have roblox hint in prompt
            captured_payloads.clear()
            res = asyncio.run(agent_instance.get_response("Help me code Roblox Studio scripts"))
            self.assertTrue(len(captured_payloads) > 0)
            system_msg = captured_payloads[0]["messages"][0]["content"]
            self.assertIn("ROBLOX STUDIO CONNECTION (Active Studio Session)", system_msg)
            self.assertIn("Utilize available Roblox MCP tools", system_msg)

    def test_git_changes_endpoint(self):
        """Test git status changes tracking endpoint."""
        # 1. When no git repo exists, should return empty changes
        if os.path.exists(os.path.join(WORKSPACE_DIR, ".git")):
            shutil.rmtree(os.path.join(WORKSPACE_DIR, ".git"))
        response = self.client.get("/api/git/changes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(response.json()["changes"], {})

        # 2. Mock git porcelain output
        with patch("subprocess.run") as mock_run:
            import subprocess
            os.makedirs(os.path.join(WORKSPACE_DIR, ".git"), exist_ok=True)
            mock_run.return_value = subprocess.CompletedProcess(
                args="git status --porcelain",
                returncode=0,
                stdout=" M main.py\n?? test.py\n D deleted.py\n",
                stderr=""
            )
            response = self.client.get("/api/git/changes")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["changes"]["main.py"], "M")
            self.assertEqual(data["changes"]["test.py"], "??")
            self.assertEqual(data["changes"]["deleted.py"], "D")

    def test_git_commit_push_endpoint(self):
        """Test secure git commit and push changes endpoint."""
        payload = {
            "commit_message": "feat: test message",
            "repo_url": "https://github.com/shibihu/Myagent.git",
            "branch_name": "main",
            "token": "ghp_mock_token_123"
        }

        # Mock subprocess run to simulate successful push
        with patch("subprocess.run") as mock_run:
            import subprocess
            os.makedirs(os.path.join(WORKSPACE_DIR, ".git"), exist_ok=True)

            # Mock successful git push command (git push status returns 0)
            mock_run.return_value = subprocess.CompletedProcess(
                args="git push",
                returncode=0,
                stdout="Everything up-to-date",
                stderr=""
            )

            response = self.client.post("/api/git/commit-push", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "success")

        # Mock push failure and verify token masking
        with patch("subprocess.run") as mock_run:
            import subprocess
            def mock_run_impl(cmd, *args, **kwargs):
                if "status" in cmd or "porcelain" in cmd:
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=" M main.py", stderr="")
                elif "push" in cmd:
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=128,
                        stdout="",
                        stderr="fatal: Authentication failed for 'https://ghp_mock_token_123@github.com/shibihu/Myagent.git/'"
                    )
                else:
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            mock_run.side_effect = mock_run_impl
            response = self.client.post("/api/git/commit-push", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "error")
            self.assertIn("Git Push Error", data["message"])
            # The token MUST be masked
            self.assertNotIn("ghp_mock_token_123", data["message"])
            self.assertIn("https://***@", data["message"])

if __name__ == "__main__":
    unittest.main()
