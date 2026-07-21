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
    # Ensure workspace exists
    ws = ensure_workspace()
    # Normalize path
    absolute_path = os.path.abspath(os.path.join(ws, filepath))
    # Throw an exception if directory traversal outside the workspace is attempted
    if not absolute_path.startswith(ws):
        raise ValueError("Directory traversal attempt detected.")
    return absolute_path

def read_file_tool(filepath: str) -> dict:
    """Reads the content of a file relative to the workspace."""
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
        return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def patch_file_tool(filepath: str, search_block: str, replace_block: str) -> dict:
    """Patches a file relative to the workspace using exact block search and replace."""
    try:
        target_path = clean_path(filepath)
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    if not os.path.exists(target_path):
        # If file doesn't exist, we can optionally create it if search_block is empty or if we want to write new content
        if not search_block:
            try:
                # Ensure parent dirs exist
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
            # Overwrite or append if search_block is completely empty
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(replace_block)
            return {"status": "success", "message": f"Successfully overwrote/wrote file '{filepath}'."}

        # Normalize line endings to avoid matching issues
        content_norm = content.replace("\r\n", "\n")
        search_norm = search_block.replace("\r\n", "\n")
        replace_norm = replace_block.replace("\r\n", "\n")

        if search_norm not in content_norm:
            return {
                "status": "error",
                "message": f"Could not find the exact search block in '{filepath}'. Ensure spacing/line endings match perfectly."
            }

        # Replace and write back
        new_content = content_norm.replace(search_norm, replace_norm, 1) # replace first occurrence only for safety
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {"status": "success", "message": f"Successfully patched '{filepath}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def view_dir_tool(path: str = ".") -> dict:
    """Recursively lists folders and files in the workspace directory."""
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
            # Ignore .git directory to keep clean
            if ".git" in dirs:
                dirs.remove(".git")

            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, ws)
                result_tree.append(rel_p)

        return {"status": "success", "files": sorted(result_tree)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def execute_command_tool(command: str) -> dict:
    """Executes a command inside the workspace directory."""
    ws = ensure_workspace()
    try:
        # We run the command using bash/shell in workspace directory
        process = subprocess.run(
            command,
            shell=True,
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60 # Timeout of 60 seconds to prevent hanging
        )
        return {
            "status": "success",
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr
        }
    except subprocess.TimeoutExpired as te:
        return {
            "status": "error",
            "message": f"Command timed out: {str(te)}",
            "stdout": te.stdout or "",
            "stderr": te.stderr or ""
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
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success", "message": f"Successfully wrote/overwrote file '{filepath}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def list_directory_tool(path: str = ".") -> dict:
    """Lists directory structure and contents in the workspace (alias to view_dir_tool)."""
    return view_dir_tool(path)

def clone_repository_tool(repo_url: str) -> dict:
    """Clones a GitHub repository into the workspace. If workspace has content, cleans it up first."""
    ws = ensure_workspace()
    try:
        # If workspace exists and has a .git, let's remove existing files or the folder to clean-slate it
        if os.path.exists(ws):
            # We can clean everything in the workspace folder first
            for item in os.listdir(ws):
                item_path = os.path.join(ws, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

        # Clone repo into ws
        # We clone to a temp directory or we clone directly inside ws (git clone <url> .)
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
            return {"status": "success", "message": f"Repository cloned successfully.", "stdout": process.stdout}
        else:
            return {"status": "error", "message": "Failed to clone repository.", "stderr": process.stderr}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def git_status_tool() -> dict:
    """Checks git status of the workspace."""
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
            "stdout": process.stdout,
            "stderr": process.stderr
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def git_rollback_tool() -> dict:
    """Rolls back all uncommitted changes in the workspace."""
    ws = ensure_workspace()
    if not os.path.exists(os.path.join(ws, ".git")):
        return {"status": "error", "message": "No git repository found in workspace."}

    try:
        # Hard reset
        res1 = subprocess.run(
            "git reset --hard HEAD",
            shell=True,
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Clean untracked files
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
            "reset_stdout": res1.stdout,
            "clean_stdout": res2.stdout
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
