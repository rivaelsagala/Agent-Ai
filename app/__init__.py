from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv

from app.logger import logger
from app.routes import router
from app.services.scheduler import start_scheduler, stop_scheduler

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing FastAPI application...")
    logger.info("Triggering background scheduler startup...")
    start_scheduler()
    logger.info("FastAPI application initialized successfully.")
    yield
    logger.info("Shutting down FastAPI application...")
    stop_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zimbo AI Server",
        description="Autonomous ReAct Multi-Agent Backend for Financial Market Intelligence & Multi-Channel Alerting",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


