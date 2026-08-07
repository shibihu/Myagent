import os
import subprocess
import shutil
import re
import logging
import asyncio
import json
import base64

# Import terminal_manager ให้ถูกต้องตามโครงสร้างโปรเจกต์ของคุณ
try:
    from backend.terminal_manager import terminal_manager
except ImportError:
    terminal_manager = None

logger = logging.getLogger(__name__)

# Workspace directory configuration
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", os.path.abspath(os.path.join(os.getcwd(), "workspace")))

# Serverless Vercel write-allowed environment adjustment
if os.environ.get("VERCEL"):
    WORKSPACE_DIR = "/tmp/workspace"

ACTIVE_REPO_NAME = None

def get_active_workspace() -> str:
    """Dynamically resolves the active workspace folder context (root or active cloned repo)."""
    base_ws = ensure_workspace()
    global ACTIVE_REPO_NAME
    if ACTIVE_REPO_NAME:
        target_path = os.path.abspath(os.path.join(base_ws, ACTIVE_REPO_NAME))
        if target_path.startswith(base_ws):
            os.makedirs(target_path, exist_ok=True)
            return target_path
    return base_ws

def ensure_workspace():
    """Ensure the workspace directory exists."""
    if not os.path.exists(WORKSPACE_DIR):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)

    # Configure default git user identity to prevent commit errors
    try:
        if shutil.which("git") is not None:
            subprocess.run(
                ["git", "config", "--global", "user.name", "MyAgent Bot"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            subprocess.run(
                ["git", "config", "--global", "user.email", "myagent@bot.local"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
    except Exception as e:
        print(f"[Git Identity Config Warning]: {e}")

    return WORKSPACE_DIR

def clean_path(filepath: str) -> str:
    """Resolve path and ensure it remains inside the workspace directory for basic path containment."""
    ws = get_active_workspace()

    cleaned = filepath.lstrip("/\\")
    if cleaned.startswith("./") or cleaned.startswith(".\\"):
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("/\\")

    absolute_path = os.path.abspath(os.path.join(ws, cleaned))
    if not absolute_path.startswith(ws):
        raise ValueError("Directory traversal attempt detected.")
    return absolute_path

def truncate_text(val: str, max_chars: int = 1000) -> str:
    """Utility helper to truncate long tool output strings to preserve tokens."""
    if not val or not isinstance(val, str):
        return val
    if len(val) > max_chars:
        return val[:max_chars] + "\n...[Truncated]"
    return val

def _write_and_sync_file(path: str, content: bytes | str, binary: bool = False, encoding: str = "utf-8") -> None:
    """Writes file content synchronously to disk and ensures buffers are flushed."""
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    mode = "wb" if binary else "w"
    with open(path, mode, encoding=None if binary else encoding) as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())

    try:
        dir_path = os.path.dirname(path) or "."
        if hasattr(os, "O_DIRECTORY"):
            dir_fd = os.open(dir_path, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except Exception as e:
        logger.debug("Directory fsync skipped or failed: %s", e)

def read_file_tool(filepath: str) -> dict:
    try:
        target_path = clean_path(filepath)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    if not os.path.exists(target_path):
        return {"status": "error", "message": f"File '{filepath}' not found."}
    if os.path.isdir(target_path):
        return {"status": "error", "message": f"'{filepath}' is a directory, not a file."}
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"status": "success", "content": truncate_text(content)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def patch_file_tool(filepath: str, search_block: str, replace_block: str) -> dict:
    try:
        target_path = clean_path(filepath)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    if not os.path.exists(target_path):
        if not search_block:
            try:
                _write_and_sync_file(target_path, replace_block, binary=False)
                return {"status": "success", "message": f"Created new file '{filepath}' and wrote content."}
            except Exception as e:
                logger.error("Disk write failed while creating new file %s: %s", filepath, e)
                return {"status": "error", "message": f"Failed to create file: {str(e)}"}
        return {"status": "error", "message": f"File '{filepath}' not found and cannot be patched without empty search_block."}

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not search_block:
            _write_and_sync_file(target_path, replace_block, binary=False)
            return {"status": "success", "message": f"Successfully overwrote/wrote file '{filepath}'."}

        content_norm = content.replace("\r\n", "\n")
        search_norm = search_block.replace("\r\n", "\n")
        replace_norm = replace_block.replace("\r\n", "\n")

        if search_norm not in content_norm:
            return {
                "status": "error",
                "message": f"Could not find the exact search block in '{filepath}'. Ensure spacing/line endings match perfectly."
            }

        new_content = content_norm.replace(search_norm, replace_norm, 1)
        _write_and_sync_file(target_path, new_content, binary=False)

        return {"status": "success", "message": f"Successfully patched '{filepath}'."}
    except Exception as e:
        logger.error("Disk write failed while patching file %s: %s", filepath, e)
        return {"status": "error", "message": str(e)}

def view_dir_tool(path: str = ".") -> dict:
    try:
        target_path = clean_path(path)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    if not os.path.exists(target_path):
        return {"status": "error", "message": f"Path '{path}' does not exist."}

    ws = get_active_workspace()
    result_tree = []
    try:
        for root, dirs, files in os.walk(target_path):
            if ".git" in dirs:
                dirs.remove(".git")

            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, ws)
                result_tree.append(rel_p)

        sorted_files = sorted(result_tree)
        if len(sorted_files) > 40:
            sorted_files = sorted_files[:40] + ["...[Truncated due to too many files]"]

        return {"status": "success", "files": sorted_files}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def execute_command_tool(command: str) -> dict:
    ws = get_active_workspace()

    if "git push" in command or "git commit" in command or (shutil.which("git") is None and "git " in command):
        commit_message = "Update from MyAgent"
        match = re.search(r'-m\s+["\']([^"\']+)["\']', command)
        if match:
            commit_message = match.group(1)
        else:
            match = re.search(r'--message=["\']([^"\']+)["\']', command)
            if match:
                commit_message = match.group(1)

        return sync_workspace_to_github_rest(commit_message)

    try:
        process = subprocess.run(
            command,
            shell=True,
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        return {
            "status": "success",
            "returncode": process.returncode,
            "stdout": truncate_text(process.stdout),
            "stderr": truncate_text(process.stderr)
        }
    except subprocess.TimeoutExpired as te:
        return {
            "status": "error",
            "message": f"Command timed out: {str(te)}",
            "stdout": truncate_text(te.stdout or ""),
            "stderr": truncate_text(te.stderr or "")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def sync_workspace_to_github_rest(commit_message: str = "Update from MyAgent") -> dict:
    try:
        import httpx

        ws = get_active_workspace()
        config_path = os.path.join(ws, ".github_config.json")
        if not os.path.exists(config_path):
            return {"status": "error", "message": "No GitHub repository config found. Please clone the repository first."}

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        owner = config.get("owner")
        repo = config.get("repo")
        token = config.get("token")

        if not owner or not repo or not token:
            return {"status": "error", "message": "Invalid GitHub repository credentials stored."}

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"token {token}"
        }

        synced_files = []
        for root, dirs, files in os.walk(ws):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file in files:
                if file == ".github_config.json":
                    continue
                filepath = os.path.join(root, file)
                relative_path = os.path.relpath(filepath, ws)

                with open(filepath, "rb") as f:
                    local_bytes = f.read()

                local_base64 = base64.b64encode(local_bytes).decode("utf-8")
                get_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{relative_path}"
                sha = None

                with httpx.Client(follow_redirects=True) as client:
                    resp = client.get(get_url, headers=headers)
                    if resp.status_code == 200:
                        sha = resp.json().get("sha")

                put_data = {
                    "message": commit_message,
                    "content": local_base64
                }
                if sha:
                    put_data["sha"] = sha

                with httpx.Client(follow_redirects=True) as client:
                    put_resp = client.put(get_url, headers=headers, json=put_data)
                    if put_resp.status_code in [200, 201]:
                        synced_files.append(relative_path)

        return {
            "status": "success",
            "message": f"Successfully pushed and synced local workspace changes directly to GitHub repository using REST API.",
            "synced_files": synced_files
        }
    except Exception as e:
        return {"status": "error", "message": f"Serverless GitHub sync failed: {str(e)}"}

def write_file_tool(filepath: str, content: str) -> dict:
    studio_mcp_url = os.environ.get("STUDIO_MCP_URL")
    if studio_mcp_url and (filepath.endswith(".lua") or filepath.endswith(".luau")):
        try:
            import httpx
            filename = os.path.basename(filepath)
            script_name = os.path.splitext(filename)[0]

            script_type = "Script"
            parent = "ServerScriptService"

            path_lower = filepath.lower()
            if "starterplayer" in path_lower or "local" in path_lower:
                script_type = "LocalScript"
                parent = "StarterPlayerScripts"
            elif "replicatedstorage" in path_lower or "module" in path_lower:
                script_type = "ModuleScript"
                parent = "ReplicatedStorage"

            payload = {
                "action": "create_or_update_script",
                "script_type": script_type,
                "parent": parent,
                "name": script_name,
                "content": content
            }

            headers = {
                "Content-Type": "application/json",
                "ngrok-skip-browser-warning": "true"
            }

            with httpx.Client(follow_redirects=True, timeout=10) as client:
                resp = client.post(studio_mcp_url, json=payload, headers=headers)
                if resp.status_code in [200, 201]:
                    return {
                        "status": "success",
                        "message": f"Successfully created/modified script '{script_name}' in Roblox Studio ({parent}) via Ngrok-MCP.",
                        "studio_response": resp.json() if "application/json" in resp.headers.get("content-type", "") else resp.text
                    }
                else:
                    raise Exception(f"Roblox Studio MCP returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to dispatch script to Roblox Studio via Ngrok-MCP: {str(e)}. Fallback to local files."
            }

    try:
        target_path = clean_path(filepath)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    try:
        _write_and_sync_file(target_path, content, binary=False)
        return {"status": "success", "message": f"Successfully wrote/overwrote file '{filepath}'."}
    except Exception as e:
        logger.error("Disk write failed for %s: %s", filepath, e)
        return {"status": "error", "message": f"Failed to write file: {str(e)}"}

def list_directory_tool(path: str = ".") -> dict:
    return view_dir_tool(path)

async def clone_repository_tool(repo_url: str) -> dict:
    try:
        repo_name = repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        session_id = "default_session"
        session = terminal_manager.get_session(session_id) if terminal_manager else None

        if session:
            command = f"git clone {repo_url} && cd {repo_name}\n"
            await session.write(command)
            return {
                "status": "success", 
                "message": f"Sent command to terminal: git clone and cd to {repo_name}"
            }
        else:
            subprocess.run(
                ["git", "clone", repo_url], 
                cwd=WORKSPACE_DIR, 
                check=True, 
                capture_output=True
            )
            return {
                "status": "success", 
                "message": f"Cloned {repo_name} successfully into workspace."
            }

    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Git Error: {e.stderr.decode()}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

git_clone_tool = clone_repository_tool

def git_status_tool() -> dict:
    ws = get_active_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        process = subprocess.run(
            ["git", "status"],
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return {
            "status": "success",
            "stdout": truncate_text(process.stdout),
            "stderr": truncate_text(process.stderr)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def git_rollback_tool() -> dict:
    ws = get_active_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        res1 = subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        res2 = subprocess.run(
            ["git", "clean", "-fd"],
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return {
            "status": "success",
            "message": "Successfully rolled back changes using hard reset and clean.",
            "reset_stdout": truncate_text(res1.stdout),
            "clean_stdout": truncate_text(res2.stdout)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def git_checkout_tool(branch_name: str) -> dict:
    ws = get_active_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        process = subprocess.run(
            ["git", "checkout", branch_name],
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if process.returncode != 0:
            process2 = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=ws,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if process2.returncode == 0:
                return {
                    "status": "success",
                    "message": f"Successfully created and switched to branch '{branch_name}'.",
                    "stdout": truncate_text(process2.stdout)
                }
            return {
                "status": "error",
                "message": f"Failed to checkout branch '{branch_name}'.",
                "stderr": truncate_text(process.stderr + "\n" + process2.stderr)
            }
        return {
            "status": "success",
            "message": f"Successfully switched to branch '{branch_name}'.",
            "stdout": truncate_text(process.stdout)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def git_pull_tool() -> dict:
    ws = get_active_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        process = subprocess.run(
            ["git", "pull"],
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if process.returncode == 0:
            return {
                "status": "success",
                "message": "Successfully pulled changes from remote.",
                "stdout": truncate_text(process.stdout)
            }
        return {
            "status": "error",
            "message": "Failed to pull changes.",
            "stderr": truncate_text(process.stderr)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}