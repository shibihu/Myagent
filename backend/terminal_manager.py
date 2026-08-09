import os
import sys
import asyncio
import subprocess
from typing import Dict, Optional, Callable
import asyncssh

# Import SSH profile manager
from backend.ssh_manager import get_ssh_server_decrypted

# Check OS environment for Windows compatibility
IS_WINDOWS = sys.platform == "win32"

if not IS_WINDOWS:
    import pty
    import fcntl
    import struct
    import termios


class TerminalSession:
    """Base interface for a terminal session."""
    async def write(self, data: str):
        pass

    async def resize(self, cols: int, rows: int):
        pass

    async def close(self):
        pass

    def is_alive(self) -> bool:
        return False


class LocalTerminalSession(TerminalSession):
    """Local terminal session supporting both Windows (cmd/powershell) and Unix (PTY/bash)."""
    def __init__(self, session_id: str, on_output: Callable[[str], None], on_close: Callable[[], None]):
        self.session_id = session_id
        self.on_output = on_output
        self.on_close = on_close
        self.master_fd = None
        self.proc = None
        self.closed = False

    async def start(self, cols: int = 80, rows: int = 24):
        try:
            if IS_WINDOWS:
                # Spawn Windows Command Prompt or PowerShell
                shell = "powershell.exe" if os.path.exists("C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe") else "cmd.exe"
                self.proc = await asyncio.create_subprocess_exec(
                    shell,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=os.environ.copy()
                )
                asyncio.create_task(self._read_pipe(self.proc.stdout))
                asyncio.create_task(self._read_pipe(self.proc.stderr))
            else:
                # Real Unix PTY session
                self.master_fd, slave_fd = pty.openpty()

                fl = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
                fcntl.fcntl(self.master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

                self._set_pty_size(cols, rows)

                shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"

                self.proc = await asyncio.create_subprocess_exec(
                    shell,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    env=os.environ.copy()
                )

                os.close(slave_fd)
                asyncio.create_task(self._read_loop())

            asyncio.create_task(self._wait_loop())

        except Exception as e:
            self.on_output(f"\r\n[Local Shell Error]: Failed to start local terminal process: {e}\r\n")
            await self.close()

    def _set_pty_size(self, cols: int, rows: int):
        if not IS_WINDOWS and self.master_fd is not None:
            try:
                size_struct = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size_struct)
            except Exception as e:
                print(f"[Local Session] Failed to set window size: {e}")

    async def _read_pipe(self, pipe):
        """Reads stream bytes for Windows subprocess pipes."""
        while not self.closed and pipe:
            try:
                data = await pipe.read(8192)
                if not data:
                    break
                self.on_output(data.decode("utf-8", errors="ignore"))
            except Exception:
                break
        await self.close()

    async def _read_loop(self):
        """Reads master FD for Unix PTY."""
        while not self.closed:
            try:
                await asyncio.sleep(0.01)
                try:
                    data = os.read(self.master_fd, 8192)
                    if not data:
                        break
                    self.on_output(data.decode("utf-8", errors="ignore"))
                except BlockingIOError:
                    continue
            except Exception:
                break
        await self.close()

    async def _wait_loop(self):
        if self.proc:
            await self.proc.wait()
        await self.close()

    async def write(self, data: str):
        if self.closed:
            return
        try:
            if IS_WINDOWS and self.proc and self.proc.stdin:
                self.proc.stdin.write(data.encode("utf-8"))
                await self.proc.stdin.drain()
            elif self.master_fd is not None:
                os.write(self.master_fd, data.encode("utf-8"))
        except Exception:
            await self.close()

    async def resize(self, cols: int, rows: int):
        if not IS_WINDOWS:
            self._set_pty_size(cols, rows)

    async def close(self):
        if self.closed:
            return
        self.closed = True

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None

        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

        self.on_close()

    def is_alive(self) -> bool:
        return not self.closed and self.proc is not None and self.proc.returncode is None


