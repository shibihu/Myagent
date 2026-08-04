import os
import sys
import asyncio
import pty
import fcntl
import struct
import termios
import subprocess
from typing import Dict, Optional, Callable
import asyncssh

# Import SSH profile manager
from backend.ssh_manager import get_ssh_server_decrypted

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
    """Real Unix PTY session running a local bash shell."""
    def __init__(self, session_id: str, on_output: Callable[[str], None], on_close: Callable[[], None]):
        self.session_id = session_id
        self.on_output = on_output
        self.on_close = on_close
        self.master_fd = None
        self.proc = None
        self.closed = False

    async def start(self, cols: int = 80, rows: int = 24):
        try:
            # Create master/slave PTY pair
            self.master_fd, slave_fd = pty.openpty()

            # Set non-blocking read on master
            fl = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            # Set initial PTY size
            self._set_pty_size(cols, rows)

            # Determine shell to launch
            shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"

            # Spawn shell with slave FD as stdout/stdin/stderr
            self.proc = await asyncio.create_subprocess_exec(
                shell,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                env=os.environ.copy()
            )

            # Close slave FD in parent process as it is now owned by child
            os.close(slave_fd)

            # Start background task to read from master_fd
            asyncio.create_task(self._read_loop())

            # Start background task to monitor process exit
            asyncio.create_task(self._wait_loop())

        except Exception as e:
            self.on_output(f"\r\n[Local Shell Error]: Failed to start local terminal process: {e}\r\n")
            await self.close()

    def _set_pty_size(self, cols: int, rows: int):
        if self.master_fd is not None:
            try:
                # TIOCSWINSZ window size structure
                size_struct = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size_struct)
            except Exception as e:
                print(f"[Local Session] Failed to set window size: {e}")

    async def _read_loop(self):
        loop = asyncio.get_running_loop()
        while not self.closed:
            try:
                # Wait for data to be available on master_fd
                await asyncio.sleep(0.01) # Small throttle to prevent CPU thrashing
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
        if self.master_fd is not None and not self.closed:
            try:
                os.write(self.master_fd, data.encode("utf-8"))
            except Exception:
                await self.close()

    async def resize(self, cols: int, rows: int):
        self._set_pty_size(cols, rows)

    async def close(self):
        if self.closed:
            return
        self.closed = True

        # Unregister and close FD
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None

        # Terminate shell process
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None

        # Notify callback
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

            # Connection options
            connect_kwargs = {
                "host": host,
                "port": port,
                "username": username,
                "known_hosts": None,  # For convenience/bypass host key check
            }

            if auth_method == "password":
                connect_kwargs["password"] = config.get("password")
            else:
                # Private key authentication
                pk_data = config.get("private_key")
                passphrase = config.get("passphrase")
                if pk_data:
                    # Load the private key securely from string
                    try:
                        key = asyncssh.import_private_key(pk_data, passphrase)
                        connect_kwargs["client_keys"] = [key]
                    except Exception as e:
                        raise ValueError(f"Failed to import private key: {e}")

            # Open SSH Connection
            self.conn = await asyncssh.connect(**connect_kwargs)

            # Start session with PTY allocation
            self.chan, _ = await self.conn.create_session(
                asyncssh.SSHClientProcess,
                term_type="xterm-color",
                term_size=(cols, rows)
            )

            # Start background reader
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
                # Handle bytes vs string output from stdout
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
        """Creates and starts a session. If server_id is supplied, it connects via SSH, otherwise spawns local PTY."""
        # Lazily start the background cleanup loop when the first session is created and loop is active
        if self.cleanup_task is None:
            try:
                self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            except Exception:
                pass

        # Clean existing session if any
        if session_id in self.sessions:
            await self.sessions[session_id].close()

        def on_close_callback():
            if session_id in self.sessions:
                del self.sessions[session_id]

        if server_id:
            # Connect via SSH
            config = get_ssh_server_decrypted(server_id)
            if not config:
                raise ValueError(f"SSH configuration with ID '{server_id}' not found.")

            sess = SSHTerminalSession(session_id, on_output, on_close_callback)
            self.sessions[session_id] = sess
            await sess.start(config, cols, rows)
        else:
            # Spawn local terminal
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
        """Periodically cleans up dead sessions."""
        while True:
            await asyncio.sleep(30)
            dead_ids = [sid for sid, sess in self.sessions.items() if not sess.is_alive()]
            for sid in dead_ids:
                print(f"[Terminal Manager] Auto-cleaning dead terminal session: {sid}")
                await self.close_session(sid)


# Global terminal manager instance
terminal_manager = TerminalManager()
