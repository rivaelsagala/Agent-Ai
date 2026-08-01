import os
from flask import Flask
from dotenv import load_dotenv

from app.routes import bp
from app.admin_routes import admin_bp

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)
    app.register_blueprint(admin_bp)
    return app
