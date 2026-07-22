import os
import subprocess
import shutil
import re

# Workspace directory configuration
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", os.path.abspath(os.path.join(os.getcwd(), "workspace")))

def ensure_workspace():
    """Ensure the workspace directory exists."""
    if not os.path.exists(WORKSPACE_DIR):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
    return WORKSPACE_DIR

def clean_path(filepath: str) -> str:
    """Resolve path and ensure it remains inside the workspace directory for basic path containment."""
    ws = ensure_workspace()
    absolute_path = os.path.abspath(os.path.join(ws, filepath))
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

def read_file_tool(filepath: str) -> dict:
    """Reads the content of a file relative to the workspace, truncated to 1,000 characters."""
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
    """Patches a file relative to the workspace using exact block search and replace."""
    try:
        target_path = clean_path(filepath)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    if not os.path.exists(target_path):
        if not search_block:
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(replace_block)
                return {"status": "success", "message": f"Created new file '{filepath}' and wrote content."}
            except Exception as e:
                return {"status": "error", "message": f"Failed to create file: {str(e)}"}
        return {"status": "error", "message": f"File '{filepath}' not found and cannot be patched without empty search_block."}

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not search_block:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(replace_block)
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
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {"status": "success", "message": f"Successfully patched '{filepath}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def view_dir_tool(path: str = ".") -> dict:
    """Recursively lists folders and files in the workspace directory, limiting entries to prevent token exhaustion."""
    try:
        target_path = clean_path(path)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    if not os.path.exists(target_path):
        return {"status": "error", "message": f"Path '{path}' does not exist."}

    ws = ensure_workspace()
    result_tree = []
    try:
        for root, dirs, files in os.walk(target_path):
            if ".git" in dirs:
                dirs.remove(".git")

            for d in dirs:
                full_p = os.path.join(root, d)
                rel_p = os.path.relpath(full_p, ws) + "/"
                result_tree.append(rel_p)

            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, ws)
                result_tree.append(rel_p)

        # Limit entries in listing to keep tokens lightweight
        sorted_files = sorted(result_tree)
        if len(sorted_files) > 40:
            sorted_files = sorted_files[:40] + ["...[Truncated due to too many files]"]

        return {"status": "success", "files": sorted_files}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def execute_command_tool(command: str) -> dict:
    """Executes a command inside the workspace directory, with truncated stdout/stderr output."""
    ws = ensure_workspace()
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

def write_file_tool(filepath: str, content: str) -> dict:
    """Writes or overwrites a file inside the workspace entirely with the given content."""
    try:
        target_path = clean_path(filepath)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success", "message": f"Successfully wrote/overwrote file '{filepath}'."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to write file: {str(e)}"}

def list_directory_tool(path: str = ".") -> dict:
    """Lists directory structure and contents in the workspace (alias to view_dir_tool)."""
    return view_dir_tool(path)

def clone_repository_tool(repo_url: str) -> dict:
    """Clones a GitHub repository into the workspace. If workspace has content, cleans it up first."""
    ws = ensure_workspace()
    try:
        if shutil.which("git") is None:
            return {
                "status": "error",
                "message": "Git command not found on the system. Please ensure git is installed."
            }

        if os.path.exists(ws):
            try:
                shutil.rmtree(ws)
            except Exception as rmtree_err:
                for root, dirs, files in os.walk(ws, topdown=False):
                    for name in files:
                        try:
                            os.remove(os.path.join(root, name))
                        except Exception:
                            pass
                    for name in dirs:
                        try:
                            shutil.rmtree(os.path.join(root, name))
                        except Exception:
                            pass

        os.makedirs(ws, exist_ok=True)

        process = subprocess.run(
            f"git clone {repo_url} .",
            shell=True,
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120
        )
        if process.returncode == 0:
            return {
                "status": "success",
                "message": "Repository cloned successfully.",
                "stdout": truncate_text(process.stdout)
            }
        else:
            return {
                "status": "error",
                "message": "Failed to clone repository.",
                "stderr": truncate_text(process.stderr or "Unknown terminal clone error"),
                "stdout": truncate_text(process.stdout)
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

git_clone_tool = clone_repository_tool

def git_status_tool() -> dict:
    """Checks git status of the workspace, with truncated output."""
    ws = ensure_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        process = subprocess.run(
            "git status",
            shell=True,
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
    """Rolls back all uncommitted changes in the workspace, with truncated output."""
    ws = ensure_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        res1 = subprocess.run(
            "git reset --hard HEAD",
            shell=True,
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        res2 = subprocess.run(
            "git clean -fd",
            shell=True,
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
    """Switches to an existing branch or creates a new one, with truncated output."""
    ws = ensure_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        process = subprocess.run(
            f"git checkout {branch_name}",
            shell=True,
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if process.returncode != 0:
            process2 = subprocess.run(
                f"git checkout -b {branch_name}",
                shell=True,
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
    """Pulls the latest changes from the remote repository, with truncated output."""
    ws = ensure_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        process = subprocess.run(
            "git pull",
            shell=True,
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
