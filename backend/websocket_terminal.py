import os
import json
import asyncio
import jwt
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Import terminal and SSH managers
from backend.terminal_manager import terminal_manager
from backend.ssh_manager import list_ssh_servers
import agent.auth as auth_mod

# Create APIRouter
router = APIRouter()

async def authenticate_ws(websocket: WebSocket) -> bool:
    """Authenticates the WebSocket connection using JWT from cookies or query parameters."""
    # 1. Look for token in cookies
    token = websocket.cookies.get("access_token")

    # 2. Fallback to query parameter
    if not token:
        token = websocket.query_params.get("token")

    # If no secret configured, allow bypass for local dev/test environment
    if not auth_mod.JWT_SECRET:
        print("[WS Auth] Warning: JWT_SECRET not set. Bypassing WS authentication for local dev.")
        return True

    if not token:
        print("[WS Auth] Connection rejected: No token found in cookies or query params.")
        return False

    try:
        payload = jwt.decode(token, auth_mod.JWT_SECRET, algorithms=[auth_mod.JWT_ALGORITHM])
        github_id = payload.get("sub")
        if github_id:
            return True
    except Exception as e:
        print(f"[WS Auth] Token decoding failed: {e}")

    return False

@router.websocket("/ws/terminal")
async def websocket_terminal_endpoint(websocket: WebSocket):
    # Accept the initial handshake
    await websocket.accept()

    # Authenticate standard session
    is_authenticated = await authenticate_ws(websocket)
    if not is_authenticated:
        await websocket.send_json({"action": "error", "message": "Unauthorized terminal session."})
        await websocket.close(code=4001)
        return

    session_id: Optional[str] = None
    send_queue = asyncio.Queue()
    send_task = None
    loop = asyncio.get_running_loop()

    # Outgoing serialization loop
    async def send_loop():
        try:
            while True:
                msg = await send_queue.get()
                if msg is None:
                    break
                await websocket.send_json(msg)
                send_queue.task_done()
        except Exception:
            pass

    # Start send loop task
    send_task = asyncio.create_task(send_loop())

    def on_output_callback(data: str):
        # Queue the stdout to be sent to client
        loop.call_soon_threadsafe(send_queue.put_nowait, {"action": "output", "data": data})

    try:
        while True:
            # Receive incoming text message
            data_str = await websocket.receive_text()
            try:
                msg = json.loads(data_str)
            except Exception:
                await send_queue.put({"action": "error", "message": "Invalid message format. JSON expected."})
                continue

            # Validate action
            action = msg.get("action")
            if not action:
                await send_queue.put({"action": "error", "message": "Missing 'action' field."})
                continue

            if action == "connect":
                # Connect / spawn terminal session
                session_id = msg.get("session_id") or "default_session"
                server_id = msg.get("server_id")  # None implies local fallback shell
                cols = int(msg.get("cols", 80))
                rows = int(msg.get("rows", 24))

                try:
                    await terminal_manager.create_session(
                        session_id=session_id,
                        on_output=on_output_callback,
                        server_id=server_id,
                        cols=cols,
                        rows=rows
                    )
                    await send_queue.put({"action": "connected", "session_id": session_id})
                except Exception as e:
                    await send_queue.put({"action": "error", "message": f"Connection failed: {str(e)}"})

            elif action == "input":
                # Forward key input to PTY
                if session_id:
                    sess = terminal_manager.get_session(session_id)
                    if sess:
                        # Prevent command injection - write raw data/strokes directly to standard PTY stream
                        input_data = msg.get("data", "")
                        await sess.write(input_data)
                    else:
                        await send_queue.put({"action": "error", "message": "Session not found."})
                else:
                    await send_queue.put({"action": "error", "message": "No active session. Connect first."})

            elif action == "resize":
                # Resize terminal window
                if session_id:
                    sess = terminal_manager.get_session(session_id)
                    if sess:
                        cols = int(msg.get("cols", 80))
                        rows = int(msg.get("rows", 24))
                        await sess.resize(cols, rows)

            elif action == "disconnect":
                # Close terminal session
                if session_id:
                    await terminal_manager.close_session(session_id)
                    session_id = None
                await send_queue.put({"action": "disconnected"})

            elif action == "heartbeat":
                # Standard keepalive check
                await send_queue.put({"action": "heartbeat"})

    except WebSocketDisconnect:
        print(f"[WS Terminal] WebSocket disconnected for session: {session_id}")
    except Exception as e:
        print(f"[WS Terminal] Error handling WebSocket message: {e}")
    finally:
        # Clean up session
        if session_id:
            await terminal_manager.close_session(session_id)

        # Stop outgoing send queue
        if send_task:
            send_task.cancel()
