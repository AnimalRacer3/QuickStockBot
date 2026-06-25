"""
QuickStockBot installer entry point.

Opens a local web wizard in the user's default browser, then starts the
Flask wizard server on 127.0.0.1:7676.
"""

from __future__ import annotations

import threading
import time
import webbrowser

from wizard.server import create_app

PORT = 7676
_HOST = "127.0.0.1"


def main() -> None:
    app = create_app()

    def _open_browser() -> None:
        time.sleep(1.2)
        webbrowser.open(f"http://{_HOST}:{PORT}/")

    threading.Thread(target=_open_browser, daemon=True).start()
    print(f"QuickStockBot Installer — wizard at http://{_HOST}:{PORT}/")
    print("Press Ctrl+C to exit after setup is complete.\n")

    app.run(host=_HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
