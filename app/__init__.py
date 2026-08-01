import os
from flask import Flask
from dotenv import load_dotenv

from app.routes import bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app
