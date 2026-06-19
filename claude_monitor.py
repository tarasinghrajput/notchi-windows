import json
import socketserver
from PyQt6.QtCore import QThread, pyqtSignal


class _ClaudeHandler(socketserver.BaseRequestHandler):
    """Handles a single inbound hook connection: reads the full payload,
    parses JSON, and hands it to the server's event callback."""

    def handle(self):
        try:
            self.request.settimeout(2.0)
            chunks = []
            while True:
                data = self.request.recv(4096)
                if not data:
                    break
                chunks.append(data)
            raw = b"".join(chunks)
            if raw:
                payload = json.loads(raw.decode("utf-8"))
                self.server.event_callback(payload)
        except Exception:
            # A malformed or partial payload must never crash the server.
            pass


class _ClaudeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler, event_callback):
        self.event_callback = event_callback
        super().__init__(server_address, handler)


class ClaudeMonitor(QThread):
    """Listens on a TCP port for hook payloads sent by notchi-hook.sh
    (running inside WSL) and re-emits each event onto the Qt main thread."""

    event_received = pyqtSignal(dict)

    def __init__(self, port=8765, parent=None):
        super().__init__(parent)
        self.port = port
        self._is_running = True
        self._server = None

    def run(self):
        try:
            self._server = _ClaudeServer(
                ("0.0.0.0", self.port),
                _ClaudeHandler,
                self._on_event,
            )
            # Short timeout lets the loop re-check _is_running for clean shutdown.
            self._server.timeout = 1.0
            while self._is_running:
                self._server.handle_request()
        except Exception as e:
            print(f"ClaudeMonitor error: {e}")
        finally:
            self._close_server()

    def _on_event(self, payload):
        # Runs on a handler thread; emitting the signal hops to the Qt main thread.
        self.event_received.emit(payload)

    def _close_server(self):
        try:
            if self._server:
                self._server.server_close()
        except Exception:
            pass

    def stop(self):
        self._is_running = False
        self._close_server()
        self.wait()
