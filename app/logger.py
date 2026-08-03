"""
logger.py
Central Loguru logger configuration and standard logging interception.
"""
import sys
import logging
from loguru import logger


class InterceptHandler(logging.Handler):
    """Intercept standard Python logging messages and redirect them to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller frame to preserve accurate line numbers and module info
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logger():
    """Configure Loguru logger sinks, formats, and standard library interceptors."""
    # Remove existing handlers
    logger.remove()

    # Configure stdout console logging with vibrant colors & detailed format
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level="DEBUG",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Intercept standard python logging (Flask, Werkzeug, APScheduler, urllib3)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Set specific third-party logger levels to avoid excessive noise
    for noisy in ["urllib3", "apscheduler.scheduler", "apscheduler.executors.default", "werkzeug"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.info("Loguru logging system initialized and active.")


# Run logger configuration upon module import
configure_logger()
