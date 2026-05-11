"""Music Player Overlay — point d'entrée."""
import threading
import http.server
import functools
from pathlib import Path
from src.ui.control import ControlPanel
from src.core.config import AppConfig

def start_http_server(port: int, root: Path) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.HTTPServer(("localhost", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

if __name__ == "__main__":
    cfg = AppConfig.load()
    root = Path(__file__).parent
    server = start_http_server(cfg.overlay_port, root)
    app = ControlPanel(cfg, server)
    app.mainloop()
