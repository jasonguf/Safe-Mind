"""
NeuroView Desktop Application
Launches the NeuroView brain viewer as a native desktop application.
"""

import os
import sys
import threading
import time
import webview
import uvicorn
from pathlib import Path

# Get the directory where this script is located
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(os.path.dirname(sys.executable))
else:
    # Running as script
    BASE_DIR = Path(__file__).parent
    APP_DIR = BASE_DIR

# Import the FastAPI app
sys.path.insert(0, str(BASE_DIR / 'backend'))
from server import app

# Server configuration
HOST = '127.0.0.1'
PORT = 8000
SERVER_URL = f'http://{HOST}:{PORT}'


class ServerThread(threading.Thread):
    """Run uvicorn server in a background thread."""

    def __init__(self):
        super().__init__(daemon=True)
        self.server = None

    def run(self):
        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False
        )
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


def wait_for_server(timeout=10):
    """Wait for the server to be ready."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f'{SERVER_URL}/', timeout=1)
            return True
        except:
            time.sleep(0.1)
    return False


def get_html_path():
    """Get the path to the HTML file."""
    html_file = BASE_DIR / 'brain_viewer.html'
    if html_file.exists():
        return str(html_file)
    # Fallback to current directory
    return str(Path(__file__).parent / 'brain_viewer.html')


def main():
    print("Starting NeuroView...")

    # Start the backend server
    server_thread = ServerThread()
    server_thread.start()

    # Wait for server to be ready
    print("Waiting for server...")
    if not wait_for_server():
        print("Error: Server failed to start")
        sys.exit(1)

    print("Server ready!")

    # Create the webview window
    html_path = get_html_path()
    print(f"Loading: {html_path}")

    # Create window with the HTML file
    window = webview.create_window(
        title='NeuroView - Neural Imaging System',
        url=html_path,
        width=1400,
        height=900,
        min_size=(1000, 700),
        resizable=True,
        frameless=False,
        easy_drag=False,
        text_select=False
    )

    # Start the GUI (this blocks until window is closed)
    webview.start(debug=False)

    # Cleanup
    print("Shutting down...")
    server_thread.stop()


if __name__ == '__main__':
    main()
