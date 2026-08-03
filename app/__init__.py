import os
from flask import Flask
from dotenv import load_dotenv

from app.routes import bp
from app.services.scheduler import start_scheduler

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)

    # Start background scheduler for automatic periodic news monitoring
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler()

    return app