class SSHTerminalSession(TerminalSession):
    """AsyncSSH-based remote SSH session."""
    def __init__(self, session_id: str, on_output: Callable[[str], None], on_close: Callable[[], None]):
        self.session_id = session_id
        self.on_output = on_output
        self.on_close = on_close
        self.conn = None
        self.chan = None
        self.closed = False

    async def start(self, config: dict, cols: int = 80, rows: int = 24):
        try:
            host = config.get("host")
            port = int(config.get("port", 22))
            username = config.get("username")
            auth_method = config.get("auth_method", "password")

            connect_kwargs = {
                "host": host,
                "port": port,
                "username": username,
                "known_hosts": None,
            }

            if auth_method == "password":
                connect_kwargs["password"] = config.get("password")
            else:
                pk_data = config.get("private_key")
                passphrase = config.get("passphrase")
                if pk_data:
                    try:
                        key = asyncssh.import_private_key(pk_data, passphrase)
                        connect_kwargs["client_keys"] = [key]
                    except Exception as e:
                        raise ValueError(f"Failed to import private key: {e}")

            self.conn = await asyncssh.connect(**connect_kwargs)

            self.chan, _ = await self.conn.create_session(
                asyncssh.SSHClientProcess,
                term_type="xterm-color",
                term_size=(cols, rows)
            )

            asyncio.create_task(self._read_loop())

        except Exception as e:
            self.on_output(f"\r\n\x1b[1;31m[SSH Connection Error]: {e}\x1b[0m\r\n")
            await self.close()

    async def _read_loop(self):
        if not self.chan:
            return
        while not self.closed:
            try:
                data = await self.chan.stdout.read(8192)
                if not data:
                    break
                if isinstance(data, bytes):
                    self.on_output(data.decode("utf-8", errors="ignore"))
                else:
                    self.on_output(data)
            except Exception:
                break
        await self.close()

    async def write(self, data: str):
        if self.chan and not self.closed:
            try:
                self.chan.stdin.write(data)
            except Exception:
                await self.close()

    async def resize(self, cols: int, rows: int):
        if self.chan and not self.closed:
            try:
                self.chan.set_terminal_size(cols, rows)
            except Exception:
                pass

    async def close(self):
        if self.closed:
            return
        self.closed = True

        if self.chan:
            try:
                self.chan.close()
            except Exception:
                pass
            self.chan = None

        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

        self.on_close()

    def is_alive(self) -> bool:
        return not self.closed and self.chan is not None


class TerminalManager:
    """Manages concurrent Terminal Sessions (local and SSH remote)."""
    def __init__(self):
        self.sessions: Dict[str, TerminalSession] = {}
        self.cleanup_task = None

    async def create_session(self, session_id: str, on_output: Callable[[str], None], server_id: Optional[str] = None, cols: int = 80, rows: int = 24) -> TerminalSession:
        if self.cleanup_task is None:
            try:
                self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            except Exception:
                pass

        if session_id in self.sessions:
            await self.sessions[session_id].close()

        def on_close_callback():
            if session_id in self.sessions:
                del self.sessions[session_id]

        if server_id:
            config = get_ssh_server_decrypted(server_id)
            if not config:
                raise ValueError(f"SSH configuration with ID '{server_id}' not found.")

            sess = SSHTerminalSession(session_id, on_output, on_close_callback)
            self.sessions[session_id] = sess
            await sess.start(config, cols, rows)
        else:
            sess = LocalTerminalSession(session_id, on_output, on_close_callback)
            self.sessions[session_id] = sess
            await sess.start(cols, rows)

        return sess

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        return self.sessions.get(session_id)

    async def close_session(self, session_id: str):
        if session_id in self.sessions:
            await self.sessions[session_id].close()

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(30)
            dead_ids = [sid for sid, sess in self.sessions.items() if not sess.is_alive()]
            for sid in dead_ids:
                print(f"[Terminal Manager] Auto-cleaning dead terminal session: {sid}")
                await self.close_session(sid)


# Global terminal manager instance
terminal_manager = TerminalManager()