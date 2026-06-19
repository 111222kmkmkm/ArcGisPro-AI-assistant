"""
Named Pipe 通信层。

Client  (NamedPipeClient)  — MCP Server → ArcGIS Pro Add-In，发送地图/UI 控制指令
Server  (NamedPipeServer)  — ArcGIS Pro Add-In → MCP Server，接收 chat 请求
"""
from __future__ import annotations
import json
import struct
import threading
from typing import Callable, Any

PIPE_NAME      = r"\\.\pipe\mcp_arcgis_bridge"
CHAT_PIPE_NAME = r"\\.\pipe\mcp_arcgis_chat"
_BUFSIZE = 65536


# ---------------------------------------------------------------------------
# Client：MCP Server → ArcGIS Pro Add-In
# ---------------------------------------------------------------------------

class NamedPipeClient:
    """向 ArcGIS Pro Add-In 发送 UI/地图控制指令。"""

    def send_command(self, command: dict) -> dict:
        try:
            import pywintypes   # type: ignore
            import win32file    # type: ignore

            handle = win32file.CreateFile(
                PIPE_NAME,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None,
            )
            payload = json.dumps(command, ensure_ascii=False).encode("utf-8")
            win32file.WriteFile(handle, struct.pack(">I", len(payload)) + payload)

            _, raw = win32file.ReadFile(handle, _BUFSIZE)
            win32file.CloseHandle(handle)

            resp_len = struct.unpack(">I", raw[:4])[0]
            return json.loads(raw[4:4 + resp_len].decode("utf-8"))

        except Exception as exc:
            return {"success": False, "error": str(exc), "pro_unavailable": True}

    def send_notification(self, command: dict) -> dict:
        """单向通知：发送命令后不等待响应，避免管道竞态条件。"""
        try:
            import pywintypes   # type: ignore
            import win32file    # type: ignore

            handle = win32file.CreateFile(
                PIPE_NAME,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None,
            )
            payload = json.dumps(command, ensure_ascii=False).encode("utf-8")
            win32file.WriteFile(handle, struct.pack(">I", len(payload)) + payload)
            win32file.FlushFileBuffers(handle)
            win32file.CloseHandle(handle)
            return {"success": True}

        except Exception as exc:
            return {"success": False, "error": str(exc), "pro_unavailable": True}

    def is_pro_running(self) -> bool:
        return self.send_command({"action": "ping"}).get("success", False)


# ---------------------------------------------------------------------------
# Server：ArcGIS Pro Add-In → MCP Server（接收 chat 请求）
# ---------------------------------------------------------------------------

class NamedPipeChatServer:
    """
    监听来自 ArcGIS Pro Add-In 的聊天请求。
    handler(command: dict) -> dict  在调用线程中同步执行。
    """

    def __init__(self, handler: Callable[[dict], dict]) -> None:
        self._handler = handler
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pipe-chat-server")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                import pywintypes                     # type: ignore
                import win32pipe, win32file, win32con  # type: ignore

                pipe = win32pipe.CreateNamedPipe(
                    CHAT_PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    _BUFSIZE, _BUFSIZE,
                    0, None,
                )
                win32pipe.ConnectNamedPipe(pipe, None)

                # read length-prefixed message
                _, raw_len = win32file.ReadFile(pipe, 4)
                msg_len = struct.unpack(">I", raw_len)[0]

                data = b""
                while len(data) < msg_len:
                    _, chunk = win32file.ReadFile(pipe, msg_len - len(data))
                    data += chunk

                command = json.loads(data.decode("utf-8"))
                response = self._handler(command)

                payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
                win32file.WriteFile(pipe, struct.pack(">I", len(payload)) + payload)
                win32file.CloseHandle(pipe)

            except Exception as exc:
                import time
                if not self._stop.is_set():
                    time.sleep(0.5)
