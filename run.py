import os
from loguru import logger
from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"Starting Atlas AI Server at http://{host}:{port} (Debug: {debug})")
    app.run(debug=debug, host=host, port=port, threaded=True)
