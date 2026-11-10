from api import create_app
from credentialing.config import get_settings

app = create_app()


if __name__ == "__main__":
    # Local development only, bound to loopback so the debugger is never network-reachable.
    # Deployments run through gunicorn and never reach this block.
    app.run(debug=get_settings().flask_debug, host="127.0.0.1", port=5000)
